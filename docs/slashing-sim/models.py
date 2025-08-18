from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime
from enum import Enum, auto
import hashlib
import random


class BehaviorProfile(Enum):
    """Defines the three validator behavior profiles used in the simulation.

    Each profile represents a different type of validator behavior:
    - HONEST: Professional operators with good uptime and responsiveness
    - LAZY: Amateur operators with poor configurations or connectivity
    - BYZANTINE: Malicious or completely offline validators
    """

    HONEST = auto()
    LAZY = auto()
    BYZANTINE = auto()


@dataclass
class EpochConfig:
    """Configuration for epoch and slot timing parameters.

    This class defines the fundamental timing constants for the Aztec consensus protocol,
    including the relationship between Aztec slots and Ethereum slots, and the various
    deadlines for attestation collection and L1 submission.

    Key timing relationships:
    - 1 Aztec slot = 3 Ethereum slots = 36 seconds
    - Attestations must be collected within 18 seconds
    - L1 submission must occur before the 24 second mark
    """

    slots_per_epoch: int = 4  # Reduced from 32 for faster testing
    committee_size: int = 48
    aztec_slot_duration_seconds: int = 36  # Aztec slot = 36 seconds
    ethereum_slot_duration_seconds: int = 12  # Ethereum slot = 12 seconds
    ethereum_slots_per_aztec: int = 3  # 36/12 = 3
    attestation_collection_window_seconds: int = (
        18  # Time to collect attestations before L1 submission
    )
    l1_submission_deadline_seconds: int = (
        24  # Must submit by end of second Ethereum slot
    )


@dataclass
class Committee:
    """Represents the validator committee for a specific epoch.

    In each epoch, a subset of validators is randomly selected to form the committee.
    The committee is responsible for proposing blocks and attesting to them.
    Each slot in the epoch has a designated proposer from the committee.

    Attributes:
        epoch: The epoch number this committee is for
        validators: List of 48 randomly selected validator IDs
        proposer_schedule: Mapping from slot number to the designated proposer
    """

    epoch: int
    validators: List[str]  # 48 randomly selected validators
    proposer_schedule: Dict[int, str]  # slot -> proposer mapping


@dataclass
class Block:
    """Represents a block in the Aztec blockchain.

    Each block contains transactions and is proposed by a designated validator
    during their assigned slot. The block hash is automatically computed from
    the block's content to ensure uniqueness and integrity.

    Attributes:
        slot: The slot number when this block was proposed
        proposer: Validator ID of the block proposer
        parent_hash: Hash of the previous block
        transactions: Number of transactions included
        timestamp: When the block was created
        hash: Auto-generated unique identifier (computed in __post_init__)
    """

    slot: int
    proposer: str
    parent_hash: str
    transactions: int
    timestamp: datetime
    hash: str = field(init=False)

    def __post_init__(self):
        """Generate a unique hash for this block based on its content."""
        content = f"{self.slot}{self.proposer}{self.parent_hash}{self.transactions}{self.timestamp}"
        self.hash = hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class Attestation:
    """Represents a validator's attestation to a specific block.

    Attestations are votes that validators cast to confirm they have seen
    and agree with a proposed block. These are critical for achieving
    consensus - a block needs 33/48 attestations to be submitted to L1.

    Attributes:
        validator: ID of the validator creating this attestation
        slot: The slot number being attested to
        block_hash: Hash of the block being attested
        received_at: When this attestation was received
        propagation_delay_ms: Network delay in receiving this attestation
        signature: Auto-generated unique signature (computed in __post_init__)
    """

    validator: str
    slot: int
    block_hash: str
    received_at: datetime
    propagation_delay_ms: float
    signature: str = field(init=False)

    def __post_init__(self):
        """Generate a unique signature for this attestation."""
        content = f"{self.validator}{self.slot}{self.block_hash}"
        self.signature = hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class NodeView:
    """Represents what a single node sees at a given point in time"""

    node_id: str
    slot: int

    # P2P layer observations
    blocks_p2p: Dict[int, Block] = field(default_factory=dict)  # slot -> block
    attestations_p2p: Dict[str, Set[str]] = field(
        default_factory=dict
    )  # block_hash -> set of validator signatures

    # L1 layer observations (what was posted to Ethereum)
    blocks_l1: Dict[int, Block] = field(default_factory=dict)  # slot -> block
    attestations_l1: Dict[str, Set[str]] = field(
        default_factory=dict
    )  # block_hash -> set of validator signatures

    # Combined view
    def get_all_blocks(self) -> Dict[int, Block]:
        """Get all blocks seen from both P2P and L1"""
        all_blocks = self.blocks_p2p.copy()
        all_blocks.update(self.blocks_l1)
        return all_blocks

    def get_all_attestations(self, block_hash: str) -> Set[str]:
        """Get all attestations for a block from both P2P and L1"""
        p2p_sigs = self.attestations_p2p.get(block_hash, set())
        l1_sigs = self.attestations_l1.get(block_hash, set())
        return p2p_sigs.union(l1_sigs)

    def add_block_p2p(self, block: Block):
        """Record block received via P2P"""
        self.blocks_p2p[block.slot] = block
        if block.hash not in self.attestations_p2p:
            self.attestations_p2p[block.hash] = set()

    def add_attestation_p2p(self, attestation: Attestation):
        """Record attestation received via P2P"""
        if attestation.block_hash not in self.attestations_p2p:
            self.attestations_p2p[attestation.block_hash] = set()
        self.attestations_p2p[attestation.block_hash].add(attestation.signature)

    def add_block_l1(self, block: Block, attestations: List[Attestation]):
        """Record block and attestations observed on L1"""
        self.blocks_l1[block.slot] = block
        if block.hash not in self.attestations_l1:
            self.attestations_l1[block.hash] = set()

        # Add all attestations that came with the L1 submission
        for att in attestations:
            self.attestations_l1[block.hash].add(att.signature)

    def has_block_reached_finality_p2p(
        self, block_hash: str, required: int = None
    ) -> bool:
        """Check if block has enough attestations from P2P view

        Args:
            block_hash: Hash of the block to check
            required: Number of attestations required (default: 2/3 + 1 of committee)
        """
        # If not specified, use default 2/3 + 1 of 48 (historical default)
        if required is None:
            required = 33
        return len(self.attestations_p2p.get(block_hash, set())) >= required

    def has_block_on_l1(self, block_hash: str) -> bool:
        """Check if block has been posted to L1"""
        return any(b.hash == block_hash for b in self.blocks_l1.values())


@dataclass
class L1Submission:
    """Represents a block submission to Ethereum L1"""

    slot: int
    block: Block
    attestations: List[Attestation]
    submission_time_ms: float  # Time when submitted to L1
    inclusion_time_ms: float  # Time when included in L1 block
    ethereum_slot: int  # Which Ethereum slot it landed in
    success: bool  # Whether it made it before deadline

    def attestation_count(self) -> int:
        return len(self.attestations)


@dataclass
class SlotData:
    """Aggregated data for a single slot in the simulation.

    This class collects all the important information about what happened
    during a specific slot, including whether a block was proposed,
    how many attestations were received, and the overall participation rate.

    Attributes:
        slot_number: The slot index
        epoch: Which epoch this slot belongs to
        proposer: ID of the designated proposer for this slot
        block_proposed: Whether the proposer actually created a block
        block: The block object if one was proposed
        attestations: List of all attestations received
        committee_members: List of all committee members for this epoch
        timestamp: When this slot started
    """

    slot_number: int
    epoch: int
    proposer: str
    block_proposed: bool
    block: Optional[Block]
    attestations: List[Attestation]
    committee_members: List[str]
    timestamp: datetime

    @property
    def participation_rate(self) -> float:
        """Calculate the percentage of committee members who attested.

        Returns:
            Float between 0.0 and 1.0 representing the participation rate.
            Returns 0.0 if no block was proposed.
        """
        if not self.block_proposed:
            return 0.0
        expected = len(self.committee_members) - 1  # Minus proposer
        if expected == 0:
            return 0.0
        return len(self.attestations) / expected


@dataclass
class ValidatorPerformance:
    """Tracks performance metrics for an individual validator.

    This class accumulates statistics about a validator's behavior throughout
    the simulation, including their success rates for both proposing blocks
    and creating attestations, as well as their average response times.

    Attributes:
        validator_id: Unique identifier for the validator
        total_slots_as_proposer: Number of times selected as proposer
        successful_proposals: Number of blocks successfully proposed
        missed_proposals: Number of times failed to propose when selected
        total_slots_as_attester: Number of slots where attestation was expected
        successful_attestations: Number of attestations successfully created
        missed_attestations: Number of attestations missed
        total_attestation_delay_ms: Cumulative delay for all attestations
    """

    validator_id: str
    total_slots_as_proposer: int = 0
    successful_proposals: int = 0
    missed_proposals: int = 0
    total_slots_as_attester: int = 0
    successful_attestations: int = 0
    missed_attestations: int = 0
    total_attestation_delay_ms: float = 0.0

    @property
    def proposal_success_rate(self) -> float:
        if self.total_slots_as_proposer == 0:
            return 0.0
        return self.successful_proposals / self.total_slots_as_proposer

    @property
    def attestation_success_rate(self) -> float:
        if self.total_slots_as_attester == 0:
            return 0.0
        return self.successful_attestations / self.total_slots_as_attester

    @property
    def average_attestation_delay_ms(self) -> float:
        if self.successful_attestations == 0:
            return 0.0
        return self.total_attestation_delay_ms / self.successful_attestations


@dataclass
class NetworkSnapshot:
    """Captures the state of the P2P network at a specific point in time.

    This class is used to record network health metrics during the simulation,
    allowing analysis of how network conditions affect consensus performance.

    Attributes:
        timestamp: When this snapshot was taken
        active_validators: Number of validators currently online
        mesh_connections: Map of validator IDs to their peer connection counts
        average_latency_ms: Mean network latency across all connections
        packet_loss_rate: Current packet loss rate (0.0 to 1.0)
    """

    timestamp: datetime
    active_validators: int
    mesh_connections: Dict[str, int]  # validator -> connection count
    average_latency_ms: float
    packet_loss_rate: float


@dataclass
class PropagationTrace:
    """Tracks the propagation path of messages (blocks/attestations) through the P2P network.

    This class records how a message spreads from its original creator through the network,
    tracking each delivery with details about:
    - Who received the message (validator)
    - When they received it (time_ms relative to creation)
    - How many hops it took to reach them (network distance)
    - Who delivered it to them (sender - the intermediary node)

    For example, if validator A creates an attestation that reaches C via B:
    - A creates attestation at t=0
    - B receives from A at t=50ms (hop=1, sender=A)
    - C receives from B at t=100ms (hop=2, sender=B)

    This allows us to reconstruct the full propagation path and understand
    network topology effects on message dissemination.
    """

    deliveries: List[tuple[str, float, int, str]] = field(
        default_factory=list
    )  # (receiver, time_ms, hop, sender)

    def record_delivery(self, receiver: str, time_ms: float, hop: int, sender: str):
        self.deliveries.append((receiver, time_ms, hop, sender))

    def get_delivery_time(self, validator: str) -> Optional[float]:
        for v, time, _, _ in self.deliveries:
            if v == validator:
                return time
        return None

    def get_delivery_info(self, validator: str) -> Optional[tuple[float, int, str]]:
        """Get full delivery info for a validator: (time_ms, hop, sender)"""
        for v, time, hop, sender in self.deliveries:
            if v == validator:
                return (time, hop, sender)
        return None


@dataclass
class SimulationConfig:
    """Master configuration for the entire simulation.

    This class contains all the parameters that control the simulation behavior,
    including network size, validator behavior distributions, timing parameters,
    and network conditions. It provides sensible defaults that can be overridden
    for different test scenarios.

    The configuration is divided into several categories:
    - Network topology (validator count, committee size)
    - Timing parameters (slot duration, deadlines)
    - GossipSub P2P parameters
    - Network conditions (latency, packet loss)
    - Validator behavior distributions and parameters
    - Simulation control (epochs to run, random seed)
    """

    # Network size
    total_validators: int = 1000
    committee_size: int = 48  # Number of validators in each epoch's committee

    # Epoch and slot configuration
    slots_per_epoch: int = 4  # Number of slots in each epoch
    aztec_slot_duration_seconds: int = 36  # Duration of each Aztec slot in seconds

    # GossipSub parameters
    gossipsub_d: int = 8
    gossipsub_dlo: int = 6
    gossipsub_dhi: int = 12
    gossipsub_dlazy: int = 6

    # Network conditions
    # Note: Minimum network latency of 50ms is enforced (even for local networks)
    base_latency_ms: float = 50
    latency_variance_ms: float = 20
    packet_loss_rate: float = 0.001

    # Validator behavior distribution
    honest_ratio: float = 0.85
    lazy_ratio: float = 0.10
    byzantine_ratio: float = 0.05

    # Behavior parameters for each type
    honest_proposal_rate: float = 0.99
    honest_attestation_rate: float = 0.98
    honest_downtime_prob: float = 0.001
    honest_recovery_prob: float = 0.9  # 90% chance to recover when down
    honest_private_peer_prob: float = 0.05  # 5% of honest validators behind NAT/firewall

    lazy_proposal_rate: float = 0.30  # Often miss their proposal slots
    lazy_attestation_rate: float = 0.20  # Rarely attest (port issues, offline, etc)
    lazy_downtime_prob: float = 0.15  # 15% chance of going offline per slot
    lazy_recovery_prob: float = 0.3  # 30% chance to recover when down
    lazy_private_peer_prob: float = 0.4  # 40% of lazy validators behind NAT/firewall

    byzantine_proposal_rate: float = 0.10  # Almost never propose
    byzantine_attestation_rate: float = 0.05  # Almost never attest
    byzantine_downtime_prob: float = 0.25  # Often offline
    byzantine_recovery_prob: float = 0.05  # 5% chance to recover when down
    byzantine_private_peer_prob: float = 0.6  # 60% of byzantine validators behind NAT/firewall

    # Attestation timing parameters (in milliseconds)
    # Note: Minimum baseline of 100ms is enforced for physical processing time
    attestation_delay_mean: float = 1000  # Mean time to create attestation
    attestation_delay_std: float = 500  # Std deviation for attestation creation

    # Validator response time parameters (in milliseconds)
    # Note: Minimum response delay of 50ms is enforced for network/processing overhead
    honest_response_mean: float = 500  # How quickly honest validators respond
    honest_response_std: float = 100
    lazy_response_mean: float = 3000  # Lazy validators are slower
    lazy_response_std: float = 1500
    byzantine_response_mean: float = 15000  # Byzantine validators barely respond
    byzantine_response_std: float = 5000

    # Simulation parameters
    epochs_to_simulate: int = 10
    random_seed: int = 42
    # L1 submission timing
    l1_submission_deadline_ms: float = 18000  # 18 seconds to submit to L1

    # Block content simulation
    avg_txs_per_block: int = 100
    tx_size_bytes: int = 2048
    block_propagation_strategy: str = "eager_lazy"

    def validate(self):
        """Validate that all configuration parameters are consistent and valid.

        Checks:
        - Behavior ratios sum to 1.0
        - Committee size doesn't exceed total validators
        - GossipSub parameters are within valid ranges
        - Timing parameters make sense

        Raises:
            AssertionError: If any validation check fails
        """
        assert (
            abs(self.honest_ratio + self.lazy_ratio + self.byzantine_ratio - 1.0)
            < 0.001
        ), "Behavior ratios must sum to 1.0"
        assert (
            self.committee_size <= self.total_validators
        ), f"Total validators ({self.total_validators}) must be at least committee size ({self.committee_size})"
        assert self.committee_size >= 1, "Committee size must be at least 1"
        assert (
            self.gossipsub_dlo <= self.gossipsub_d <= self.gossipsub_dhi
        ), "GossipSub parameters must satisfy: dlo <= d <= dhi"
        assert self.slots_per_epoch >= 1, "Must have at least 1 slot per epoch"
        assert (
            self.aztec_slot_duration_seconds >= 12
        ), "Aztec slot duration must be at least 12 seconds (1 Ethereum slot)"
