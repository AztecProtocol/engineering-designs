#!/usr/bin/env python
"""
Clean event viewer using DataFrames for better visualization
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(".")))

import polars as pl
from models import SimulationConfig, EpochConfig, BehaviorProfile
from collector import EventCollector
from committee import CommitteeManager
from validator import ValidatorNode
from network import GossipSubSimulator
from events import EventType


def run_simple_simulation():
    """Run a simple 1-slot simulation"""
    config = SimulationConfig(
        total_validators=50,
        epochs_to_simulate=1,
        honest_ratio=0.7,
        lazy_ratio=0.2,
        byzantine_ratio=0.1,
        random_seed=42,
    )

    epoch_config = EpochConfig()
    committee_manager = CommitteeManager(epoch_config, config.random_seed)
    collector = EventCollector(epoch_config)

    # Create validators
    validators = {}
    idx = 0
    for _ in range(int(config.total_validators * config.honest_ratio)):
        vid = f"validator_{idx:04d}"
        validators[vid] = ValidatorNode(
            vid, BehaviorProfile.HONEST, config.random_seed + idx, config
        )
        idx += 1

    for _ in range(int(config.total_validators * config.lazy_ratio)):
        vid = f"validator_{idx:04d}"
        validators[vid] = ValidatorNode(
            vid, BehaviorProfile.LAZY, config.random_seed + idx, config
        )
        idx += 1

    for _ in range(config.total_validators - idx):
        vid = f"validator_{idx:04d}"
        validators[vid] = ValidatorNode(
            vid, BehaviorProfile.BYZANTINE, config.random_seed + idx, config
        )
        idx += 1

    # Setup network
    validator_ids = list(validators.keys())
    network = GossipSubSimulator(config, validator_ids)
    network.set_validator_behaviors(validators)

    # Run simulation
    collector.record_simulation_start(config)
    collector.record_epoch_start(0)
    committee = committee_manager.draw_committee(0, validator_ids)

    # Record committee once for the epoch
    collector.record_committee_selection(0, committee, validators)

    # Just run slot 0
    print("Running slot 0...")
    collector.record_proposer_assignment(0, committee)
    collector.record_slot(0, committee, validators, network)

    return collector.event_store, committee.proposer_schedule[0]


def create_event_dataframe(event_store):
    """Create a clean DataFrame from events"""
    df = event_store.to_dataframe()

    # Add human-readable event type
    df = df.with_columns(pl.col("event_type").alias("event"))

    # Extract key data fields (they're already flattened with data_ prefix)
    # Handle columns that may or may not exist
    columns_to_add = []

    # Block hash
    if "data_block_hash" in df.columns:
        columns_to_add.append(
            pl.when(pl.col("data_block_hash").is_not_null())
            .then(pl.col("data_block_hash").cast(pl.Utf8).str.slice(0, 8))
            .otherwise(pl.lit(""))
            .alias("block_hash")
        )
    else:
        columns_to_add.append(pl.lit("").alias("block_hash"))

    # Attestation count (convert from string)
    if "data_attestation_count" in df.columns:
        columns_to_add.append(
            pl.when(pl.col("data_attestation_count").is_not_null())
            .then(pl.col("data_attestation_count").cast(pl.Int64))
            .otherwise(pl.lit(0))
            .cast(pl.Int64)
            .alias("attestation_count")
        )
    else:
        columns_to_add.append(pl.lit(0).cast(pl.Int64).alias("attestation_count"))

    # Status
    if "data_status" in df.columns:
        columns_to_add.append(
            pl.when(pl.col("data_status").is_not_null())
            .then(pl.col("data_status"))
            .otherwise(pl.lit(""))
            .alias("status")
        )
    else:
        columns_to_add.append(pl.lit("").alias("status"))

    # Attester
    if "data_attester" in df.columns:
        columns_to_add.append(
            pl.when(pl.col("data_attester").is_not_null())
            .then(pl.col("data_attester"))
            .otherwise(pl.lit(""))
            .alias("attester")
        )
    else:
        columns_to_add.append(pl.lit("").alias("attester"))

    # Submission time
    if "data_submission_time_ms" in df.columns:
        columns_to_add.append(
            pl.when(pl.col("data_submission_time_ms").is_not_null())
            .then(pl.col("data_submission_time_ms"))
            .otherwise(pl.lit(0))
            .alias("submission_time_ms")
        )
    else:
        columns_to_add.append(pl.lit(0).alias("submission_time_ms"))

    # Time ms
    columns_to_add.append(pl.col("timestamp_ms").cast(pl.Int64).alias("time_ms"))

    df = df.with_columns(columns_to_add)

    return df


def get_validator_events(df, validator_id, slot=0, include_global=True):
    """
    Get all events related to a specific validator.

    Args:
        df: Event DataFrame
        validator_id: Validator to filter for
        slot: Slot number to filter
        include_global: Whether to include global events (L1_FINALIZED, SLOT_END)

    Returns:
        DataFrame with validator-specific events and relative timestamps
    """
    # Filter for this slot
    slot_df = df.filter(pl.col("slot") == slot)

    # Calculate relative time
    slot_start = slot_df["timestamp_ms"].min()
    slot_df = slot_df.with_columns(
        ((pl.col("timestamp_ms") - slot_start).round(1)).alias("relative_ms")
    )

    # Build the filter
    filter_condition = (pl.col("actor") == validator_id) | (
        pl.col("subject") == validator_id
    )

    if include_global:
        global_events = ["L1_FINALIZED", "SLOT_START", "SLOT_END"]
        filter_condition = filter_condition | pl.col("event").is_in(global_events)

    return slot_df.filter(filter_condition)


def get_committee_members(df, epoch=0):
    """
    Extract the committee members from COMMITTEE_SELECTED event.

    Args:
        df: Event DataFrame
        epoch: Epoch number to get committee for

    Returns:
        List of validator IDs in the committee
    """
    import json

    committee_event = df.filter(
        (pl.col("event") == "COMMITTEE_SELECTED") & (pl.col("data_epoch") == epoch)
    )

    if committee_event.height == 0:
        return []

    # Extract committee list from the data field (it's a JSON string)
    committee_str = committee_event["data_committee"][0]
    if isinstance(committee_str, str):
        return json.loads(committee_str)
    return committee_str


def get_l1_attestations(df):
    """
    Get all attestations that made it to L1 across all slots.
    
    Extracts attestations from L1_FINALIZED events to show which validators' 
    attestations were successfully included on-chain.
    
    Args:
        df: Event DataFrame
        
    Returns:
        Dict mapping slot -> list of attesters whose attestations were finalized
    """
    import json
    
    l1_finalized = df.filter(pl.col("event") == "L1_FINALIZED")
    
    result = {}
    for row in l1_finalized.iter_rows(named=True):
        slot = row["slot"]
        attestations_str = row.get("data_attestations")
        
        if attestations_str:
            if isinstance(attestations_str, str):
                attesters = json.loads(attestations_str)
            else:
                attesters = attestations_str
            result[slot] = attesters
        else:
            result[slot] = []
    
    return result


def get_l1_view(df):
    """
    Get complete L1 view showing all finalized blocks and their attestations.
    
    This represents the global L1 state that all validators eventually observe,
    showing which blocks were finalized and which attestations were included.
    
    Args:
        df: Event DataFrame
        
    Returns:
        DataFrame with all L1_FINALIZED events and their attestation data
    """
    return df.filter(pl.col("event") == "L1_FINALIZED")


def get_key_events(df, slot=0):
    """Get only the most important events for a slot"""
    slot_df = df.filter(pl.col("slot") == slot)

    # Calculate relative time
    slot_start = slot_df["timestamp_ms"].min()
    slot_df = slot_df.with_columns(
        ((pl.col("timestamp_ms") - slot_start).round(1)).alias("relative_ms")
    )

    # Filter for key events
    key_event_types = ["BLOCK_PROPOSED", "L1_SUBMISSION", "L1_FINALIZED"]
    return slot_df.filter(pl.col("event").is_in(key_event_types))


def show_validator_timeline(df, validator_id, slot=0):
    """Show clean timeline for a specific validator"""
    print(f"\n{'='*80}")
    print(f"TIMELINE FOR {validator_id} - SLOT {slot}")
    print(f"{'='*80}")

    # Use the helper function
    validator_events = get_validator_events(df, validator_id, slot)

    # Clean up the display
    attestation_count = 0
    for row in validator_events.iter_rows(named=True):
        time = f"[{row['relative_ms']:7.1f}ms]"

        if row["event"] == "BLOCK_PROPOSED" and row["actor"] == validator_id:
            print(f"{time} 📦 I PROPOSED block {row['block_hash']}")
        elif row["event"] == "BLOCK_RECEIVED_P2P" and row["subject"] == validator_id:
            print(f"{time} 📨 Received block {row['block_hash']} from {row['actor']}")
        elif row["event"] == "ATTESTATION_CREATED" and row["actor"] == validator_id:
            print(f"{time} ✍️  Created attestation for {row['block_hash']}")
        elif (
            row["event"] == "ATTESTATION_RECEIVED_P2P"
            and row["subject"] == validator_id
        ):
            attestation_count += 1
            print(
                f"{time} 📬 [{attestation_count:2d}/48] Received attestation from {row['attester']}"
            )
        elif row["event"] == "L1_SUBMISSION" and row["actor"] == validator_id:
            if row["status"] == "success":
                print(
                    f"{time} ✅ Submitted to L1 with {int(row['attestation_count'])} attestations - SUCCESS"
                )
            else:
                print(f"{time} ❌ L1 submission FAILED")
        elif row["event"] == "L1_FINALIZED":
            print(
                f"{time} 🌐 === GLOBAL: Block {row['block_hash']} FINALIZED on L1 with {int(row['attestation_count'])} attestations ==="
            )
        elif row["event"] == "SLOT_END":
            print(f"{time} --- SLOT END ---")


def show_key_events(df, slot=0):
    """Show only the key events in chronological order"""
    print(f"\n{'='*80}")
    print(f"KEY EVENTS - SLOT {slot}")
    print(f"{'='*80}")

    # Use the helper function
    key_events = get_key_events(df, slot)

    for row in key_events.iter_rows(named=True):
        time = f"[{row['relative_ms']:7.1f}ms]"

        if row["event"] == "BLOCK_PROPOSED":
            print(f"{time} 📦 Block proposed by {row['actor']}")
        elif row["event"] == "L1_SUBMISSION":
            status_icon = "✅" if row["status"] == "success" else "❌"
            print(
                f"{time} {status_icon} {row['actor']} L1 submission: {row['status']} ({int(row['attestation_count'])} attestations)"
            )
        elif row["event"] == "L1_FINALIZED":
            print(
                f"{time} 🌐 Block FINALIZED on L1 ({int(row['attestation_count'])} attestations)"
            )


def main():
    print("=" * 80)
    print("CLEAN EVENT VIEWER WITH DATAFRAMES")
    print("=" * 80)

    # Run simulation
    event_store, proposer = run_simple_simulation()

    # Create DataFrame
    df = create_event_dataframe(event_store)

    # Show key events
    show_key_events(df, slot=0)

    # Show proposer timeline
    show_validator_timeline(df, proposer, slot=0)

    # Show a regular validator timeline
    show_validator_timeline(df, "validator_0000", slot=0)

    # Summary statistics
    print(f"\n{'='*80}")
    print("EVENT SUMMARY")
    print(f"{'='*80}")

    event_counts = (
        df.filter(pl.col("slot") == 0)
        .group_by("event")
        .count()
        .sort("count", descending=True)
    )
    print("\nEvent counts for slot 0:")
    for row in event_counts.iter_rows():
        event, count = row[0], row[1]
        if event in [
            "BLOCK_PROPOSED",
            "ATTESTATION_CREATED",
            "L1_SUBMISSION",
            "L1_FINALIZED",
        ]:
            print(f"  {event}: {count}")

    # Show attestation collection
    attestation_events = df.filter(
        (pl.col("event") == "ATTESTATION_RECEIVED_P2P")
        & (pl.col("subject") == proposer)
    )
    print(f"\nProposer received {attestation_events.height} attestations via P2P")

    # L1 submission details
    l1_submissions = df.filter(pl.col("event") == "L1_SUBMISSION")
    if l1_submissions.height > 0:
        l1_sub = l1_submissions.row(0, named=True)
        print(f"L1 submission status: {l1_sub['status']}")
        print(f"Attestations submitted: {int(l1_sub['attestation_count'])}")

    print("\n✅ Use this script to view clean event timelines!")

    return df


if __name__ == "__main__":
    df = main()
