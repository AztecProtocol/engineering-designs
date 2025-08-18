import random
from typing import List, Dict

try:
    from .models import Committee, EpochConfig
except ImportError:
    from models import Committee, EpochConfig


class CommitteeManager:
    """Manages committee selection and proposer assignment for the consensus protocol.

    The CommitteeManager is responsible for:
    - Randomly selecting committees for each epoch
    - Assigning proposers to slots within each epoch
    - Ensuring deterministic selection using seeded randomness

    Committee selection is critical for consensus security. By randomly
    selecting validators for each epoch, we prevent attackers from knowing
    in advance which validators will be responsible for specific slots.

    The use of deterministic seeds ensures that simulations are reproducible
    while still providing the randomness needed for realistic modeling.
    """

    def __init__(self, epoch_config: EpochConfig, seed: int = 42):
        """Initialize the committee manager.

        Args:
            epoch_config: Configuration with committee size and slot parameters
            seed: Base random seed for reproducible committee selection
        """
        self.config = epoch_config
        self.base_seed = seed

    def get_epoch_seed(self, epoch: int) -> int:
        """Generate a deterministic seed for an epoch.

        Each epoch gets a unique seed derived from the base seed,
        ensuring different but reproducible committee selections.

        Args:
            epoch: The epoch number

        Returns:
            Seed value for this epoch's random selections
        """
        return self.base_seed + epoch * 1000

    def get_slot_seed(self, slot: int) -> int:
        """Generate a deterministic seed for a slot.

        Each slot gets a unique seed for proposer selection,
        ensuring reproducible but unpredictable assignments.

        Args:
            slot: The slot number

        Returns:
            Seed value for this slot's proposer selection
        """
        return self.base_seed + slot * 10

    def draw_committee(self, epoch: int, validator_set: List[str]) -> Committee:
        """Randomly select a committee for an epoch.

        Selects a subset of validators to form the committee for this epoch.
        Also pre-assigns proposers for all slots in the epoch to avoid
        recalculation during simulation.

        Args:
            epoch: The epoch number
            validator_set: List of all available validator IDs

        Returns:
            Committee object with selected validators and proposer schedule

        Raises:
            ValueError: If validator set is smaller than committee size
        """
        if len(validator_set) < self.config.committee_size:
            raise ValueError(
                f"Validator set ({len(validator_set)}) smaller than committee size ({self.config.committee_size})"
            )

        random.seed(self.get_epoch_seed(epoch))
        committee_validators = random.sample(validator_set, self.config.committee_size)

        # Pre-assign proposers for all slots in the epoch
        proposer_schedule = {}
        for slot_in_epoch in range(self.config.slots_per_epoch):
            slot_number = epoch * self.config.slots_per_epoch + slot_in_epoch
            proposer_schedule[slot_number] = self.select_proposer(
                slot_number, committee_validators
            )

        return Committee(
            epoch=epoch,
            validators=committee_validators,
            proposer_schedule=proposer_schedule,
        )

    def select_proposer(self, slot: int, committee: List[str]) -> str:
        """Select a proposer for a specific slot.

        Uses deterministic randomness to select one validator from the
        committee to be the block proposer for this slot.

        Args:
            slot: The slot number
            committee: List of committee member IDs

        Returns:
            ID of the selected proposer
        """
        random.seed(self.get_slot_seed(slot))
        return random.choice(committee)

    def get_attesters_for_slot(self, committee: Committee, slot: int) -> List[str]:
        """Get the list of validators who should attest in a slot.

        Returns all committee members except the proposer, as the proposer
        creates the block but other members attest to it.

        Args:
            committee: The committee for this epoch
            slot: The slot number

        Returns:
            List of validator IDs who should create attestations
        """
        proposer = committee.proposer_schedule.get(slot)
        if not proposer:
            return committee.validators

        # Return all committee members except the proposer
        return [v for v in committee.validators if v != proposer]
