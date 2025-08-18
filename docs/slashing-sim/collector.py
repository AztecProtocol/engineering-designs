"""
Event-based data collector - records only events, all other data is derived
"""

import random
import numpy as np
from typing import Dict, Optional, List
from datetime import datetime

try:
    from .events import EventStore, Event, EventType
    from .models import Committee, Block, Attestation, BehaviorProfile
    from .network import GossipSubSimulator
    from .validator import ValidatorNode
except ImportError:
    from events import EventStore, Event, EventType
    from models import Committee, Block, Attestation, BehaviorProfile
    from network import GossipSubSimulator
    from validator import ValidatorNode


class EventCollector:
    """Central event collection system for the simulation.

    The EventCollector is responsible for recording all events that occur
    during the simulation into a centralized EventStore. It handles:

    - Simulation lifecycle events (start, epochs, slots)
    - Committee and proposer assignments
    - Block proposals and propagation
    - Attestation creation and dissemination
    - L1 submission attempts and outcomes
    - Network events and validator status changes

    The collector uses an event-sourced architecture where events are the
    single source of truth. All analysis and visualization is derived from
    these events, ensuring consistency and reproducibility.

    Key design principles:
    - Events are immutable once recorded
    - Timestamps are absolute from simulation start
    - Post-processing determines L1 submission timing
    - Batch operations for performance with large validator sets
    """

    def __init__(self, epoch_config, simulation_config=None):
        """Initialize the event collector.

        Args:
            epoch_config: Configuration for epochs and slots
            simulation_config: Optional simulation configuration
        """
        self.epoch_config = epoch_config
        self.simulation_config = simulation_config
        self.event_store = EventStore()
        self.last_block_hash = "genesis"
        self.simulation_start_ms = 0.0
        self.current_time_ms = 0.0

    def record_simulation_start(self, config):
        """Record the start of a simulation run.

        Captures the initial configuration for reproducibility.

        Args:
            config: SimulationConfig object with all parameters
        """
        self.event_store.add_event(
            Event(
                timestamp_ms=0,
                slot=0,
                event_type=EventType.SIMULATION_START,
                data={
                    "total_validators": config.total_validators,
                    "epochs": config.epochs_to_simulate,
                    "config": config.__dict__,
                },
            )
        )

    def record_epoch_start(self, epoch: int):
        """Record the beginning of a new epoch.

        Args:
            epoch: The epoch number starting
        """
        self.event_store.add_event(
            Event(
                timestamp_ms=self.current_time_ms,
                slot=epoch * self.epoch_config.slots_per_epoch,
                event_type=EventType.EPOCH_START,
                data={"epoch": epoch},
            )
        )

    def record_committee_selection(
        self, epoch: int, committee: Committee, validators: Dict[str, ValidatorNode]
    ):
        """Record the committee selection for an epoch.

        Captures which validators were selected for the committee and
        their behavior profiles for analysis.

        Args:
            epoch: The epoch number
            committee: The selected committee
            validators: Map of all validators for behavior lookup
        """
        # Record committee selection at the start of the epoch
        validator_behaviors = {
            vid: validators[vid].profile.name for vid in committee.validators
        }

        self.event_store.add_event(
            Event(
                timestamp_ms=self.current_time_ms,
                slot=epoch * self.epoch_config.slots_per_epoch,  # First slot of epoch
                event_type=EventType.COMMITTEE_SELECTED,
                data={
                    "epoch": epoch,
                    "committee": committee.validators,
                    "committee_size": len(committee.validators),
                    "validator_behaviors": validator_behaviors,
                },
            )
        )

    def record_proposer_assignment(self, slot: int, committee: Committee):
        """Record which validator is assigned as proposer for a slot.

        Args:
            slot: The slot number
            committee: The committee containing proposer schedule
        """
        # Get proposer for this slot from the committee's schedule
        proposer = committee.proposer_schedule[slot]

        # Calculate time for this slot
        slot_start_ms = slot * self.epoch_config.aztec_slot_duration_seconds * 1000

        self.event_store.add_event(
            Event(
                timestamp_ms=slot_start_ms,
                slot=slot,
                event_type=EventType.PROPOSER_ASSIGNED,
                subject=proposer,
                data={"proposer": proposer, "slot": slot},
            )
        )

    def record_slot(
        self,
        slot: int,
        committee: Committee,
        validators: Dict[str, ValidatorNode],
        network: GossipSubSimulator,
    ):
        """Record all events that occur during a single consensus slot.

        This is the main simulation method that orchestrates a complete slot:

        Phase 1: Block Proposal (t=0)
        - Proposer decides whether to propose
        - Block is created and propagated via P2P
        - Other validators receive the block with network delays

        Phase 2: Attestation Collection (t=100ms to 18s)
        - Validators who received the block create attestations
        - Attestations propagate through the network
        - Proposer collects attestations from peers

        Phase 3: L1 Submission (post-processed)
        - Analyzes when proposer reaches 33 attestations
        - Determines if submission meets deadline
        - Records success or failure

        The method uses batching for performance with large validator sets
        and tracks full propagation paths for network analysis.

        Args:
            slot: The slot number being simulated
            committee: The committee for this epoch
            validators: Map of all validator nodes
            network: The P2P network simulator
        """
        # Calculate absolute time for this slot
        slot_start_ms = slot * self.epoch_config.aztec_slot_duration_seconds * 1000
        self.current_time_ms = slot_start_ms

        # Record slot start
        self.event_store.record_slot_start(slot, slot_start_ms)

        # Track node status changes at start of slot
        for validator_id, validator_node in validators.items():
            status_change = validator_node.update_online_status()
            if status_change is not None:
                event_type = (
                    EventType.NODE_ONLINE if status_change else EventType.NODE_OFFLINE
                )
                self.event_store.add_event(
                    Event(
                        timestamp_ms=slot_start_ms,
                        slot=slot,
                        event_type=event_type,
                        actor=validator_id,
                        data={"is_online": status_change},
                    )
                )

        # Get proposer
        proposer = committee.proposer_schedule[slot]
        proposer_node = validators[proposer]

        # Phase 1: Block proposal (0-5 seconds)
        block_proposed = proposer_node.should_propose_block(slot)

        if block_proposed:
            # Create block
            block = Block(
                slot=slot,
                proposer=proposer,
                parent_hash=self.last_block_hash,
                transactions=0,
                timestamp=datetime.now(),
            )
            self.last_block_hash = block.hash

            # Record block proposal
            self.event_store.add_event(
                Event(
                    timestamp_ms=slot_start_ms,
                    slot=slot,
                    event_type=EventType.BLOCK_PROPOSED,
                    actor=proposer,
                    data={
                        "block_hash": block.hash,
                        "parent_hash": block.parent_hash,
                        "transactions": block.transactions,
                        "proposer": proposer,
                    },
                )
            )

            # Propagate block through network
            propagation_trace = network.propagate_block_proposal(proposer, block)

            # Record block receipt events
            for (
                receiver,
                delivery_time_ms,
                hops,
                sender,
            ) in propagation_trace.deliveries:
                self.event_store.add_event(
                    Event(
                        timestamp_ms=slot_start_ms + delivery_time_ms,
                        slot=slot,
                        event_type=EventType.BLOCK_RECEIVED_P2P,
                        actor=sender,  # The intermediary who delivered the block
                        subject=receiver,  # The validator who received it
                        data={
                            "block_hash": block.hash,
                            "proposer": proposer,  # Original block proposer
                            "parent_hash": block.parent_hash,
                            "transactions": block.transactions,
                            "delivery_time_ms": delivery_time_ms,
                            "hops": hops,
                        },
                    )
                )

            # Phase 2: Attestations
            attestation_deadline_ms = (
                self.epoch_config.attestation_collection_window_seconds * 1000
            )

            # Proposer creates their own attestation immediately
            # They should only do this if they are online
            self.event_store.add_event(
                Event(
                    timestamp_ms=slot_start_ms + 100,  # Almost immediately after block
                    slot=slot,
                    event_type=EventType.ATTESTATION_CREATED,
                    actor=proposer,
                    data={
                        "block_hash": block.hash,
                        "attester": proposer,
                        "delay_ms": 100,
                    },
                )
            )

            # Batch process committee attestations for better performance
            attestation_events = []
            attestations_to_propagate = []

            # Note: We'll use behavior-specific response delays instead of a generic base delay

            for i, validator_id in enumerate(committee.validators):
                if validator_id == proposer:
                    continue

                # Check if validator received the block
                delivery_time = propagation_trace.get_delivery_time(validator_id)

                if delivery_time is not None:
                    time_to_deadline = attestation_deadline_ms - delivery_time
                    validator_node = validators[validator_id]

                    if validator_node.should_attest(block, time_to_deadline):
                        # Use pre-generated random delays
                        if validator_node.profile == BehaviorProfile.HONEST:
                            mean = validator_node.config.honest_response_mean
                            std = validator_node.config.honest_response_std
                        elif validator_node.profile == BehaviorProfile.LAZY:
                            mean = validator_node.config.lazy_response_mean
                            std = validator_node.config.lazy_response_std
                        else:  # Byzantine
                            mean = validator_node.config.byzantine_response_mean
                            std = validator_node.config.byzantine_response_std

                        # Ensure minimum response delay of 100ms for physical processing time
                        MIN_RESPONSE_DELAY_MS = 100
                        response_delay = max(
                            MIN_RESPONSE_DELAY_MS, np.random.normal(mean, std)
                        )
                        # Total attestation time is block delivery + validator response time
                        attestation_time_ms = delivery_time + response_delay

                        # Batch attestation events
                        attestation_events.append(
                            Event(
                                timestamp_ms=slot_start_ms + attestation_time_ms,
                                slot=slot,
                                event_type=EventType.ATTESTATION_CREATED,
                                actor=validator_id,
                                data={
                                    "block_hash": block.hash,
                                    "attester": validator_id,
                                    "delay_ms": attestation_time_ms,
                                },
                            )
                        )

                        # Create actual attestation for propagation
                        attestation = Attestation(
                            validator=validator_id,
                            slot=slot,
                            block_hash=block.hash,
                            received_at=datetime.now(),
                            propagation_delay_ms=attestation_time_ms,
                        )

                        attestations_to_propagate.append(
                            (validator_id, attestation, attestation_time_ms)
                        )

            # Add all attestation creation events in batch
            if attestation_events:
                self.event_store.add_events_batch(attestation_events)

            # Now propagate all attestations and collect receipt events
            receipt_events = []
            for (
                validator_id,
                attestation,
                attestation_time_ms,
            ) in attestations_to_propagate:
                # Propagate attestation
                att_propagation = network.propagate_attestation(
                    validator_id, attestation
                )

                # Collect attestation receipt events
                for (
                    receiver,
                    peer_delivery_time,
                    peer_hops,
                    sender,
                ) in att_propagation.deliveries:
                    # peer_delivery_time is relative to attestation creation
                    absolute_delivery_time = attestation_time_ms + peer_delivery_time
                    receipt_events.append(
                        Event(
                            timestamp_ms=slot_start_ms + absolute_delivery_time,
                            slot=slot,
                            event_type=EventType.ATTESTATION_RECEIVED_P2P,
                            actor=sender,  # The intermediary who delivered the message
                            subject=receiver,  # The validator who received it
                            data={
                                "block_hash": block.hash,
                                "attester": validator_id,  # Original creator of the attestation
                                "delivery_time_ms": absolute_delivery_time,
                                "hops": peer_hops,
                            },
                        )
                    )

            # Add all receipt events in batch
            if receipt_events:
                self.event_store.add_events_batch(receipt_events)

            # Phase 3: Post-process events to determine L1 submission
            # This analyzes the attestation events we just recorded to determine
            # when L1 submission would occur
            self._process_l1_submission(slot, block, proposer, validators)

        # Record slot end
        self.event_store.add_event(
            Event(
                timestamp_ms=slot_start_ms
                + self.epoch_config.aztec_slot_duration_seconds * 1000,
                slot=slot,
                event_type=EventType.SLOT_END,
                data={"block_proposed": block_proposed},
            )
        )

    def _process_l1_submission(
        self,
        slot: int,
        block: Block,
        proposer: str,
        validators: Dict[str, ValidatorNode],
    ):
        """Analyze attestation events to determine L1 submission outcome.

        This post-processing step reconstructs when the proposer would have
        submitted to L1 based on attestations received. The proposer submits
        as soon as they collect 33/48 attestations (2/3 + 1 supermajority).

        The submission succeeds if:
        - 33 attestations are collected
        - Submission occurs before the 18-second deadline
        - The Ethereum block hasn't already been mined

        This approach ensures accurate timing by analyzing the actual
        propagation of attestations through the P2P network.

        Args:
            slot: The slot number
            block: The proposed block
            proposer: ID of the block proposer
            validators: Map of validator nodes (unused but kept for compatibility)
        """
        slot_start_ms = slot * self.epoch_config.aztec_slot_duration_seconds * 1000
        # Use config value if available, otherwise default to 18 seconds
        l1_submission_deadline_ms = (
            self.simulation_config.l1_submission_deadline_ms
            if self.simulation_config
            else 18000
        )

        # Get all attestation receipt events for the proposer in this slot
        proposer_attestations = []

        for event in self.event_store.get_events_for_slot(slot):
            # Find when proposer received attestations
            if (
                event.event_type == EventType.ATTESTATION_RECEIVED_P2P
                and event.subject == proposer
            ):
                relative_time = event.timestamp_ms - slot_start_ms
                # Only count attestations that arrive before L1 submission deadline
                if relative_time < l1_submission_deadline_ms:
                    proposer_attestations.append(
                        {
                            "attester": event.data["attester"],
                            "timestamp_ms": relative_time,
                        }
                    )

        # Add proposer's own attestation (they always have it immediately)
        proposer_attestations.insert(
            0,
            {
                "attester": proposer,
                "timestamp_ms": 100,  # Proposer attests almost immediately
            },
        )

        # Sort by timestamp to find when we hit threshold
        proposer_attestations.sort(key=lambda x: x["timestamp_ms"])

        # Calculate consensus threshold (2/3 + 1)
        threshold = (self.epoch_config.committee_size * 2 // 3) + 1

        # Check if we reached consensus threshold
        if len(proposer_attestations) >= threshold:
            # Time when threshold attestation was received
            threshold_time_ms = proposer_attestations[threshold - 1]["timestamp_ms"]

            # L1 submission happens shortly after reaching threshold
            l1_submission_time = threshold_time_ms  # + random.uniform(50, 200)

            # Only submit if before deadline
            if l1_submission_time < l1_submission_deadline_ms:
                proposer_block_attestations = proposer_attestations[:threshold]

                # Calculate Ethereum slot timing
                absolute_time = slot_start_ms + l1_submission_time
                ethereum_slot_duration_ms = (
                    self.epoch_config.ethereum_slot_duration_seconds * 1000
                )

                current_ethereum_slot = int(absolute_time / ethereum_slot_duration_ms)
                ethereum_slot_start_ms = (
                    current_ethereum_slot * ethereum_slot_duration_ms
                )
                time_into_ethereum_slot = absolute_time - ethereum_slot_start_ms

                inclusion_cutoff_ms = 4000

                print(
                    f"    Submitting to L1 at {l1_submission_time:.1f}ms (reached {threshold} attestations)"
                )
                print(
                    f"    L1 submission at {l1_submission_time:.1f}ms (Eth slot {current_ethereum_slot}, {time_into_ethereum_slot:.1f}ms into slot)"
                )

                # Determine submission result
                submission_status = "pending"
                inclusion_time_ms = None
                failure_reason = None

                # Will be included in next Ethereum block
                # Or even the one after if we are already to far into this slot
                next_ethereum_block_time = (
                    current_ethereum_slot
                    + 1
                    + (1 if time_into_ethereum_slot > inclusion_cutoff_ms else 0)
                ) * ethereum_slot_duration_ms
                inclusion_time_ms = next_ethereum_block_time - slot_start_ms

                aztec_slot_duration_ms = (
                    self.epoch_config.aztec_slot_duration_seconds * 1000
                )

                if inclusion_time_ms <= aztec_slot_duration_ms:
                    submission_status = "success"
                else:
                    submission_status = "failed"
                    failure_reason = "inclusion_too_late"

                # Record single L1 submission event with status
                self.event_store.add_event(
                    Event(
                        timestamp_ms=slot_start_ms + l1_submission_time,
                        slot=slot,
                        event_type=EventType.L1_SUBMISSION,
                        actor=proposer,
                        data={
                            "block_hash": block.hash,
                            "attestation_count": len(proposer_block_attestations),
                            "submission_time_ms": l1_submission_time,
                            "attesters": [
                                att["attester"] for att in proposer_block_attestations
                            ],
                            "status": submission_status,
                            "ethereum_slot": current_ethereum_slot,
                            "time_into_eth_slot": time_into_ethereum_slot,
                            "inclusion_time_ms": inclusion_time_ms,
                            "failure_reason": failure_reason,
                        },
                    )
                )

                # If successful, record L1 finalization
                if submission_status == "success":
                    self.event_store.add_event(
                        Event(
                            timestamp_ms=slot_start_ms + inclusion_time_ms,
                            slot=slot,
                            event_type=EventType.L1_FINALIZED,
                            data={
                                "block_hash": block.hash,
                                "proposer": proposer,
                                "parent_hash": block.parent_hash,
                                "transactions": block.transactions,
                                "attestations": [
                                    att["attester"]
                                    for att in proposer_block_attestations
                                ],
                                "attestation_count": len(proposer_block_attestations),
                                "ethereum_block": current_ethereum_slot + 1,
                                "ethereum_block_time": (current_ethereum_slot + 1)
                                * ethereum_slot_duration_ms,
                            },
                        )
                    )
        else:
            # Never reached consensus - record as failed submission
            print(
                f"    WARNING: Only collected {len(proposer_attestations)}/{threshold} attestations - block dropped!"
            )
            self.event_store.add_event(
                Event(
                    timestamp_ms=slot_start_ms + l1_submission_deadline_ms,
                    slot=slot,
                    event_type=EventType.L1_SUBMISSION,
                    actor=proposer,
                    data={
                        "block_hash": block.hash,
                        "attestation_count": len(proposer_attestations),
                        "attesters": [att["attester"] for att in proposer_attestations],
                        "submission_time_ms": l1_submission_deadline_ms,
                        "status": "failed",
                        "failure_reason": "insufficient_attestations",
                        "ethereum_slot": None,
                        "time_into_eth_slot": None,
                        "inclusion_time_ms": None,
                    },
                )
            )

    def record_simulation_end(self):
        """Record simulation end"""
        self.event_store.add_event(
            Event(
                timestamp_ms=self.current_time_ms,
                slot=-1,
                event_type=EventType.SIMULATION_END,
                data={"total_events": len(self.event_store.events)},
            )
        )
