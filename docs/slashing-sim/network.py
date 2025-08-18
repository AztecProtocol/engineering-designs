import random
import numpy as np
import numba
from numba import jit, prange
from typing import Dict, Set, List, Optional, Tuple

try:
    from .models import Block, Attestation, PropagationTrace, SimulationConfig, BehaviorProfile
except ImportError:
    from models import Block, Attestation, PropagationTrace, SimulationConfig, BehaviorProfile


@jit(nopython=True)
def propagate_message_fast(
    adjacency_matrix: np.ndarray,
    latency_matrix: np.ndarray,
    is_online: np.ndarray,
    packet_loss_rate: float,
    source_idx: int,
    num_validators: int,
    max_hops: int,
    is_attestation: bool,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Simulate message propagation through the P2P network using breadth-first traversal.

    This function uses Numba JIT compilation for high-performance network simulation.
    It models how a message (block or attestation) spreads from a source validator
    through the mesh network, tracking delivery times, paths, and hop counts.

    The propagation follows these rules:
    - Messages only travel along established connections (adjacency_matrix)
    - Validators only propagate if online (is_online array)
    - Each hop adds latency based on the connection (latency_matrix)
    - Packets may be randomly lost based on packet_loss_rate
    - Attestations propagate 30% faster than blocks (smaller size)
    - Maximum hop count limits propagation depth

    Args:
        adjacency_matrix: NxN matrix where 1 indicates a connection between validators
        latency_matrix: NxN matrix of latencies (ms) between connected validators
        is_online: Boolean array indicating which validators are online
        packet_loss_rate: Probability (0-1) that a packet is lost on any hop
        source_idx: Index of the validator originating the message
        num_validators: Total number of validators in the network
        max_hops: Maximum number of hops before stopping propagation
        is_attestation: True for attestations (faster), False for blocks

    Returns:
        Tuple of three arrays:
        - delivery_times: Time (ms) when each validator receives the message (-1 if unreached)
        - senders: Index of the validator who delivered to each recipient (-1 if unreached)
        - hops: Number of hops to reach each validator (0 if unreached)
    """
    delivery_times = np.full(num_validators, -1.0)
    delivery_times[source_idx] = 0.0

    senders = np.full(num_validators, -1, dtype=np.int32)
    senders[source_idx] = source_idx  # Source is its own sender

    hops = np.zeros(num_validators, dtype=np.int32)

    visited = np.zeros(num_validators, dtype=np.bool_)
    visited[source_idx] = True

    current_layer = np.zeros(num_validators, dtype=np.bool_)
    current_layer[source_idx] = True

    for hop in range(max_hops):
        next_layer = np.zeros(num_validators, dtype=np.bool_)

        for sender in range(num_validators):
            if not current_layer[sender]:
                continue

            # Check if sender is online and can propagate
            if not is_online[sender]:
                continue

            sender_time = delivery_times[sender]

            # Check all neighbors
            for receiver in range(num_validators):
                if adjacency_matrix[sender, receiver] == 0:
                    continue
                if visited[receiver]:
                    continue

                # Check if receiver is online (can receive messages)
                if not is_online[receiver]:
                    continue

                # Simulate packet loss
                if np.random.random() < packet_loss_rate:
                    continue

                # Calculate delivery time
                latency = latency_matrix[sender, receiver]
                if is_attestation:
                    latency *= 0.7  # Attestations are smaller, propagate faster

                delivery_time = sender_time + latency
                delivery_times[receiver] = delivery_time
                senders[receiver] = sender
                hops[receiver] = hop + 1
                visited[receiver] = True
                next_layer[receiver] = True

        # Swap layers
        current_layer = next_layer

        # Stop if no more propagation
        if not np.any(next_layer):
            break

    return delivery_times, senders, hops


class GossipSubSimulator:
    """Simulates a GossipSub P2P network for message propagation.

    This class models the libp2p GossipSub protocol, which is used by many
    blockchain networks for efficient message dissemination. It creates a
    mesh topology where validators maintain connections to a subset of peers,
    with additional "lazy" connections for redundancy.

    The simulator handles:
    - Building realistic mesh topologies based on GossipSub parameters
    - Simulating message propagation with latency and packet loss
    - Tracking delivery paths to understand network flow
    - Supporting both block and attestation propagation

    Network topology:
    - Mesh connections: Active bidirectional links for eager push
    - Lazy connections: Metadata-only links for redundancy
    - Latency varies between connections based on geographic distribution
    """

    def __init__(self, config: SimulationConfig, validators: List[str]):
        """Initialize the GossipSub network simulator.

        Args:
            config: Simulation configuration with network parameters
            validators: List of validator IDs to include in the network
        """
        self.config = config
        self.validators = validators
        self.mesh_degree = config.gossipsub_d
        self.mesh_degree_low = config.gossipsub_dlo
        self.mesh_degree_high = config.gossipsub_dhi
        self.lazy_degree = config.gossipsub_dlazy

        # Network topology
        self.mesh_connections: Dict[str, Set[str]] = {}
        self.lazy_connections: Dict[str, Set[str]] = {}

        # Latency matrix (symmetric)
        self.latency_matrix: Dict[Tuple[str, str], float] = {}

        # NumPy arrays for fast propagation
        self.adjacency_matrix: np.ndarray = None
        self.latency_array: np.ndarray = None
        self.validator_to_idx: Dict[str, int] = {v: i for i, v in enumerate(validators)}
        self.idx_to_validator: Dict[int, str] = {i: v for i, v in enumerate(validators)}

        # Validator behavior map (will be set later)
        self.validator_behaviors: Dict[str, any] = {}
        
        # Private/public node tracking
        self.private_nodes: Set[str] = set()
        self.public_nodes: Set[str] = set()

        # Initialize latencies first (doesn't depend on behaviors)
        self._initialize_latencies()

    def set_validator_behaviors(self, validators: Dict[str, any]):
        """Set the validator behavior objects for propagation decisions.

        Args:
            validators: Map of validator ID to ValidatorNode objects
        """
        self.validator_behaviors = validators
        # Now build topology based on behaviors
        self._build_mesh_topology()
        self._build_numpy_arrays()

    def _build_mesh_topology(self):
        """Build the GossipSub mesh topology with target degree connections.

        Creates a mesh network where each validator aims to maintain
        'mesh_degree' bidirectional connections. The actual degree may
        vary between mesh_degree_low and mesh_degree_high based on
        network dynamics. Additionally creates lazy connections for
        redundancy.
        
        Models private nodes (behind NAT) that can only initiate outbound
        connections but cannot accept incoming connections.
        """
        # Determine which nodes are private (behind NAT/firewall) based on validator configuration
        self.private_nodes = set()
        self.public_nodes = set()
        
        for validator in self.validators:
            if validator in self.validator_behaviors:
                validator_node = self.validator_behaviors[validator]
                # Use the is_private status determined during validator initialization
                if validator_node.is_private:
                    self.private_nodes.add(validator)
                else:
                    self.public_nodes.add(validator)
            else:
                # Default to public if no behavior is set
                self.public_nodes.add(validator)
        
        print(f"Network topology: {len(self.public_nodes)} public nodes, {len(self.private_nodes)} private nodes")
        
        # Initialize empty connection sets
        for validator in self.validators:
            self.mesh_connections[validator] = set()
            self.lazy_connections[validator] = set()

        # Phase 1: Public nodes connect to each other
        public_list = list(self.public_nodes)
        for validator in public_list:
            current_connections = len(self.mesh_connections[validator])
            needed_connections = self.mesh_degree - current_connections

            if needed_connections > 0:
                # Public nodes can connect to other public nodes
                potential_peers = [
                    v
                    for v in public_list
                    if v != validator
                    and v not in self.mesh_connections[validator]
                    and len(self.mesh_connections[v]) < self.mesh_degree_high
                ]

                # Randomly select peers to connect to
                if len(potential_peers) >= needed_connections:
                    new_peers = random.sample(potential_peers, needed_connections)
                else:
                    new_peers = potential_peers

                # Create bidirectional connections
                for peer in new_peers:
                    self.mesh_connections[validator].add(peer)
                    self.mesh_connections[peer].add(validator)
        
        # Phase 2: Private nodes initiate connections to public nodes
        for validator in self.private_nodes:
            # Private nodes can only connect out to public nodes
            current_connections = len(self.mesh_connections[validator])
            needed_connections = self.mesh_degree - current_connections
            
            if needed_connections > 0:
                # Can only connect to public nodes that aren't at capacity
                potential_peers = [
                    v
                    for v in public_list
                    if v not in self.mesh_connections[validator]
                    and len(self.mesh_connections[v]) < self.mesh_degree_high
                ]
                
                # Randomly select peers to connect to
                if len(potential_peers) >= needed_connections:
                    new_peers = random.sample(potential_peers, needed_connections)
                else:
                    new_peers = potential_peers
                
                # Create bidirectional connections (private node initiated)
                for peer in new_peers:
                    self.mesh_connections[validator].add(peer)
                    self.mesh_connections[peer].add(validator)
        
        # Report connectivity issues
        isolated_nodes = [v for v in self.validators if len(self.mesh_connections[v]) == 0]
        under_connected = [v for v in self.validators if len(self.mesh_connections[v]) < self.mesh_degree_low]
        
        if isolated_nodes:
            print(f"Warning: {len(isolated_nodes)} isolated nodes (no connections)")
        if under_connected:
            print(f"Warning: {len(under_connected)} under-connected nodes (< {self.mesh_degree_low} connections)")

        # Build lazy connections (for redundancy)
        for validator in self.validators:
            # Find validators not in mesh
            non_mesh_peers = [
                v
                for v in self.validators
                if v != validator and v not in self.mesh_connections[validator]
            ]

            if len(non_mesh_peers) > self.lazy_degree:
                lazy_peers = random.sample(non_mesh_peers, self.lazy_degree)
            else:
                lazy_peers = non_mesh_peers

            self.lazy_connections[validator] = set(lazy_peers)

    def _initialize_latencies(self):
        """Initialize symmetric latency matrix between all validator pairs.

        Latencies are sampled from a normal distribution to model
        geographic distribution of validators. The matrix is symmetric
        since latency is the same in both directions.
        """
        # Create symmetric latency matrix
        for i, v1 in enumerate(self.validators):
            for v2 in self.validators[i:]:
                if v1 == v2:
                    latency = 0.0
                else:
                    # Sample from normal distribution with minimum latency
                    # Physical minimum for network latency (even local network)
                    MIN_NETWORK_LATENCY_MS = 50.0
                    base = self.config.base_latency_ms
                    variance = self.config.latency_variance_ms
                    latency = max(
                        MIN_NETWORK_LATENCY_MS, base + random.gauss(0, variance)
                    )

                self.latency_matrix[(v1, v2)] = latency
                self.latency_matrix[(v2, v1)] = latency

    def get_latency(self, v1: str, v2: str) -> float:
        """Get the network latency between two validators.

        Args:
            v1: First validator ID
            v2: Second validator ID

        Returns:
            Latency in milliseconds
        """
        return self.latency_matrix.get((v1, v2), self.config.base_latency_ms)

    def _build_numpy_arrays(self):
        """Convert network topology to NumPy arrays for Numba acceleration.

        Creates adjacency matrix and latency array that can be used by
        the JIT-compiled propagation function for high performance.
        """
        n = len(self.validators)
        self.adjacency_matrix = np.zeros((n, n), dtype=np.int8)
        self.latency_array = np.zeros((n, n), dtype=np.float32)

        # Build adjacency matrix from mesh connections
        for validator, connections in self.mesh_connections.items():
            v_idx = self.validator_to_idx[validator]
            for connected in connections:
                c_idx = self.validator_to_idx[connected]
                self.adjacency_matrix[v_idx, c_idx] = 1

        # Build latency array
        for i, v1 in enumerate(self.validators):
            for j, v2 in enumerate(self.validators):
                self.latency_array[i, j] = self.get_latency(v1, v2)

    def get_mesh_topology(self) -> Dict[str, Set[str]]:
        """Get the current mesh connections for network analysis.

        Returns:
            Dictionary mapping each validator to their set of mesh peers
        """
        return self.mesh_connections.copy()

    def get_full_topology(self) -> Dict[str, Set[str]]:
        """Get the complete network topology including lazy connections.

        Returns:
            Dictionary mapping each validator to all their connections
            (both mesh and lazy)
        """
        full_topology = {}
        for validator in self.validators:
            full_topology[validator] = self.mesh_connections.get(
                validator, set()
            ) | self.lazy_connections.get(validator, set())
        return full_topology

    def propagate_attestation(
        self, attester: str, attestation: Attestation
    ) -> PropagationTrace:
        """Simulate attestation propagation through the P2P network.

        Attestations are smaller than blocks and propagate 30% faster.
        The function tracks the full propagation path, including which
        validator delivered the attestation to each recipient.

        Args:
            attester: ID of the validator creating the attestation
            attestation: The attestation object to propagate

        Returns:
            PropagationTrace containing delivery details for all reached validators
        """
        trace = PropagationTrace()

        # Get attester index
        attester_idx = self.validator_to_idx[attester]

        # Collect online status from validators
        is_online = np.ones(len(self.validators), dtype=np.bool_)
        for i, validator_id in enumerate(self.validators):
            if validator_id in self.validator_behaviors:
                is_online[i] = self.validator_behaviors[validator_id].is_online
            # else: default to online if no behavior set

        # Use fast Numba propagation
        delivery_times, sender_indices, hop_counts = propagate_message_fast(
            self.adjacency_matrix,
            self.latency_array,
            is_online,
            self.config.packet_loss_rate,
            attester_idx,
            len(self.validators),
            max_hops=8,
            is_attestation=True,
        )

        # Convert results to PropagationTrace
        for idx, delivery_time in enumerate(delivery_times):
            if delivery_time > 0:  # Skip source and unreached nodes
                receiver = self.idx_to_validator[idx]
                sender_idx = sender_indices[idx]
                sender = self.idx_to_validator[sender_idx]
                hop = hop_counts[idx]
                trace.record_delivery(receiver, delivery_time, hop, sender)

        return trace

    def propagate_block_proposal(self, proposer: str, block: Block) -> PropagationTrace:
        """Simulate block propagation through the P2P network.

        Blocks are larger than attestations and propagate at full latency.
        The function tracks the full propagation path and also handles
        lazy push for metadata dissemination.

        Args:
            proposer: ID of the validator proposing the block
            block: The block object to propagate

        Returns:
            PropagationTrace containing delivery details for all reached validators
        """
        trace = PropagationTrace()

        # Get proposer index
        proposer_idx = self.validator_to_idx[proposer]

        # Collect online status from validators
        is_online = np.ones(len(self.validators), dtype=np.bool_)
        for i, validator_id in enumerate(self.validators):
            if validator_id in self.validator_behaviors:
                is_online[i] = self.validator_behaviors[validator_id].is_online
            # else: default to online if no behavior set

        # Use fast Numba propagation
        delivery_times, sender_indices, hop_counts = propagate_message_fast(
            self.adjacency_matrix,
            self.latency_array,
            is_online,
            self.config.packet_loss_rate,
            proposer_idx,
            len(self.validators),
            max_hops=10,
            is_attestation=False,
        )

        # Convert results to PropagationTrace
        for idx, delivery_time in enumerate(delivery_times):
            if delivery_time > 0:  # Skip source and unreached nodes
                receiver = self.idx_to_validator[idx]
                sender_idx = sender_indices[idx]
                sender = self.idx_to_validator[sender_idx]
                hop = hop_counts[idx]
                trace.record_delivery(receiver, delivery_time, hop, sender)

        # Lazy push for redundancy (metadata only, not included in main propagation)
        self._lazy_push(proposer, block, trace)

        return trace

    def _lazy_push(self, proposer: str, block: Block, trace: PropagationTrace):
        """Handle lazy push of block metadata to non-mesh peers.

        In GossipSub, lazy connections receive metadata about messages
        but not the full content. Recipients can request the full message
        if needed. This provides redundancy without the overhead of
        eager push to all peers.

        Args:
            proposer: ID of the block proposer
            block: The block being propagated
            trace: PropagationTrace (not modified by lazy push)
        """
        # Lazy connections get metadata about the block
        # In real GossipSub, they would request the block if needed
        # For simulation, we'll just note these connections exist
        lazy_peers = self.lazy_connections.get(proposer, set())
        for peer in lazy_peers:
            if random.random() >= self.config.packet_loss_rate:
                # Lazy push has higher latency
                latency = self.get_latency(proposer, peer) * 1.5
                # Don't record in main trace as it's metadata only
                pass
