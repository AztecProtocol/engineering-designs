import random
from typing import Optional, Tuple

try:
    from .models import BehaviorProfile, Block
except ImportError:
    from models import BehaviorProfile, Block


class ValidatorNode:
    """Represents a validator node in the Aztec network simulation.

    This class models the behavior of individual validators, including their
    decision-making for block proposals and attestations. Validators can have
    different behavior profiles (Honest, Lazy, Byzantine) that affect their
    reliability and participation rates.

    The validator's behavior is influenced by:
    - Their behavior profile (honest, lazy, or byzantine)
    - Network conditions and online status
    - Time pressure and deadlines
    - Probabilistic decision-making based on configured rates

    Attributes:
        id: Unique identifier for this validator
        profile: Behavior profile determining participation patterns
        is_online: Current online/offline status
        is_private: Whether validator is behind NAT/firewall (can only initiate outbound)
        network_latency_ms: Network latency affecting message delivery
        random: Seeded random generator for reproducible behavior
        config: Configuration object with behavior parameters
    """

    def __init__(
        self,
        validator_id: str,
        behavior_profile: BehaviorProfile,
        seed: int = None,
        config=None,
    ):
        """Initialize a validator node with specified behavior.

        Args:
            validator_id: Unique identifier for this validator
            behavior_profile: The behavior type (HONEST, LAZY, or BYZANTINE)
            seed: Random seed for reproducible behavior
            config: Optional SimulationConfig with behavior parameters
        """
        self.id = validator_id
        self.profile = behavior_profile
        self.is_online = True
        self.is_private = False  # Will be set based on probability
        self.network_latency_ms = 0.0
        self.random = random.Random(seed) if seed else random.Random()
        self.config = config

        # Set behavior-specific parameters
        self._set_behavior_parameters()

    def _set_behavior_parameters(self):
        """Set behavior-specific parameters based on profile.

        Configures proposal rates, attestation rates, downtime probability,
        recovery probability, and whether the validator is behind NAT/firewall
        based on the validator's behavior profile. Uses config values if available,
        otherwise falls back to sensible defaults.
        """
        if self.config:
            # Use config values if provided
            if self.profile == BehaviorProfile.HONEST:
                self.proposal_rate = self.config.honest_proposal_rate
                self.attestation_rate = self.config.honest_attestation_rate
                self.downtime_probability = self.config.honest_downtime_prob
                self.recovery_probability = self.config.honest_recovery_prob
                # Determine if this validator is behind NAT/firewall
                self.is_private = self.random.random() < self.config.honest_private_peer_prob
            elif self.profile == BehaviorProfile.LAZY:
                self.proposal_rate = self.config.lazy_proposal_rate
                self.attestation_rate = self.config.lazy_attestation_rate
                self.downtime_probability = self.config.lazy_downtime_prob
                self.recovery_probability = self.config.lazy_recovery_prob
                # Lazy validators more likely to be behind NAT/firewall
                self.is_private = self.random.random() < self.config.lazy_private_peer_prob
            else:  # BYZANTINE
                self.proposal_rate = self.config.byzantine_proposal_rate
                self.attestation_rate = self.config.byzantine_attestation_rate
                self.downtime_probability = self.config.byzantine_downtime_prob
                self.recovery_probability = self.config.byzantine_recovery_prob
                # Byzantine validators often intentionally hide
                self.is_private = self.random.random() < self.config.byzantine_private_peer_prob
        else:
            # Default values
            if self.profile == BehaviorProfile.HONEST:
                self.proposal_rate = 0.99
                self.attestation_rate = 0.98
                self.downtime_probability = 0.001
                self.recovery_probability = 0.9
                self.is_private = self.random.random() < 0.05  # 5% behind NAT
            elif self.profile == BehaviorProfile.LAZY:
                self.proposal_rate = 0.30
                self.attestation_rate = 0.20
                self.downtime_probability = 0.15
                self.recovery_probability = 0.3
                self.is_private = self.random.random() < 0.4  # 40% behind NAT
            else:  # BYZANTINE
                self.proposal_rate = 0.10
                self.attestation_rate = 0.05
                self.downtime_probability = 0.25
                self.recovery_probability = 0.05
                self.is_private = self.random.random() < 0.6  # 60% behind NAT

    def update_online_status(self) -> Optional[bool]:
        """Update the validator's online/offline status probabilistically.

        Online validators may go offline based on downtime_probability.
        Offline validators may recover based on recovery_probability.
        This models real-world validator availability issues like
        network problems, hardware failures, or maintenance.
        
        Returns:
            True if went online, False if went offline, None if no change
        """
        previous_status = self.is_online
        
        if self.is_online:
            # Check if validator goes offline
            if self.random.random() < self.downtime_probability:
                self.is_online = False
        else:
            # Check if validator comes back online using configured recovery probability
            if self.random.random() < self.recovery_probability:
                self.is_online = True
        
        # Return status change if any
        if previous_status != self.is_online:
            return self.is_online
        return None
    
    def is_available_for_propagation(self) -> bool:
        """Check if this validator can propagate messages.
        
        A validator can propagate messages if they are online.
        Whether they are private or public affects network topology
        but not their ability to propagate once connected.
        
        Returns:
            Boolean indicating if validator can propagate messages
        """
        # Don't update status here - it's done at slot start
        return self.is_online

    def should_propose_block(self, slot: int) -> bool:
        """Determine whether this validator should propose a block.

        The decision is based on:
        - Current online status (offline validators cannot propose)
        - Behavior profile (byzantine validators may use special strategies)
        - Probabilistic proposal rate

        Args:
            slot: The slot number for the proposal

        Returns:
            True if the validator should propose a block
        """
        # Don't update status here - it's done at slot start
        if not self.is_online:
            return False

        # Model proposal probability based on behavior profile
        if self.profile == BehaviorProfile.BYZANTINE:
            return self.byzantine_proposal_strategy(slot)
        else:
            return self.random.random() < self.proposal_rate

    def byzantine_proposal_strategy(self, slot: int) -> bool:
        """Implement byzantine validator's strategic proposal behavior.

        Byzantine validators may intentionally skip certain slots or
        engage in other malicious behaviors to disrupt consensus.

        Args:
            slot: The slot number for the proposal

        Returns:
            True if the byzantine validator decides to propose
        """
        if slot % 10 == 0:  # Skip every 10th slot
            return False
        return self.random.random() < self.proposal_rate

    def should_attest(self, block: Optional[Block], time_to_deadline_ms: float) -> bool:
        """Determine whether this validator should create an attestation.

        The decision considers:
        - Online status
        - Whether a block exists to attest to
        - Whether the block was received with enough time to process
        - Behavior profile (byzantine validators may be selective)
        - Time pressure (less time = lower probability)

        Args:
            block: The block to attest to (None if no block received)
            time_to_deadline_ms: Milliseconds until attestation deadline

        Returns:
            True if the validator should create an attestation
        """
        if not self.is_online:
            return False

        if block is None:  # No block to attest to
            return False

        # Check if received block in time
        if not self.received_block_in_time(time_to_deadline_ms):
            return False

        if self.profile == BehaviorProfile.BYZANTINE:
            return self.byzantine_attestation_strategy(block)
        else:
            # Apply time pressure
            time_factor = self.calculate_time_pressure_factor(time_to_deadline_ms)
            adjusted_rate = self.attestation_rate * time_factor
            return self.random.random() < adjusted_rate

    def received_block_in_time(self, time_to_deadline_ms: float) -> bool:
        """Check if block was received with enough time to process.

        Validators need minimum processing time to validate a block
        and create an attestation. This models real-world constraints.

        Args:
            time_to_deadline_ms: Time remaining until deadline

        Returns:
            True if there's enough time to process and attest
        """
        min_processing_time_ms = 500  # 500ms minimum to process block
        return time_to_deadline_ms > min_processing_time_ms

    def calculate_time_pressure_factor(self, time_to_deadline_ms: float) -> float:
        """Calculate attestation probability adjustment based on time pressure.

        As the deadline approaches, validators become less likely to
        successfully create and submit attestations. This models the
        real-world effect of network congestion and processing delays.

        Args:
            time_to_deadline_ms: Time remaining until deadline

        Returns:
            Factor between 0.5 and 1.0 to multiply with base attestation rate
        """
        if time_to_deadline_ms < 1000:  # Less than 1 second
            return 0.5
        elif time_to_deadline_ms < 3000:  # Less than 3 seconds
            return 0.8
        else:
            return 1.0

    def byzantine_attestation_strategy(self, block: Block) -> bool:
        """Implement byzantine validator's selective attestation strategy.

        Byzantine validators may selectively withhold attestations to
        disrupt consensus or target specific validators.

        Args:
            block: The block to potentially attest to

        Returns:
            True if the byzantine validator decides to attest
        """
        if hash(block.proposer) % 5 == 0:  # Skip attestations for certain proposers
            return False
        return self.random.random() < self.attestation_rate

    def set_network_latency(self, latency_ms: float):
        """Set the network latency for this validator.

        Args:
            latency_ms: Network latency in milliseconds
        """
        self.network_latency_ms = latency_ms
