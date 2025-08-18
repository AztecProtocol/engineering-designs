"""
Core event model - the single source of truth for all simulation data
"""

import bisect
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum, auto


class EventType(Enum):
    """Enumeration of all event types that can occur during simulation.

    Events are grouped into categories:
    - Simulation lifecycle: Start/end of simulation, epochs, and slots
    - Committee management: Selection and proposer assignment
    - Block operations: Proposal and receipt via P2P
    - Attestations: Creation and propagation through network
    - L1 interactions: Submission attempts and finalization
    - Network dynamics: Node status changes and message drops
    """

    # Simulation events
    SIMULATION_START = auto()
    EPOCH_START = auto()
    SLOT_START = auto()

    # Committee events
    COMMITTEE_SELECTED = auto()
    PROPOSER_ASSIGNED = auto()

    # Block events
    BLOCK_PROPOSED = auto()
    BLOCK_RECEIVED_P2P = auto()

    # Attestation events
    ATTESTATION_CREATED = auto()
    ATTESTATION_RECEIVED_P2P = auto()
    ATTESTATION_RECEIVED_L1 = auto()

    # L1 events
    L1_SUBMISSION = auto()  # Single event with status field
    L1_FINALIZED = auto()  # Replaces per-validator BLOCK_RECEIVED_L1

    # Network events
    NODE_ONLINE = auto()
    NODE_OFFLINE = auto()
    MESSAGE_DROPPED = auto()

    # End events
    SLOT_END = auto()
    EPOCH_END = auto()
    SIMULATION_END = auto()


@dataclass
class Event:
    """Represents a single event in the simulation's event stream.

    Events are the fundamental unit of data in the simulation, recording
    everything that happens with precise timestamps. This event-sourced
    architecture ensures reproducibility and enables detailed analysis.

    Attributes:
        timestamp_ms: Absolute time from simulation start in milliseconds
        slot: The slot number when this event occurred
        event_type: The type of event (from EventType enum)
        actor: The entity performing the action (e.g., sender of a message)
        subject: The entity affected by the action (e.g., receiver of a message)
        data: Additional event-specific data as key-value pairs

    For network events:
        - actor is the sender/intermediary who delivered the message
        - subject is the receiver
        - data contains the original creator (e.g., 'attester' for attestations)
    """

    timestamp_ms: float  # Absolute time from simulation start
    slot: int  # Which slot this occurred in
    event_type: EventType
    actor: Optional[str] = None  # Who performed the action (if applicable)
    subject: Optional[str] = None  # Who is affected (if applicable)
    data: Dict[str, Any] = field(default_factory=dict)  # Event-specific data

    def __str__(self):
        """Format event as a human-readable string."""
        return f"[{self.timestamp_ms:8.1f}ms] Slot {self.slot}: {self.event_type.name} - {self.actor or 'System'}"


class EventStore:
    """Central storage for all simulation events in chronological order.

    The EventStore is the single source of truth for everything that happens
    during a simulation. It maintains events in sorted order by timestamp
    and provides efficient methods for querying and analysis.

    Key features:
    - Maintains chronological ordering of all events
    - Efficient insertion using binary search
    - Batch insertion for performance
    - Multiple query methods for different analysis needs
    - Export to DataFrame for data analysis

    This event-sourced architecture ensures:
    - Complete reproducibility of simulations
    - Ability to reconstruct any point-in-time state
    - Detailed audit trail for debugging
    - Foundation for analytics and visualization
    """

    def __init__(self):
        """Initialize an empty event store."""
        self.events: List[Event] = []
        self._slot_start_times: Dict[int, float] = {}  # Cache slot start times

    def add_event(self, event: Event):
        """Add a single event to the store, maintaining chronological order.

        Uses binary search to find the correct insertion point, ensuring
        O(log n) search time. Events are sorted by (timestamp, event_type)
        to ensure deterministic ordering when events occur simultaneously.

        Args:
            event: The event to add to the store
        """
        # Use bisect to insert in sorted position - O(log n) instead of O(n log n)
        key = (event.timestamp_ms, event.event_type.value)
        # Find insertion point
        left = 0
        right = len(self.events)
        while left < right:
            mid = (left + right) // 2
            mid_key = (self.events[mid].timestamp_ms, self.events[mid].event_type.value)
            if mid_key < key:
                left = mid + 1
            else:
                right = mid
        self.events.insert(left, event)

    def add_events_batch(self, events: List[Event]):
        """Add multiple events efficiently using merge sort for large batches.

        For small batches (<10 events), inserts individually.
        For larger batches, sorts the new events and merges with existing
        events in O(n) time, which is more efficient than individual insertions.

        Args:
            events: List of events to add
        """
        if not events:
            return

        # If we have no existing events, just sort the new ones
        if not self.events:
            self.events = sorted(
                events, key=lambda e: (e.timestamp_ms, e.event_type.value)
            )
            return

        # If adding many events, merge-sort is more efficient
        if len(events) > 10:
            # Sort new events first
            sorted_new = sorted(
                events, key=lambda e: (e.timestamp_ms, e.event_type.value)
            )
            # Merge with existing sorted list
            self.events = self._merge_sorted_lists(self.events, sorted_new)
        else:
            # For small batches, insert individually
            for event in events:
                self.add_event(event)

    def _merge_sorted_lists(
        self, list1: List[Event], list2: List[Event]
    ) -> List[Event]:
        """Merge two sorted event lists in linear time.

        Args:
            list1: First sorted list of events
            list2: Second sorted list of events

        Returns:
            Merged sorted list containing all events from both inputs
        """
        result = []
        i, j = 0, 0

        while i < len(list1) and j < len(list2):
            key1 = (list1[i].timestamp_ms, list1[i].event_type.value)
            key2 = (list2[j].timestamp_ms, list2[j].event_type.value)

            if key1 <= key2:
                result.append(list1[i])
                i += 1
            else:
                result.append(list2[j])
                j += 1

        # Add remaining elements
        result.extend(list1[i:])
        result.extend(list2[j:])

        return result

    def get_events_for_slot(self, slot: int) -> List[Event]:
        """Get all events that occurred during a specific slot.

        Args:
            slot: The slot number to query

        Returns:
            List of events in chronological order for that slot
        """
        return [e for e in self.events if e.slot == slot]

    def get_events_for_validator(self, validator_id: str) -> List[Event]:
        """Get all events where a validator was actor or subject.

        Args:
            validator_id: The validator ID to query

        Returns:
            List of events involving this validator
        """
        return [
            e
            for e in self.events
            if e.actor == validator_id or e.subject == validator_id
        ]

    def get_events_by_type(self, event_type: EventType) -> List[Event]:
        """Filter events by type.

        Args:
            event_type: The EventType to filter for

        Returns:
            List of all events matching the specified type
        """
        return [e for e in self.events if e.event_type == event_type]

    def get_events_in_range(self, start_ms: float, end_ms: float) -> List[Event]:
        """Get all events within a time window.

        Args:
            start_ms: Start of time range (inclusive)
            end_ms: End of time range (inclusive)

        Returns:
            List of events within the specified time range
        """
        return [e for e in self.events if start_ms <= e.timestamp_ms <= end_ms]

    def get_validator_view_at_time(
        self, validator_id: str, timestamp_ms: float
    ) -> List[Event]:
        """Reconstruct what a validator has observed up to a point in time.

        This is useful for understanding a validator's decision-making context
        at any moment during the simulation. It includes:
        - Messages they've received (as subject of RECEIVED events)
        - Actions they've taken (as actor of creation/proposal events)

        Args:
            validator_id: The validator whose view to reconstruct
            timestamp_ms: The point in time to query

        Returns:
            List of events visible to the validator up to that time
        """
        view_events = []
        for event in self.events:
            if event.timestamp_ms > timestamp_ms:
                break

            # Include events where this validator received something
            if event.subject == validator_id and "RECEIVED" in event.event_type.name:
                view_events.append(event)

            # Include events where this validator created/proposed something
            if event.actor == validator_id and event.event_type in [
                EventType.BLOCK_PROPOSED,
                EventType.ATTESTATION_CREATED,
                EventType.L1_SUBMISSION_ATTEMPT,
            ]:
                view_events.append(event)

        return view_events

    def to_dataframe(self):
        """Export events to a Polars DataFrame for data analysis.

        Converts the event stream into a structured DataFrame with columns
        for all event attributes and flattened data fields. This enables
        powerful data analysis using Polars' query capabilities.

        Returns:
            Polars DataFrame with one row per event
        """
        import polars as pl
        import json

        # Define which data fields should be numeric types
        NUMERIC_FIELDS = {
            # Integer fields
            'epoch', 'slot', 'committee_size', 'hops', 'attestation_count',
            'ethereum_slot', 'ethereum_block', 'total_validators', 'epochs',
            'transactions',
            # Float fields  
            'delivery_time_ms', 'delay_ms', 'submission_time_ms', 
            'time_into_eth_slot', 'inclusion_time_ms', 'slot_duration_ms',
            'ethereum_block_time'
        }
        
        # Boolean fields
        BOOLEAN_FIELDS = {'block_proposed'}

        # First pass: collect all unique data keys to ensure consistent schema
        all_data_keys = sorted(
            set(key for event in self.events for key in event.data.keys())
        )

        records = []
        for event in self.events:
            record = {
                "timestamp_ms": float(event.timestamp_ms),
                "slot": int(event.slot) if event.slot is not None else 0,
                "event_type": (
                    str(event.event_type.name)
                    if hasattr(event.event_type, "name")
                    else str(event.event_type)
                ),
                "actor": str(event.actor) if event.actor else None,
                "subject": str(event.subject) if event.subject else None,
            }
            # Add ALL data fields to ensure consistent schema
            for key in all_data_keys:
                value = event.data.get(key, None)
                # Convert based on field type
                if value is not None:
                    if isinstance(value, (list, dict)):
                        value = json.dumps(value)
                    elif key in NUMERIC_FIELDS:
                        # Keep numeric values as numbers
                        try:
                            if '.' in str(value) or 'e' in str(value).lower():
                                value = float(value)
                            else:
                                value = int(value)
                        except (ValueError, TypeError):
                            value = None
                    elif key in BOOLEAN_FIELDS:
                        # Convert to boolean
                        if isinstance(value, str):
                            value = value.lower() in ('true', '1', 'yes')
                        else:
                            value = bool(value)
                    else:
                        # Keep as string
                        value = str(value)
                # Always add the key, even if None
                record[f"data_{key}"] = value
            records.append(record)

        # Create DataFrame with explicit schema
        if records:
            # Define schema with proper types
            schema = {
                "timestamp_ms": pl.Float64,
                "slot": pl.Int64,
                "event_type": pl.Utf8,
                "actor": pl.Utf8,
                "subject": pl.Utf8,
            }
            
            # Define which data fields should be numeric types
            INTEGER_FIELDS = {
                'epoch', 'slot', 'committee_size', 'hops', 'attestation_count',
                'ethereum_slot', 'ethereum_block', 'total_validators', 'epochs',
                'transactions'
            }
            
            FLOAT_FIELDS = {
                'delivery_time_ms', 'delay_ms', 'submission_time_ms', 
                'time_into_eth_slot', 'inclusion_time_ms', 'slot_duration_ms',
                'ethereum_block_time'
            }
            
            # Set appropriate types for each data field
            for key in all_data_keys:
                if key in INTEGER_FIELDS:
                    schema[f"data_{key}"] = pl.Int64
                elif key in FLOAT_FIELDS:
                    schema[f"data_{key}"] = pl.Float64
                elif key in BOOLEAN_FIELDS:
                    schema[f"data_{key}"] = pl.Boolean
                else:
                    schema[f"data_{key}"] = pl.Utf8

            return pl.DataFrame(records, schema=schema)
        else:
            return pl.DataFrame()

    def record_slot_start(self, slot: int, timestamp_ms: float):
        """Record when a slot starts for relative time calculations"""
        self._slot_start_times[slot] = timestamp_ms
        self.add_event(
            Event(
                timestamp_ms=timestamp_ms,
                slot=slot,
                event_type=EventType.SLOT_START,
                data={"slot_duration_ms": 36000},
            )
        )

    def get_relative_time(self, slot: int, absolute_time_ms: float) -> float:
        """Get time relative to slot start"""
        if slot in self._slot_start_times:
            return absolute_time_ms - self._slot_start_times[slot]
        return absolute_time_ms
