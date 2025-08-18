"""
Simulator class that encapsulates simulation state and provides access to internal components.
This allows for network analysis, partition detection, and other advanced features.
"""

from typing import Optional, Dict, List, Tuple, Set
import polars as pl
import numpy as np
import networkx as nx
# Removed scipy - using NetworkX for all partition detection

from models import SimulationConfig, BehaviorProfile, EpochConfig
from collector import EventCollector
from committee import CommitteeManager
from validator import ValidatorNode
from network import GossipSubSimulator
from view_events import create_event_dataframe


class AztecSimulator:
    """
    Main simulator class that manages the simulation state and provides
    access to network topology and partition analysis.
    """

    def __init__(self, config: Optional[SimulationConfig] = None):
        """
        Initialize the simulator with configuration.

        Args:
            config: SimulationConfig object. If None, uses default configuration.
        """
        # Use default config if none provided
        if config is None:
            config = SimulationConfig(
                total_validators=50,
                epochs_to_simulate=1,
                honest_ratio=0.7,
                lazy_ratio=0.2,
                byzantine_ratio=0.1,
                random_seed=42,
            )

        self.config = config

        # Setup epoch configuration
        self.epoch_config = EpochConfig()
        self.epoch_config.slots_per_epoch = config.slots_per_epoch
        self.epoch_config.aztec_slot_duration_seconds = (
            config.aztec_slot_duration_seconds
        )
        self.epoch_config.committee_size = config.committee_size

        # Initialize components
        self.committee_manager = CommitteeManager(self.epoch_config, config.random_seed)
        self.collector = EventCollector(self.epoch_config, config)

        # Create validators
        self.validators = self._create_validators()
        self.validator_ids = list(self.validators.keys())

        # Setup network
        self.network = GossipSubSimulator(config, self.validator_ids)
        self.network.set_validator_behaviors(self.validators)

        # Track current state
        self.current_epoch = 0
        self.current_slot = 0
        self.current_committee = None
        self.simulation_complete = False

        # Store results
        self.df = None

    def _create_validators(self) -> Dict[str, ValidatorNode]:
        """Create validators based on behavior ratios."""
        validators = {}
        idx = 0

        # Honest validators
        for _ in range(int(self.config.total_validators * self.config.honest_ratio)):
            vid = f"validator_{idx:04d}"
            validators[vid] = ValidatorNode(
                vid, BehaviorProfile.HONEST, self.config.random_seed + idx, self.config
            )
            idx += 1

        # Lazy validators
        for _ in range(int(self.config.total_validators * self.config.lazy_ratio)):
            vid = f"validator_{idx:04d}"
            validators[vid] = ValidatorNode(
                vid, BehaviorProfile.LAZY, self.config.random_seed + idx, self.config
            )
            idx += 1

        # Byzantine validators (remainder)
        for _ in range(self.config.total_validators - idx):
            vid = f"validator_{idx:04d}"
            validators[vid] = ValidatorNode(
                vid,
                BehaviorProfile.BYZANTINE,
                self.config.random_seed + idx,
                self.config,
            )
            idx += 1

        return validators

    def run(self) -> pl.DataFrame:
        """
        Run the complete simulation.

        Returns:
            DataFrame containing all simulation events with derived fields
        """
        # Start simulation
        self.collector.record_simulation_start(self.config)

        # Run epochs
        for epoch in range(self.config.epochs_to_simulate):
            self.current_epoch = epoch
            self.collector.record_epoch_start(epoch)

            # Draw committee ONCE per epoch
            self.current_committee = self.committee_manager.draw_committee(
                epoch, self.validator_ids
            )
            self.collector.record_committee_selection(
                epoch, self.current_committee, self.validators
            )

            # Run each slot in the epoch
            for slot in range(self.config.slots_per_epoch):
                absolute_slot = epoch * self.config.slots_per_epoch + slot
                self.current_slot = absolute_slot

                # Record proposer assignment for this slot
                self.collector.record_proposer_assignment(
                    absolute_slot, self.current_committee
                )

                # Run the slot
                self.collector.record_slot(
                    absolute_slot, self.current_committee, self.validators, self.network
                )

        # End simulation
        self.collector.record_simulation_end()
        self.simulation_complete = True

        # Convert events to DataFrame
        self.df = create_event_dataframe(self.collector.event_store)

        print(f"✅ Simulation complete! {len(self.df)} events recorded")
        print(f"  Epochs simulated: {self.config.epochs_to_simulate}")
        print(f"  Slots per epoch: {self.config.slots_per_epoch}")
        print(
            f"  Total slots: {self.config.epochs_to_simulate * self.config.slots_per_epoch}"
        )
        print(
            f"  Validators: {self.config.total_validators} "
            f"(Honest: {self.config.honest_ratio:.0%}, "
            f"Lazy: {self.config.lazy_ratio:.0%}, "
            f"Byzantine: {self.config.byzantine_ratio:.0%})"
        )

        return self.df

    def get_network_state_at_slot(self, slot: int) -> Dict:
        """
        Get the network state at a specific slot, including online status.

        Args:
            slot: The slot number to analyze

        Returns:
            Dictionary containing:
            - adjacency_matrix: Network connectivity matrix
            - online_validators: Boolean array of online status
            - validator_names: List of validator names in matrix order
        """
        if not self.simulation_complete:
            raise RuntimeError(
                "Simulation must be completed before analyzing network state"
            )

        # Get online status from events up to this slot
        online = np.ones(len(self.validator_ids), dtype=bool)

        # Filter events up to and including this slot
        slot_events = self.df.filter(pl.col("slot") <= slot)

        # Process online/offline events
        for row in slot_events.filter(
            pl.col("event").is_in(["NODE_OFFLINE", "NODE_ONLINE"])
        ).iter_rows(named=True):
            validator = row["actor"]
            if validator in self.network.validator_to_idx:
                idx = self.network.validator_to_idx[validator]
                online[idx] = row["event"] == "NODE_ONLINE"

        return {
            "adjacency_matrix": self.network.adjacency_matrix.copy(),
            "online_validators": online,
            "validator_names": self.validator_ids,
            "slot": slot,
        }

    def detect_partitions_at_slot(self, slot: int) -> Dict:
        """
        Detect network partitions at a specific slot using NetworkX.
        This is now a wrapper around detect_partitions_networkx for compatibility.

        Args:
            slot: The slot number to analyze

        Returns:
            Dictionary containing partition information
        """
        # Use NetworkX implementation for everything
        detailed = self.detect_partitions_networkx(slot)
        
        # Extract simplified info for backward compatibility
        partition_sizes = [p["size"] for p in detailed["partitions"]]
        partition_list = [set(p["validators"]) for p in detailed["partitions"]]
        
        state = self.get_network_state_at_slot(slot)
        total_online = int(state["online_validators"].sum())
        total_offline = int((~state["online_validators"]).sum())
        
        return {
            "is_partitioned": detailed["is_partitioned"],
            "num_partitions": detailed["num_partitions"],
            "partition_sizes": partition_sizes,
            "partitions": partition_list,
            "largest_partition_fraction": (
                max(partition_sizes) / total_online if partition_sizes and total_online > 0 else 0
            ),
            "total_online": total_online,
            "total_offline": total_offline,
        }

    def detect_partitions_networkx(self, slot: int) -> Dict:
        """
        Alternative partition detection using NetworkX for more detailed analysis.

        Args:
            slot: The slot number to analyze

        Returns:
            Dictionary with detailed partition information
        """
        state = self.get_network_state_at_slot(slot)

        # Create NetworkX graph
        G = nx.Graph()

        # Add only online validators
        online_indices = np.where(state["online_validators"])[0]
        for idx in online_indices:
            G.add_node(state["validator_names"][idx], index=idx)

        # Add edges between online validators
        adjacency = state["adjacency_matrix"]
        online = state["online_validators"]

        for i in online_indices:
            for j in online_indices:
                if i < j and adjacency[i, j] == 1:
                    G.add_edge(state["validator_names"][i], state["validator_names"][j])

        # Find connected components
        components = list(nx.connected_components(G))

        # Analyze each partition
        partition_details = []
        for component in components:
            # Calculate partition metrics
            subgraph = G.subgraph(component)

            partition_info = {
                "validators": list(component),
                "size": len(component),
                "fraction": len(component) / state["online_validators"].sum(),
                "density": nx.density(subgraph) if len(component) > 1 else 0,
                "avg_degree": (
                    np.mean([d for _, d in subgraph.degree()])
                    if len(component) > 0
                    else 0
                ),
            }

            # Check if committee members are in this partition
            if self.current_committee:
                committee_in_partition = [
                    v for v in component if v in self.current_committee.validators
                ]
                partition_info["committee_members"] = len(committee_in_partition)
                partition_info["committee_fraction"] = len(
                    committee_in_partition
                ) / len(self.current_committee.validators)

            partition_details.append(partition_info)

        # Sort by size (largest first)
        partition_details.sort(key=lambda x: x["size"], reverse=True)

        return {
            "is_partitioned": len(components) > 1,
            "num_partitions": len(components),
            "partitions": partition_details,
            "graph_stats": {
                "total_nodes": G.number_of_nodes(),
                "total_edges": G.number_of_edges(),
                "average_degree": (
                    np.mean([d for _, d in G.degree()])
                    if G.number_of_nodes() > 0
                    else 0
                ),
            },
        }

    def analyze_partition_impact(self, slot: int) -> Dict:
        """
        Analyze the impact of network partitions on consensus.

        Args:
            slot: The slot number to analyze

        Returns:
            Dictionary with partition impact analysis
        """
        partitions = self.detect_partitions_networkx(slot)

        if not partitions["is_partitioned"]:
            return {"can_reach_consensus": True, "reason": "Network is not partitioned"}

        # Check if any partition has enough committee members for consensus
        consensus_threshold = (self.config.committee_size * 2 // 3) + 1

        results = {
            "is_partitioned": True,
            "num_partitions": partitions["num_partitions"],
            "consensus_threshold": consensus_threshold,
            "partitions_analysis": [],
        }

        can_reach_consensus = False
        for partition in partitions["partitions"]:
            partition_analysis = {
                "size": partition["size"],
                "committee_members": partition.get("committee_members", 0),
                "can_reach_consensus": partition.get("committee_members", 0)
                >= consensus_threshold,
            }

            if partition_analysis["can_reach_consensus"]:
                can_reach_consensus = True

            results["partitions_analysis"].append(partition_analysis)

        results["can_reach_consensus"] = can_reach_consensus
        results["reason"] = (
            "At least one partition has enough committee members for consensus"
            if can_reach_consensus
            else f"No partition has {consensus_threshold} committee members needed for consensus"
        )

        return results

    def get_partition_timeline(self) -> pl.DataFrame:
        """
        Analyze network partitions across all slots in the simulation.

        Returns:
            DataFrame with partition information for each slot
        """
        if not self.simulation_complete:
            raise RuntimeError(
                "Simulation must be completed before analyzing partitions"
            )

        timeline_data = []
        total_slots = self.config.epochs_to_simulate * self.config.slots_per_epoch

        for slot in range(total_slots):
            # Use NetworkX directly to avoid duplicate detection
            detailed_info = self.detect_partitions_networkx(slot)
            
            # Extract the info we need for timeline
            state = self.get_network_state_at_slot(slot)
            partition_sizes = [p["size"] for p in detailed_info["partitions"]]
            
            # Check consensus impact
            consensus_threshold = (self.config.committee_size * 2 // 3) + 1
            can_reach_consensus = any(
                p.get("committee_members", 0) >= consensus_threshold 
                for p in detailed_info["partitions"]
            ) if detailed_info["is_partitioned"] else True

            timeline_data.append(
                {
                    "slot": slot,
                    "epoch": slot // self.config.slots_per_epoch,
                    "is_partitioned": detailed_info["is_partitioned"],
                    "num_partitions": detailed_info["num_partitions"],
                    "largest_partition_size": (
                        max(partition_sizes) if partition_sizes else 0
                    ),
                    "largest_partition_fraction": (
                        max(partition_sizes) / state["online_validators"].sum() 
                        if partition_sizes and state["online_validators"].sum() > 0 else 0
                    ),
                    "total_online": int(state["online_validators"].sum()),
                    "total_offline": int((~state["online_validators"]).sum()),
                    "can_reach_consensus": can_reach_consensus,
                }
            )

        return pl.DataFrame(timeline_data)
