import marimo

__generated_with = "0.14.16"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import polars as pl
    import numpy as np
    import altair as alt
    from typing import Dict, List, Any
    from pathlib import Path

    # Add the slashing_simulation directory to path
    import sys
    import json
    import time

    sys.path.insert(0, str(Path(__file__).parent))

    # Import our simulation modules
    from models import SimulationConfig

    # Import simulation with analysis capabilities
    from simulation import run_simulation_with_analysis
    from view_events import (
        get_validator_events,
        get_key_events,
        get_committee_members,
    )

    import heapq
    import hashlib

    import networkx as nx
    import warnings

    warnings.filterwarnings("ignore", category=UserWarning)

    # Enable Altair data transformations
    alt.data_transformers.enable("default")
    return (
        SimulationConfig,
        alt,
        get_committee_members,
        hashlib,
        heapq,
        json,
        mo,
        nx,
        pd,
        pl,
        run_simulation_with_analysis,
        time,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
    # Aztec P2P Network Simulation

    ## Overview
    This interactive notebook simulates the Aztec blockchain's peer-to-peer network and consensus mechanism to analyze validator behavior, network resilience, and potential slashing scenarios. It models realistic network conditions including latency, node failures, and Byzantine behavior.

    ## What This Simulation Does
    - **Models validator diversity**: Simulates honest, lazy, and Byzantine validators with different response times and reliability
    - **Simulates P2P networking**: Models GossipSub propagation with NAT/firewall effects on connectivity
    - **Tracks consensus formation**: Monitors how validators collect attestations to reach the 2/3+1 threshold
    - **Identifies slashing candidates**: Detects validators who propose conflicting blocks or fail their duties
    - **Analyzes network partitions**: Detects when the network splits and its impact on consensus
    - **Measures L1 submission success**: Tracks whether blocks make it to Ethereum within the deadline

    ## How to Use This Notebook
    1. **Configure the simulation** using the sliders below (validator counts, network parameters, behavior probabilities)
    2. **Click "Run Simulation"** to start - this typically takes 5-30 seconds depending on parameters
    3. **Explore the results** through the automatically generated visualizations and metrics
    4. **Analyze specific scenarios** using the interactive charts that appear after simulation

    ## Key Metrics to Watch
    - **L1 Success Rate**: Percentage of blocks that successfully reach Ethereum (target: >95%)
    - **Attestation Participation**: How many validators actually attest vs. expected
    - **Network Partitions**: Whether the network splits into isolated groups
    - **Slashing Proposals**: Validators identified for potential slashing due to misbehavior

    ## Configuration Tips
    - Start with default values for a baseline healthy network
    - Increase lazy/Byzantine ratios to stress-test the network
    - Adjust NAT probabilities to model different network topologies
    - Modify response times to simulate different geographic distributions

    ---

    ## Configuration

    Configure the simulation parameters below:
    """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    # Basic configuration
    total_validators_input = mo.ui.number(
        start=48, stop=10000, value=50, step=1, label="Total Validators"
    )
    committee_size_input = mo.ui.number(
        start=1, stop=200, value=16, step=1, label="Committee Size"
    )
    honest_ratio_input = mo.ui.number(
        start=0.0, stop=1.0, value=0.7, step=0.05, label="Honest Ratio"
    )
    lazy_ratio_input = mo.ui.number(
        start=0.0, stop=1.0, value=0.2, step=0.05, label="Lazy Ratio"
    )
    epochs_input = mo.ui.number(
        start=1, stop=100, value=16, step=1, label="Epochs to Simulate"
    )
    slots_per_epoch_input = mo.ui.number(
        start=1, stop=48, value=16, step=1, label="Slots per Epoch"
    )
    aztec_slot_duration_input = mo.ui.number(
        start=12, stop=120, value=36, step=6, label="Aztec Slot Duration (seconds)"
    )
    random_seed_input = mo.ui.number(
        start=0, stop=10000, value=42, step=1, label="Random Seed"
    )
    round_size_input = mo.ui.number(
        start=1, stop=200, value=100, step=1, label="Round Size"
    )

    # L1 submission deadline control
    l1_submission_deadline_input = mo.ui.number(
        start=1000,
        stop=36000,
        value=16000,
        step=1000,
        label="L1 Submission Deadline (ms)",
    )

    mo.vstack(
        [
            mo.md("### Basic Configuration"),
            mo.hstack(
                [
                    total_validators_input,
                    committee_size_input,
                    honest_ratio_input,
                    lazy_ratio_input,
                    random_seed_input,
                ]
            ),
            mo.md("### Timing Configuration"),
            mo.hstack(
                [
                    round_size_input,
                    epochs_input,
                    slots_per_epoch_input,
                    aztec_slot_duration_input,
                    l1_submission_deadline_input,
                ]
            ),
        ]
    )
    return (
        aztec_slot_duration_input,
        committee_size_input,
        epochs_input,
        honest_ratio_input,
        l1_submission_deadline_input,
        lazy_ratio_input,
        random_seed_input,
        round_size_input,
        slots_per_epoch_input,
        total_validators_input,
    )


@app.cell(hide_code=True)
def _(mo):
    # Network delay configuration

    # Network latency controls
    base_latency_input = mo.ui.number(
        start=1, stop=1000, value=150, step=5, label="Base Network Latency (ms)"
    )
    latency_std_input = mo.ui.number(
        start=0, stop=200, value=150, step=5, label="Latency Std Dev (ms)"
    )
    packet_loss_input = mo.ui.number(
        start=0.0, stop=0.1, value=0.001, step=0.001, label="Packet Loss Rate"
    )

    mo.vstack(
        [
            mo.md("### Network Delay Configuration"),
            mo.md("**Network Parameters:**"),
            mo.hstack([base_latency_input, latency_std_input, packet_loss_input]),
        ]
    )
    return base_latency_input, latency_std_input, packet_loss_input


@app.cell(hide_code=True)
def _(mo):
    # GossipSub network configuration

    gossipsub_d = mo.ui.number(
        start=4, stop=20, value=8, step=1, label="GossipSub D (target mesh degree)"
    )
    gossipsub_dlo = mo.ui.number(
        start=2, stop=10, value=4, step=1, label="GossipSub D_low (min mesh degree)"
    )
    gossipsub_dhi = mo.ui.number(
        start=8,
        stop=30,
        value=12,
        step=1,
        label="GossipSub D_high (max mesh degree)",
    )
    gossipsub_dlazy = mo.ui.number(
        start=2,
        stop=15,
        value=8,
        step=1,
        label="GossipSub D_lazy (lazy push degree)",
    )

    mo.vstack(
        [
            mo.md("## GossipSub Network Configuration"),
            mo.hstack([gossipsub_d, gossipsub_dlo, gossipsub_dhi, gossipsub_dlazy]),
        ]
    )
    return gossipsub_d, gossipsub_dhi, gossipsub_dlazy, gossipsub_dlo


@app.cell(hide_code=True)
def _(mo):
    honest_response_mean = mo.ui.number(
        start=50,
        stop=5000,
        value=1000,
        step=50,
        label="Honest Validator Response Mean (ms)",
    )
    honest_response_std = mo.ui.number(
        start=0,
        stop=2000,
        value=500,
        step=25,
        label="Honest Validator Response Std (ms)",
    )

    honest_proposal_rate = mo.ui.number(
        start=0.0, stop=1.0, value=0.99, step=0.01, label="Honest Proposal Rate"
    )
    honest_attestation_rate = mo.ui.number(
        start=0.0, stop=1.0, value=0.98, step=0.01, label="Honest Attestation Rate"
    )
    honest_downtime_prob = mo.ui.number(
        start=0.0,
        stop=0.1,
        value=0.001,
        step=0.001,
        label="Honest Downtime Probability",
    )
    honest_recovery_prob = mo.ui.number(
        start=0.0,
        stop=1.0,
        value=0.9,
        step=0.05,
        label="Honest Recovery Probability",
    )
    honest_private_peer_prob = mo.ui.number(
        start=0.0,
        stop=1.0,
        value=0.05,
        step=0.05,
        label="Honest Private Peer Probability (NAT/firewall)",
    )

    # Lazy validator probabilities
    # Lazy validator delays
    lazy_response_mean = mo.ui.number(
        start=500,
        stop=20000,
        value=3000,
        step=250,
        label="Lazy Validator Response Mean (ms)",
    )
    lazy_response_std = mo.ui.number(
        start=0,
        stop=10000,
        value=3000,
        step=250,
        label="Lazy Validator Response Std (ms)",
    )
    lazy_proposal_rate = mo.ui.number(
        start=0.0, stop=1.0, value=0.75, step=0.05, label="Lazy Proposal Rate"
    )
    lazy_attestation_rate = mo.ui.number(
        start=0.0, stop=1.0, value=0.75, step=0.05, label="Lazy Attestation Rate"
    )
    lazy_downtime_prob = mo.ui.number(
        start=0.0,
        stop=0.5,
        value=0.10,
        step=0.01,
        label="Lazy Downtime Probability",
    )
    lazy_recovery_prob = mo.ui.number(
        start=0.0,
        stop=1.0,
        value=0.05,
        step=0.05,
        label="Lazy Recovery Probability",
    )
    lazy_private_peer_prob = mo.ui.number(
        start=0.0,
        stop=1.0,
        value=0.4,
        step=0.05,
        label="Lazy Private Peer Probability (NAT/firewall)",
    )

    # Byzantine validator probabilities
    byzantine_response_mean = mo.ui.number(
        start=5000,
        stop=60000,
        value=15000,
        step=1000,
        label="Byzantine Validator Response Mean (ms)",
    )
    byzantine_response_std = mo.ui.number(
        start=0,
        stop=20000,
        value=5000,
        step=500,
        label="Byzantine Validator Response Std (ms)",
    )
    byzantine_proposal_rate = mo.ui.number(
        start=0.0, stop=1.0, value=0.10, step=0.05, label="Byzantine Proposal Rate"
    )
    byzantine_attestation_rate = mo.ui.number(
        start=0.0,
        stop=1.0,
        value=0.05,
        step=0.01,
        label="Byzantine Attestation Rate",
    )
    byzantine_downtime_prob = mo.ui.number(
        start=0.0,
        stop=0.5,
        value=0.25,
        step=0.01,
        label="Byzantine Downtime Probability",
    )
    byzantine_recovery_prob = mo.ui.number(
        start=0.0,
        stop=1.0,
        value=0.05,
        step=0.05,
        label="Byzantine Recovery Probability",
    )
    byzantine_private_peer_prob = mo.ui.number(
        start=0.0,
        stop=1.0,
        value=0.6,
        step=0.05,
        label="Byzantine Private Peer Probability (NAT/firewall)",
    )

    mo.vstack(
        [
            mo.md("## Validator Behavior Probabilities"),
            mo.md("**Honest Validators:**"),
            mo.hstack(
                [honest_response_mean, honest_proposal_rate, honest_attestation_rate]
            ),
            mo.hstack(
                [
                    honest_response_std,
                    honest_downtime_prob,
                    honest_recovery_prob,
                    honest_private_peer_prob,
                ]
            ),
            mo.md("**Lazy Validators:**"),
            mo.hstack([lazy_response_mean, lazy_proposal_rate, lazy_attestation_rate]),
            mo.hstack(
                [
                    lazy_response_std,
                    lazy_downtime_prob,
                    lazy_recovery_prob,
                    lazy_private_peer_prob,
                ]
            ),
            mo.md("**Byzantine Validators:**"),
            mo.hstack(
                [
                    byzantine_response_mean,
                    byzantine_proposal_rate,
                    byzantine_attestation_rate,
                ]
            ),
            mo.hstack(
                [
                    byzantine_response_std,
                    byzantine_downtime_prob,
                    byzantine_recovery_prob,
                    byzantine_private_peer_prob,
                ]
            ),
        ]
    )
    return (
        byzantine_attestation_rate,
        byzantine_downtime_prob,
        byzantine_private_peer_prob,
        byzantine_proposal_rate,
        byzantine_recovery_prob,
        byzantine_response_mean,
        byzantine_response_std,
        honest_attestation_rate,
        honest_downtime_prob,
        honest_private_peer_prob,
        honest_proposal_rate,
        honest_recovery_prob,
        honest_response_mean,
        honest_response_std,
        lazy_attestation_rate,
        lazy_downtime_prob,
        lazy_private_peer_prob,
        lazy_proposal_rate,
        lazy_recovery_prob,
        lazy_response_mean,
        lazy_response_std,
    )


@app.cell(hide_code=True)
def _(
    SimulationConfig,
    aztec_slot_duration_input,
    base_latency_input,
    byzantine_attestation_rate,
    byzantine_downtime_prob,
    byzantine_private_peer_prob,
    byzantine_proposal_rate,
    byzantine_recovery_prob,
    byzantine_response_mean,
    byzantine_response_std,
    committee_size_input,
    epochs_input,
    gossipsub_d,
    gossipsub_dhi,
    gossipsub_dlazy,
    gossipsub_dlo,
    honest_attestation_rate,
    honest_downtime_prob,
    honest_private_peer_prob,
    honest_proposal_rate,
    honest_ratio_input,
    honest_recovery_prob,
    honest_response_mean,
    honest_response_std,
    l1_submission_deadline_input,
    latency_std_input,
    lazy_attestation_rate,
    lazy_downtime_prob,
    lazy_private_peer_prob,
    lazy_proposal_rate,
    lazy_ratio_input,
    lazy_recovery_prob,
    lazy_response_mean,
    lazy_response_std,
    packet_loss_input,
    random_seed_input,
    slots_per_epoch_input,
    total_validators_input,
):
    # Create configuration with ALL parameters in single struct
    config = SimulationConfig(
        # Basic parameters
        total_validators=total_validators_input.value,
        committee_size=committee_size_input.value,
        epochs_to_simulate=epochs_input.value,
        slots_per_epoch=slots_per_epoch_input.value,
        aztec_slot_duration_seconds=aztec_slot_duration_input.value,
        honest_ratio=honest_ratio_input.value,
        lazy_ratio=lazy_ratio_input.value,
        byzantine_ratio=1.0 - honest_ratio_input.value - lazy_ratio_input.value,
        random_seed=random_seed_input.value,
        l1_submission_deadline_ms=l1_submission_deadline_input.value,
        # Network parameters
        base_latency_ms=base_latency_input.value,
        latency_variance_ms=latency_std_input.value,
        packet_loss_rate=packet_loss_input.value,
        # GossipSub parameters
        gossipsub_d=gossipsub_d.value,
        gossipsub_dlo=gossipsub_dlo.value,
        gossipsub_dhi=gossipsub_dhi.value,
        gossipsub_dlazy=gossipsub_dlazy.value,
        # Validator response time parameters
        honest_response_mean=honest_response_mean.value,
        honest_response_std=honest_response_std.value,
        lazy_response_mean=lazy_response_mean.value,
        lazy_response_std=lazy_response_std.value,
        byzantine_response_mean=byzantine_response_mean.value,
        byzantine_response_std=byzantine_response_std.value,
        # Behavior probability parameters
        honest_proposal_rate=honest_proposal_rate.value,
        honest_attestation_rate=honest_attestation_rate.value,
        honest_downtime_prob=honest_downtime_prob.value,
        honest_recovery_prob=honest_recovery_prob.value,
        honest_private_peer_prob=honest_private_peer_prob.value,
        lazy_proposal_rate=lazy_proposal_rate.value,
        lazy_attestation_rate=lazy_attestation_rate.value,
        lazy_downtime_prob=lazy_downtime_prob.value,
        lazy_recovery_prob=lazy_recovery_prob.value,
        lazy_private_peer_prob=lazy_private_peer_prob.value,
        byzantine_proposal_rate=byzantine_proposal_rate.value,
        byzantine_attestation_rate=byzantine_attestation_rate.value,
        byzantine_downtime_prob=byzantine_downtime_prob.value,
        byzantine_recovery_prob=byzantine_recovery_prob.value,
        byzantine_private_peer_prob=byzantine_private_peer_prob.value,
    )

    # Calculate consensus threshold
    consensus_threshold = (config.committee_size * 2 // 3) + 1

    # Display configuration
    print(f"Configuration:")
    print(f"  Total validators: {config.total_validators}")
    print(f"  Committee size: {config.committee_size}")
    print(
        f"  Consensus threshold: {consensus_threshold} attestations ({consensus_threshold/config.committee_size:.1%})"
    )
    print(f"  Honest: {config.honest_ratio:.0%}")
    print(f"  Lazy: {config.lazy_ratio:.0%}")
    print(f"  Byzantine: {config.byzantine_ratio:.0%}")
    print(f"  Epochs: {config.epochs_to_simulate}")
    print(f"  Slots per epoch: {config.slots_per_epoch}")
    print(f"  Aztec slot duration: {config.aztec_slot_duration_seconds} seconds")
    print(f"  Total slots: {config.epochs_to_simulate * config.slots_per_epoch}")
    print(f"  Network latency: {config.base_latency_ms}±{config.latency_variance_ms}ms")
    print(f"  Packet loss: {config.packet_loss_rate:.1%}")
    print(f"  L1 submission deadline: {config.l1_submission_deadline_ms}ms")
    print(f"  Random seed: {config.random_seed}")
    print("\nBehavior Probabilities:")
    print(
        f"  Honest: proposal={config.honest_proposal_rate:.0%}, attest={config.honest_attestation_rate:.0%}, downtime={config.honest_downtime_prob:.1%}, recovery={config.honest_recovery_prob:.0%}, private={config.honest_private_peer_prob:.0%}"
    )
    print(
        f"  Lazy: proposal={config.lazy_proposal_rate:.0%}, attest={config.lazy_attestation_rate:.0%}, downtime={config.lazy_downtime_prob:.0%}, recovery={config.lazy_recovery_prob:.0%}, private={config.lazy_private_peer_prob:.0%}"
    )
    print(
        f"  Byzantine: proposal={config.byzantine_proposal_rate:.0%}, attest={config.byzantine_attestation_rate:.0%}, downtime={config.byzantine_downtime_prob:.0%}, recovery={config.byzantine_recovery_prob:.0%}, private={config.byzantine_private_peer_prob:.0%}"
    )
    return config, consensus_threshold


@app.cell
def _(config, consensus_threshold, mo):
    # Calculate total slots for display
    total_slots = config.epochs_to_simulate * config.slots_per_epoch

    # Create the run simulation button
    run_simulation_button = mo.ui.run_button(
        label="🚀 Run Simulation", kind="success", full_width=False
    )

    # Display configuration summary and button
    mo.vstack(
        [
            mo.md(
                f"""
            ## Simulation Ready

            **Configuration Summary:**

            - **{config.total_validators}** validators, committee size: **{config.committee_size}**
            - Consensus threshold: **{consensus_threshold}** attestations ({consensus_threshold / config.committee_size:.1%})
            - Validator mix: **{config.honest_ratio:.0%}** honest, **{config.lazy_ratio:.0%}** lazy, **{config.byzantine_ratio:.0%}** byzantine
            - **{config.epochs_to_simulate}** epoch(s), **{config.slots_per_epoch}** slots per epoch = **{total_slots}** total slots
            - Aztec slot duration: **{config.aztec_slot_duration_seconds}** seconds
            - Network latency: **{config.base_latency_ms}±{config.latency_variance_ms}ms**

            Click the button below to start the simulation:
            """
            ),
            mo.center(run_simulation_button),
        ]
    )

    return run_simulation_button, total_slots


@app.cell
def _(
    config,
    mo,
    run_simulation_button,
    run_simulation_with_analysis,
    time,
    total_slots,
):
    # Initialize variables
    df = None
    simulator = None

    # Only run simulation when button is clicked
    if run_simulation_button.value:
        # Run simulation with timing
        start_time = time.time()

        # Run simulation with a spinner
        with mo.status.spinner(
            title="Running Simulation",
            subtitle=f"Simulating {total_slots} slots with {config.total_validators} validators...",
        ):
            df, simulator = run_simulation_with_analysis(config)

        elapsed_time = time.time() - start_time

        # Display results
        print(f"\n✅ Simulation completed in {elapsed_time:.2f} seconds")
        print(
            f"📊 Generated {len(df):,} events ({len(df) / elapsed_time:.0f} events/sec)"
        )

        print(f"\n📋 Response Time Configuration Applied:")
        print(
            f"  Honest response: {config.honest_response_mean}±{config.honest_response_std}ms"
        )
        print(
            f"  Lazy response: {config.lazy_response_mean}±{config.lazy_response_std}ms"
        )
        print(
            f"  Byzantine response: {config.byzantine_response_mean}±{config.byzantine_response_std}ms"
        )

    (
        mo.md(
            f"""
        ## ✅ Simulation Complete!

        **Results:**
        - Completed in **{elapsed_time:.2f}** seconds
        - Generated **{len(df):,}** events ({len(df) / elapsed_time:.0f} events/sec)
        - All data ready for analysis below
        """
        )
        if run_simulation_button.value
        else None
    )
    return df, simulator


@app.cell(hide_code=True)
def _(config, df, mo, pl):
    def highlevel_overview(df):
        # Count attestations using Polars syntax
        attestation_created = df.filter(pl.col("event") == "ATTESTATION_CREATED")
        attestation_received = df.filter(pl.col("event") == "ATTESTATION_RECEIVED_P2P")
        proposers = df.filter(pl.col("event") == "PROPOSER_ASSIGNED")

        # L1 submission analysis
        slot_end = df.filter(pl.col("event") == "SLOT_END")
        l1_submissions = df.filter(pl.col("event") == "L1_SUBMISSION")

        submission_data = []

        if slot_end.height > 0:
            for row in slot_end.iter_rows(named=True):
                proposer, slot_start_time = (
                    proposers.filter(pl.col("slot") == row["slot"])
                    .select(["subject", "timestamp_ms"])
                    .row(0)
                )

                slot_data = {
                    "slot": row["slot"],
                    "proposer": proposer,
                    "status": "failed",
                    "attestations_in_time": 0,
                    "attestations_total": 0,
                    "attestations_global": 0,
                    "failure_reason": "no block proposed",
                    "cumulative_success": 0,
                }

                if row.get("data_block_proposed", False) not in [
                    "false",
                    "False",
                    False,
                ]:
                    submission = l1_submissions.filter(
                        pl.col("slot") == row["slot"]
                    ).row(0, named=True)
                    received = attestation_received.filter(
                        (pl.col("slot") == row["slot"])
                        & (pl.col(name="subject") == proposer)
                    )

                    ## Adding 1 for itself.
                    if received.height > 0 and "data_attester" in received.columns:
                        total_received = 1 + len(received["data_attester"].unique())
                    else:
                        total_received = 1

                    if received.height > 0 and "data_attester" in received.columns:
                        received_in_time = 1 + len(
                            received.filter(
                                (pl.col("timestamp_ms") - slot_start_time)
                                < config.l1_submission_deadline_ms
                            )["data_attester"].unique()
                        )
                    else:
                        received_in_time = 1

                    slot_data.update(
                        {
                            "status": submission["status"],
                            "attestations_in_time": received_in_time,
                            "attestations_total": total_received,
                            "attestations_global": attestation_created.filter(
                                pl.col("slot") == submission["slot"]
                            ).height,
                            "failure_reason": (
                                submission.get("data_failure_reason", "-")
                                if submission.get("status") == "failed"
                                else "-"
                            ),
                        }
                    )

                submission_data.append(slot_data)

        # Calculate cumulative successes
        cumulative_success = 0
        for i, row in enumerate(submission_data):
            if row["status"] == "success":
                cumulative_success += 1
            submission_data[i]["cumulative_success"] = cumulative_success

        # Convert to pandas DataFrame for Altair
        submission_df = (
            pl.DataFrame(submission_data) if submission_data else pl.DataFrame()
        )

        return mo.vstack(
            [
                mo.md("# Overview"),
                mo.md(
                    f"""**Attestations created:** {attestation_created.height}. **Attestation messages received:** {attestation_received.height}"""
                ),
                mo.ui.table(submission_df),
            ]
        )

    highlevel_overview(df)
    return


@app.cell
def _(config, pl):
    def get_slots_with_proposals(df, epoch):
        """
        Get the number of slots that had block proposals in an epoch.
        """
        start_slot = epoch * config.slots_per_epoch
        end_slot = start_slot + config.slots_per_epoch

        block_proposals = df.filter(
            (pl.col("event_type") == "BLOCK_PROPOSED")
            & (pl.col("slot") >= start_slot)
            & (pl.col("slot") < end_slot)
        )

        # Return unique slots that had proposals
        return block_proposals["slot"].unique().to_list()

    def get_expected_attestations(df, epoch):
        """
        Get the expected number of attestations for an epoch based on actual proposals.
        Validators can only attest if there was a block proposed.
        """
        slots_with_proposals = get_slots_with_proposals(df, epoch)
        return len(slots_with_proposals)

    return (get_expected_attestations,)


@app.cell(hide_code=True)
def _(config, get_committee_members, get_expected_attestations, json, pl):
    def get_node_view(df, node):
        """
        Get the complete view of attestations from a node's perspective.
        This includes:
        1. Attestations received via P2P (from other validators)
        2. Own attestations created (since node doesn't receive its own)
        3. Attestations from L1 finalized blocks (global truth)
        """
        # Get attestations received from others via P2P
        p2p_attestations = df.filter(
            (pl.col("subject") == node)
            & (pl.col("event_type") == "ATTESTATION_RECEIVED_P2P")
        )

        if p2p_attestations.height > 0 and "data_attester" in p2p_attestations.columns:
            received_attestations = (
                p2p_attestations.select(
                    [
                        "timestamp_ms",
                        "slot",
                        "data_attester",
                        (
                            pl.col("data_hops").cast(pl.Int64)
                            if "data_hops" in p2p_attestations.columns
                            else pl.lit(1).cast(pl.Int64).alias("data_hops")
                        ),
                    ]
                )
                .rename({"data_attester": "attester"})
                .with_columns(pl.lit("p2p").alias("source"))
            )
        else:
            # Create empty dataframe with same schema
            received_attestations = pl.DataFrame(
                {
                    "timestamp_ms": [],
                    "slot": [],
                    "attester": [],
                    "data_hops": [],
                    "source": [],
                },
                schema={
                    "timestamp_ms": pl.Float64,
                    "slot": pl.Int64,
                    "attester": pl.Utf8,
                    "data_hops": pl.Int64,
                    "source": pl.Utf8,
                },
            )

        # Get own attestations created
        own_attestations = (
            df.filter(
                (pl.col("actor") == node)
                & (pl.col("event_type") == "ATTESTATION_CREATED")
            )
            .select(["timestamp_ms", "slot", "actor"])
            .rename({"actor": "attester"})
            .with_columns(
                [
                    pl.lit(0).cast(pl.Int64).alias("data_hops"),
                    pl.lit("own").alias("source"),
                ]
            )
        )

        # Get L1 finalized attestations (shared by all nodes)
        l1_finalized_events = df.filter(pl.col("event_type") == "L1_FINALIZED")

        # Check if we have L1 finalized events and if they have attestations
        if (
            l1_finalized_events.height > 0
            and "data_attestations" in l1_finalized_events.columns
        ):
            l1_attestations = (
                l1_finalized_events.with_columns(
                    [
                        pl.col("data_attestations")
                        .map_elements(
                            lambda x: json.loads(x) if isinstance(x, str) else x,
                            return_dtype=pl.List(pl.Utf8),
                        )
                        .alias("attesters_list")
                    ]
                )
                .explode("attesters_list")
                .select(["timestamp_ms", "slot", "attesters_list"])
                .rename({"attesters_list": "attester"})
                .with_columns(
                    [
                        pl.lit(None)
                        .cast(pl.Int64)
                        .alias("data_hops"),  # L1 doesn't have hops
                        pl.lit("l1").alias("source"),
                    ]
                )
            )
        else:
            # Create empty dataframe with same schema if no L1 attestations
            l1_attestations = pl.DataFrame(
                {
                    "timestamp_ms": [],
                    "slot": [],
                    "attester": [],
                    "data_hops": [],
                    "source": [],
                },
                schema={
                    "timestamp_ms": pl.Float64,
                    "slot": pl.Int64,
                    "attester": pl.Utf8,
                    "data_hops": pl.Int64,
                    "source": pl.Utf8,
                },
            )

        # Combine all three views
        combined_view = pl.concat(
            [received_attestations, own_attestations, l1_attestations]
        )

        # Add deadline and in_time calculations
        node_view = (
            combined_view.with_columns(
                [
                    (
                        pl.col("slot") * config.aztec_slot_duration_seconds * 1000
                        + config.l1_submission_deadline_ms
                    ).alias("deadline")
                ]
            )
            .with_columns(
                [(pl.col("timestamp_ms") < pl.col("deadline")).alias("in_time")]
            )
            .sort("timestamp_ms")
            # Keep first occurrence per slot/attester/source combo
            .unique(subset=["slot", "attester"], keep="first")
            .sort("timestamp_ms")
        )

        return node_view

    def get_node_summary_view(df, node, epoch):
        """
        Use the global view of created attestations do outline number of created and missed attestations for every validator in the committee for the epoch.
        """
        committee_members = get_committee_members(df, epoch)
        df_epoch = df.filter(pl.col("slot") // config.slots_per_epoch == epoch)
        df_epoch = get_node_view(df_epoch, node)
        expected_attestations = get_expected_attestations(df, epoch)

        # Aggregate attestations per validator
        attestation_summary = df_epoch.group_by("attester").agg(
            pl.col("slot").count().alias("created")
        )

        # Create DataFrame with all committee members
        all_members = pl.DataFrame({"attester": committee_members})

        # Left join to include all committee members
        result = (
            all_members.join(attestation_summary, on="attester", how="left")
            .with_columns(
                [
                    # Fill nulls with 0 for members who didn't attest
                    pl.col("created").fill_null(0),
                    # Calculate missed slots
                    (expected_attestations - pl.col("created").fill_null(0)).alias(
                        "missed"
                    ),
                ]
            )
            .with_columns(
                [
                    (pl.col("missed") / (pl.col("missed") + pl.col("created"))).alias(
                        "fraction_missed"
                    )
                ]
            )
        )

        # Sort by performance (most created first)
        result = result.sort("created", descending=True)

        return result

    return get_node_summary_view, get_node_view


@app.cell
def _(mo):
    mo.md(
        r"""
    # Slashing 

    In this section we are going to look deeper into slashing itself. We will try to emulate how the nodes in the network propose, and come to agreement on what was proposed. Our main point of interest is really the inactivity case, because this is the least clear variant.

    The flow is fairly simple:

    1. For every slot check if the `proposer` is online
    2. The proposer derives a proposal that he would pick if he was to make a new one
    3. He computes a `score` for the new proposal and every existing proposal
    4. He signal on the proposal with the best `score`, if this is his own new, the payload is created as well.

    The current mechanism used to derive the proposal that he wish to propose is very simple, and follows one of the cases that we have in the node (somewhat):

    1. For the last finished epoch, build a summary of every committee member
    2. Collect all the members that have missed all their attestations for blocks that were produced, put them in the payload

    The real point of interest in the following sections are how altering just the heuristic can alter the signalling outcomes.
    """
    )
    return


@app.cell
def _(get_node_summary_view, pl):
    def will_propose(df, node, epoch):
        """
        Who would we propose if we were the only girl in the world
        """
        potential_criminals = (
            get_node_summary_view(df, node, epoch)
            .filter(pl.col("fraction_missed") >= 1)["attester"]
            .sort()
            .to_list()
        )

        if len(potential_criminals) > 0:
            return frozenset(potential_criminals)
        return None

    return (will_propose,)


@app.cell
def _(config, df, hashlib, heapq, mo, pl, round_size_input, will_propose):
    # We try not to be too smart here, but just have it kinda run.
    ROUND_SIZE = round_size_input.value

    def get_proposal_id(proposal):
        return hashlib.md5(",".join(proposal).encode()).hexdigest()[:8]

    def build_signal_df(heuristic):
        signals_df = pl.DataFrame(
            {
                "slot": [],
                "round": [],
                "proposer": [],
                "proposal": [],
                "proposal_id": [],
            },
            schema={
                "slot": pl.Int64,
                "round": pl.Int64,
                "proposer": pl.Utf8,
                "proposal": pl.List(pl.Utf8),
                "proposal_id": pl.Utf8,
            },
        )

        node_active_df = df.filter(
            (pl.col("event_type").is_in(["NODE_OFFLINE", "NODE_ONLINE"]))
        )

        def is_validator_online(validator, slot):
            t = node_active_df.filter(
                (pl.col("actor") == validator) & (pl.col("slot") <= slot)
            ).sort("slot")

            if t.is_empty():
                return True

            return t.tail(1)["event_type"].item() == "NODE_ONLINE"

        # Calculate total slots to process
        total_epochs = config.epochs_to_simulate - 1
        total_slots = total_epochs * config.slots_per_epoch

        # Generate all slot combinations
        slot_list = []
        for epoch in range(1, config.epochs_to_simulate):
            for i in range(config.slots_per_epoch):
                slot_list.append((epoch, i))

        # Use progress bar as an iterable
        for slot_idx, (epoch, i) in mo.status.progress_bar(
            enumerate(slot_list),
            total=total_slots,
            title="Building slashing signals",
            subtitle=f"Processing {total_slots} slots",
        ):
            slot = epoch * config.slots_per_epoch + i

            t = (
                df.filter(pl.col("event") == "PROPOSER_ASSIGNED")
                .filter(pl.col("slot") == slot)
                .select(["subject"])
            )

            if t.is_empty():
                continue

            (proposer,) = t.row(0)

            if not is_validator_online(proposer, slot):
                continue

            def h(proposal):
                return heuristic(df, proposer, slot, proposal, signals_df)

            # Make a new proposal based on the last epoch.
            new_proposal = will_propose(df, proposer, epoch - 1)

            # Get all unique proposals that have been signaled before. Note this implies only proposals by proposers are of interest.
            previous_proposals = set()

            if signals_df.height > 0:
                for row in signals_df.iter_rows(named=True):
                    if row["proposal"]:
                        previous_proposals.add(frozenset(sorted(row["proposal"])))

            # Build priority queue with all proposals
            pq = []

            if new_proposal:
                score = h(new_proposal)
                if score < 0:
                    heapq.heappush(pq, (score, new_proposal))

            for proposal in previous_proposals:
                score = h(proposal)
                if score < 0:
                    heapq.heappush(pq, (score, proposal))

            # Take the best of the proposals and signal that
            # Note that as `previous_proposals` are built using the dataframe, this means that the only historical proposlas
            # that is taken into account is proposals made by proposers and then signalled on. This is similar to the proposer
            # creating the proposal an instantly signalling on it.
            if len(pq) > 0:
                to_signal = heapq.heappop(pq)[1]
                proposal_list = sorted(list(to_signal)) if to_signal else []
                proposal_id = get_proposal_id(proposal_list)

                # Append new row to signals_df
                new_row = pl.DataFrame(
                    {
                        "slot": [slot],
                        "round": [slot // ROUND_SIZE],
                        "proposer": [proposer],
                        "proposal": [proposal_list],
                        "proposal_id": [proposal_id],
                    }
                )
                signals_df = pl.concat([signals_df, new_row])
        return signals_df

    return ROUND_SIZE, build_signal_df, get_proposal_id


@app.cell(hide_code=True)
def _(alt, config, mo, pd, pl):
    def visualize_cumulative_votes(signals_df, selected_round=0):
        # Filter for selected round
        round_df = signals_df.filter(pl.col("round") == selected_round)

        if round_df.height == 0:
            return mo.md(f"No votes found for round {selected_round}")

        # Convert proposals to hashable format and create unique IDs
        round_df = round_df.with_columns(
            [pl.col("proposal").list.sort().list.join(",").alias("proposal_str")]
        )

        # Get unique proposals with their IDs
        unique_proposals = (
            round_df.select(["proposal_str", "proposal_id"])
            .unique()
            .sort("proposal_str")
        )

        first_vote_slots = (
            round_df.group_by(["proposal_str", "proposal_id"])
            .agg(pl.col("slot").min().alias("first_slot"))
            .sort("first_slot")
        )

        # Get all slots where votes occurred
        slot_points = round_df.select(["slot", "proposer"]).unique().sort("slot")

        # Build cumulative data
        cumulative_data = []

        for slot, proposer in slot_points.iter_rows():
            # Count votes up to this slot
            votes_up_to_slot = round_df.filter(pl.col("slot") <= slot)
            vote_counts = votes_up_to_slot.group_by("proposal_id").agg(
                pl.len().alias("count")
            )

            for row in unique_proposals.iter_rows(named=True):
                proposal_str = row["proposal_str"]
                proposal_id = row["proposal_id"]

                # Get first vote slot for this proposal
                first_slot = first_vote_slots.filter(
                    pl.col("proposal_id") == proposal_id
                )["first_slot"][0]

                # Only add data point if this proposal has received its first vote
                if slot >= first_slot:
                    count = vote_counts.filter(pl.col("proposal_id") == proposal_id)
                    cumulative_votes = count["count"][0] if count.height > 0 else 0

                    # Parse proposal back to get validator count
                    validators = proposal_str.split(",") if proposal_str else []

                    # Create display label with ID to ensure uniqueness
                    display_label = (
                        f"[{proposal_id}] {validators[0][:10]}..."
                        if validators
                        else f"[{proposal_id}]"
                    )

                    cumulative_data.append(
                        {
                            "slot": slot,
                            "epoch": slot // config.slots_per_epoch,
                            "proposer": proposer,
                            "proposal_display": display_label,  # Unique display name
                            "proposal_id": proposal_id,
                            "proposal_full": proposal_str,
                            "cumulative_votes": cumulative_votes,
                            "validator_count": len(validators),
                            "validators": ", ".join(validators[:3])
                            + ("..." if len(validators) > 3 else ""),
                        }
                    )

        # Convert to pandas for Altair
        plot_df = pd.DataFrame(cumulative_data)

        if plot_df.empty:
            return mo.md("No data to visualize")

        # Get actual slot range
        min_slot = plot_df["slot"].min()
        max_slot = plot_df["slot"].max()

        # Calculate epoch boundaries
        min_epoch = min_slot // config.slots_per_epoch
        max_epoch = max_slot // config.slots_per_epoch + 1
        epoch_boundaries = [
            epoch * config.slots_per_epoch
            for epoch in range(min_epoch, max_epoch + 1)
            if min_slot - 10 <= epoch * config.slots_per_epoch <= max_slot + 10
        ]

        # Create the step chart
        base_chart = (
            alt.Chart(plot_df)
            .mark_line(interpolate="step-after", point=True)
            .encode(
                x=alt.X(
                    "slot:Q",
                    title="Slot Number",
                    scale=alt.Scale(domain=[min_slot, max_slot]),
                ),
                y=alt.Y("cumulative_votes:Q", title="Cumulative Votes"),
                color=alt.Color(
                    "proposal_display:N",  # Use the unique display name
                    title="Proposal",
                    legend=alt.Legend(orient="bottom", columns=2),
                ),
                tooltip=[
                    alt.Tooltip("slot:Q", title="Slot"),
                    alt.Tooltip("epoch:Q", title="Epoch"),
                    alt.Tooltip("proposer:N", title="Proposer"),
                    alt.Tooltip("cumulative_votes:Q", title="Total Votes"),
                    alt.Tooltip("proposal_id:N", title="Proposal ID"),
                    alt.Tooltip("validator_count:Q", title="Validators to Slash"),
                    alt.Tooltip("validators:N", title="Validators (first 3)"),
                    alt.Tooltip("proposal_full:N", title="Full Proposal"),
                ],
            )
        )

        # Add epoch boundaries
        if epoch_boundaries:
            epoch_df = pd.DataFrame(
                {
                    "slot": epoch_boundaries,
                    "label": [
                        f"Epoch {slot // config.slots_per_epoch}"
                        for slot in epoch_boundaries
                    ],
                }
            )

            epoch_lines = (
                alt.Chart(epoch_df)
                .mark_rule(strokeDash=[3, 3], opacity=0.5)
                .encode(
                    x=alt.X("slot:Q", scale=alt.Scale(domain=[min_slot, max_slot])),
                    tooltip=["label:N"],
                )
            )

            chart = (
                (epoch_lines + base_chart)
                .properties(
                    title=f"Cumulative Votes per Proposal in Round {selected_round}",
                )
                .interactive()
            )
        else:
            chart = base_chart.properties(
                title=f"Cumulative Votes per Proposal in Round {selected_round}",
            ).interactive()

        # Add summary statistics with proposal IDs
        summary = (
            round_df.group_by(["proposal_id", "proposal_str"])
            .agg(
                [
                    pl.len().alias("total_votes"),
                    pl.col("slot").min().alias("first_vote_slot"),
                    pl.col("slot").max().alias("last_vote_slot"),
                ]
            )
            .with_columns(
                [
                    # Add validator count for summary
                    pl.col("proposal_str")
                    .str.split(",")
                    .list.len()
                    .alias("validator_count")
                ]
            )
            .select(
                [
                    "proposal_id",
                    "validator_count",
                    "total_votes",
                    "first_vote_slot",
                    "last_vote_slot",
                ]
            )
            .sort("total_votes", descending=True)
        )

        return mo.vstack(
            [chart, mo.md("### Vote Summary"), mo.ui.table(summary, page_size=3)]
        )

    return (visualize_cumulative_votes,)


@app.cell
def _(mo):
    mo.md(
        r"""
    ## Current Heuristic

    The current heuristic is fairly simple:

    1. Consider if you agree with the proposal
        1. I agree if all of the members in the proposals in one of the last `n` epochs have all missed `>=` 75%
    2. Score the proposal based solely on the amount slashed (the length of the proposal) 


    The payload creation and agreement here practically means that we will not try to slash "across" committees.
    """
    )
    return


@app.cell
def _(build_signal_df, config, get_node_summary_view, mo, pl):
    def will_agree(df, node, current_epoch, suggested, lookback_epochs=50):
        """
        Return a true if we agree, and false otherwise
        Really simple implementation, not taking efficiency into account at all here.
        """
        suggested_df = pl.DataFrame({"attester": list(suggested)})

        start_epoch = max(0, current_epoch - lookback_epochs + 1)

        for epoch in range(start_epoch, current_epoch + 1):
            temp = get_node_summary_view(df, node, epoch)

            agree_count = (
                suggested_df.join(temp, on="attester", how="left")
                .with_columns([(pl.col("fraction_missed") >= 0.75).alias("agree")])[
                    "agree"
                ]
                .sum()
            )

            if len(suggested) == agree_count:
                return True

        return False

    def current_heuristic(df, proposer, current_slot, proposal, signals_df):
        """
        The current heuristic, take the largest slash you agree with
        """

        current_epoch = current_slot // config.slots_per_epoch

        if not (will_agree(df, proposer, current_epoch - 1, proposal)):
            return 0
        return -len(proposal)

    # Use it with your signals DataFrame
    signals_df = build_signal_df(current_heuristic)

    # Show a completion message briefly
    mo.md(f"✅ **Slashing signals built** - Generated {len(signals_df)} proposals")
    return signals_df, will_agree


@app.cell
def _(mo, signals_df):
    # Create round selector
    max_round = signals_df["round"].max() if signals_df.height > 0 else 0
    round_selector = mo.ui.number(
        start=0, stop=max_round, value=0, label="Select Round"
    )
    round_selector
    return (round_selector,)


@app.cell
def _(mo, round_selector, signals_df, visualize_cumulative_votes):
    mo.vstack(
        [
            mo.md("### Current Heuristic"),
            visualize_cumulative_votes(signals_df, round_selector.value),
        ]
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
    ## Heuristic accounting for existing signals

    This heuristic is also very simple. It uses the same agreement as before. And really only change the scoring. 
    The score is altered on two important points:

    1. Proposals get discarded if it is impossible for them to reach qourum, e.g., there are not sufficient signals left in the round
    2. The number of signals already on the proposal is taken into account, adding a multiplier of `(signals + 1) ** 0.1` to length of the proposal
    """
    )
    return


@app.cell
def _(
    ROUND_SIZE,
    build_signal_df,
    config,
    get_proposal_id,
    mo,
    pl,
    will_agree,
):
    def new_heuristic(df, proposer, slot, proposal, signals_df):
        current_epoch = slot // config.slots_per_epoch

        # If we disagree, don't both voting for it
        if not (will_agree(df, proposer, current_epoch - 1, proposal)):
            return 0

        round = slot // ROUND_SIZE
        left_in_round = ROUND_SIZE - (slot - round * ROUND_SIZE)

        proposal_list = sorted(proposal) if proposal else []
        proposal_id = get_proposal_id(proposal_list)

        votes = signals_df.filter(
            (pl.col("round") == round) & (pl.col("proposal_id") == proposal_id)
        ).height

        # If it is impossible for the proposal to reach the quorum, don't bother
        if 1 + votes + left_in_round <= ROUND_SIZE / 2:
            return 0

        v = float(votes + 1) ** 0.1 * float(len(proposal))

        return -v

    signals_df_2 = build_signal_df(new_heuristic)

    # Show a completion message briefly
    mo.md(f"✅ **Slashing signals built** - Generated {len(signals_df_2)} proposals")
    return (signals_df_2,)


@app.cell
def _(mo, round_selector, signals_df_2, visualize_cumulative_votes):
    mo.vstack(
        [
            mo.md("### New Heuristic"),
            visualize_cumulative_votes(signals_df_2, round_selector.value),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    # Deeper Analysis
    Below this point you are staring into the abyss. 

    This is the place where I have been looking to figure out if things were built somewhat correctly or get more specific insights into the views of the nodes or latency across the network.
    """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
    # Network Partition Analysis

    This section is focused on looking into the network topology and its impacts.
    """
    )
    return


@app.cell(hide_code=True)
def _(config, mo, simulator):
    # Get partition timeline for all slots
    partition_timeline = simulator.get_partition_timeline()

    # Calculate statistics
    total_slots_ = config.epochs_to_simulate * config.slots_per_epoch
    partitioned_slots = partition_timeline.filter(
        partition_timeline["is_partitioned"] == True
    )
    consensus_risk_slots = partition_timeline.filter(
        partition_timeline["can_reach_consensus"] == False
    )

    mo.vstack(
        [
            mo.md("## Network Partition Summary"),
            mo.md(
                f"""
            **Overall Statistics:**

            - Total slots simulated: {total_slots_}
            - Slots with network partitions: {len(partitioned_slots)} ({len(partitioned_slots) / total_slots_ * 100:.1f}%)
            - Slots where consensus was at risk: {len(consensus_risk_slots)} ({len(consensus_risk_slots) / total_slots_ * 100:.1f}%)
            - Average online validators: {partition_timeline["total_online"].mean():.1f}
            - Average offline validators: {partition_timeline["total_offline"].mean():.1f}
        """
            ),
            mo.ui.table(partition_timeline, page_size=10),
        ]
    )
    return (partition_timeline,)


@app.cell(hide_code=True)
def _(alt, mo, partition_timeline):
    # Create visualization of partition status over time

    # Convert to pandas for Altair
    timeline_df = partition_timeline.to_pandas()

    # Create line chart for online/offline validators
    online_chart = (
        alt.Chart(timeline_df)
        .mark_line(color="green")
        .encode(
            x=alt.X("slot:Q", title="Slot"),
            y=alt.Y("total_online:Q", title="Number of Validators"),
            tooltip=["slot:Q", "total_online:Q", "total_offline:Q"],
        )
    )

    offline_chart = (
        alt.Chart(timeline_df)
        .mark_line(color="red", strokeDash=[5, 5])
        .encode(x="slot:Q", y="total_offline:Q", tooltip=["slot:Q", "total_offline:Q"])
    )

    # Mark partitioned slots
    partition_marks = (
        alt.Chart(timeline_df[timeline_df["is_partitioned"]])
        .mark_rect(opacity=0.3, color="orange")
        .encode(
            x="slot:Q",
            x2=alt.X2(datum=alt.expr("datum.slot + 1")),
            tooltip=["slot:Q", "num_partitions:Q"],
        )
    )

    # Mark consensus risk slots
    risk_marks = (
        alt.Chart(timeline_df[~timeline_df["can_reach_consensus"]])
        .mark_rect(opacity=0.3, color="red")
        .encode(
            x="slot:Q",
            x2=alt.X2(datum=alt.expr("datum.slot + 1")),
            tooltip=["slot:Q"],
        )
    )

    combined_chart = (
        (partition_marks + risk_marks + online_chart + offline_chart)
        .properties(
            title="Network Health Over Time",
            height=500
        )
        .interactive()
    )

    mo.vstack(
        [
            mo.md("## Network Health Visualization"),
            mo.md(
                """
            **Legend:**

            - Green line: Online validators
            - Red dashed line: Offline validators  
            - Orange shading: Network is partitioned
            - Red shading: Consensus at risk
        """
            ),
            combined_chart,
        ]
    )
    return


@app.cell
def _(mo, simulator):
    # Create a slot selector for network visualization
    network_viz_slot = mo.ui.number(
        start=0,
        stop=simulator.config.epochs_to_simulate * simulator.config.slots_per_epoch - 1,
        value=0,
        step=1,
        label="Select Slot for Network Visualization",
    )

    mo.vstack(
        [
            mo.md("## Network Topology Visualization"),
            mo.md(
                "This section visualizes the actual P2P network topology, at a specific point in time"
            ),
            network_viz_slot,
        ]
    )
    return (network_viz_slot,)


@app.cell
def _(nx, simulator):
    def get_stable_network_pos(simulator):
        # Compute stable node positions once for all validators
        # This ensures consistent layout across different slots

        # Create a graph with all validators
        G_stable = nx.Graph()

        # Add all validator nodes
        for validator in simulator.validator_ids:
            G_stable.add_node(validator)

        # Add edges based on the initial network topology
        adjacency = simulator.network.adjacency_matrix
        validator_names = simulator.validator_ids

        for i in range(len(validator_names)):
            for j in range(i + 1, len(validator_names)):
                if adjacency[i, j] == 1:
                    G_stable.add_edge(validator_names[i], validator_names[j])

        # Compute positions using spring layout with fixed seed for consistency
        # Use more iterations for better layout
        stable_node_positions = nx.spring_layout(
            G_stable,
            k=3,  # Increase distance between nodes
            iterations=100,  # More iterations for better layout
            seed=42,  # Fixed seed for reproducibility
        )
        return stable_node_positions

    stable_node_positions = get_stable_network_pos(simulator)
    return (stable_node_positions,)


@app.cell
def _(alt, mo, network_viz_slot, nx, pd, simulator, stable_node_positions):
    def create_network_visualization(simulator, slot, node_positions):
        """Create an interactive network visualization using Altair."""

        height, width = 700, 800

        # Get network state and partition info
        state = simulator.get_network_state_at_slot(slot)
        partition_info = simulator.detect_partitions_networkx(slot)

        # Create a selection for synchronized tooltips
        # Temporarily disabled for debugging
        # hover_selection = alt.selection_point(
        #     fields=["validator"], on="mouseover", clear="mouseout", nearest=True
        # )

        # Create NetworkX graph
        G = nx.Graph()
        adjacency = state["adjacency_matrix"]
        online = state["online_validators"]
        validator_names = state["validator_names"]

        # Add nodes with attributes
        for i, validator in enumerate(validator_names):
            validator_obj = simulator.validators.get(validator)

            is_online = online[i]
            is_committee = validator in (
                simulator.current_committee.validators
                if simulator.current_committee
                else []
            )
            is_private = validator_obj.is_private if validator_obj else False
            behavior = validator_obj.profile.name if validator_obj else "UNKNOWN"

            G.add_node(
                validator,
                online=is_online,
                committee=is_committee,
                private=is_private,
                behavior=behavior,
                index=i,
            )

        # Add edges for online nodes
        for i in range(len(validator_names)):
            if online[i]:
                for j in range(i + 1, len(validator_names)):
                    if online[j] and adjacency[i, j] == 1:
                        G.add_edge(validator_names[i], validator_names[j])

        # Use the pre-computed stable positions
        pos = node_positions

        # Create node data for Altair
        node_data = []
        for node in G.nodes():
            attrs = G.nodes[node]

            # Determine partition for coloring
            partition_id = 0
            if partition_info["is_partitioned"] and attrs["online"]:
                for pid, p in enumerate(partition_info["partitions"]):
                    if node in p["validators"]:
                        partition_id = pid + 1
                        break

            # Create display label
            node_label = node[-4:]  # Last 4 chars of validator ID

            # Determine color based on behavior and status
            if not attrs["online"]:
                color_category = "Offline"
            elif attrs["behavior"] == "HONEST":
                color_category = (
                    "Honest (Private)" if attrs["private"] else "Honest (Public)"
                )
            elif attrs["behavior"] == "LAZY":
                color_category = (
                    "Lazy (Private)" if attrs["private"] else "Lazy (Public)"
                )
            else:
                color_category = (
                    "Byzantine (Private)" if attrs["private"] else "Byzantine (Public)"
                )

            node_data.append(
                {
                    "validator": node,
                    "label": node_label,
                    "x": pos[node][0],
                    "y": pos[node][1],
                    "behavior": attrs["behavior"],
                    "online": attrs["online"],
                    "committee": attrs["committee"],
                    "private": attrs["private"],
                    "color_category": color_category,
                    "partition": partition_id,
                    "size": 150 if attrs["committee"] else 80,
                }
            )

        # Create edge data for Altair
        edge_data = []
        for edge in G.edges():
            source_pos = pos[edge[0]]
            target_pos = pos[edge[1]]
            edge_data.append(
                {
                    "source": edge[0],
                    "target": edge[1],
                    "x": source_pos[0],
                    "y": source_pos[1],
                    "x2": target_pos[0],
                    "y2": target_pos[1],
                }
            )

        # Convert to DataFrames
        nodes_df = pd.DataFrame(node_data)
        edges_df = pd.DataFrame(edge_data) if edge_data else pd.DataFrame()

        # Color schemes
        behavior_colors = {
            "Honest (Public)": "#2ecc71",
            "Honest (Private)": "#82e0aa",
            "Lazy (Public)": "#e67e22",
            "Lazy (Private)": "#f8c471",
            "Byzantine (Public)": "#e74c3c",
            "Byzantine (Private)": "#f1948a",
            "Offline": "#bdc3c7",
        }

        partition_colors = [
            "#3498db",
            "#e74c3c",
            "#f39c12",
            "#2ecc71",
            "#9b59b6",
            "#1abc9c",
        ]

        # Create edge chart with thicker lines
        if not edges_df.empty:
            edge_chart = (
                alt.Chart(edges_df)
                .mark_rule(opacity=0.3, strokeWidth=2)  # Thicker edges
                .encode(
                    x=alt.X("x:Q", scale=alt.Scale(domain=[-1.5, 1.5]), axis=None),
                    y=alt.Y("y:Q", scale=alt.Scale(domain=[-1.5, 1.5]), axis=None),
                    x2="x2:Q",
                    y2="y2:Q",
                    color=alt.value("#7f8c8d"),  # Slightly darker gray
                )
            )
        else:
            edge_chart = alt.Chart(pd.DataFrame()).mark_point()  # Empty chart

        # Create behavior-colored node chart
        behavior_nodes = (
            alt.Chart(nodes_df)
            .mark_circle()
            .encode(
                x=alt.X("x:Q", scale=alt.Scale(domain=[-1.5, 1.5]), axis=None),
                y=alt.Y("y:Q", scale=alt.Scale(domain=[-1.5, 1.5]), axis=None),
                size=alt.Size("size:Q", scale=alt.Scale(range=[50, 200]), legend=None),
                color=alt.Color(
                    "color_category:N",
                    scale=alt.Scale(
                        domain=list(behavior_colors.keys()),
                        range=list(behavior_colors.values()),
                    ),
                    title="Node Type",
                ),
                tooltip=[
                    alt.Tooltip("label:N", title="Validator"),
                    alt.Tooltip("behavior:N", title="Behavior"),
                    alt.Tooltip("online:N", title="Online"),
                    alt.Tooltip("committee:N", title="Committee Member"),
                    alt.Tooltip("private:N", title="Private Node"),
                    alt.Tooltip("partition:Q", title="Partition ID"),
                ],
            )
            .properties(
                width=width, height=height, title="Network Topology by Behavior"
            )
        )

        # Create partition-colored node chart
        if partition_info["is_partitioned"]:
            partition_nodes = (
                alt.Chart(nodes_df[nodes_df["online"]])
                .mark_circle()
                .encode(
                    x=alt.X("x:Q", scale=alt.Scale(domain=[-1.5, 1.5]), axis=None),
                    y=alt.Y("y:Q", scale=alt.Scale(domain=[-1.5, 1.5]), axis=None),
                    size=alt.Size(
                        "size:Q", scale=alt.Scale(range=[50, 200]), legend=None
                    ),
                    color=alt.Color(
                        "partition:N",
                        scale=alt.Scale(
                            domain=list(range(len(partition_info["partitions"]) + 1)),
                            range=partition_colors[
                                : len(partition_info["partitions"]) + 1
                            ],
                        ),
                        title="Partition",
                    ),
                    tooltip=[
                        alt.Tooltip("label:N", title="Validator"),
                        alt.Tooltip("partition:Q", title="Partition"),
                        alt.Tooltip("committee:N", title="Committee Member"),
                    ],
                )
            )

            # Add offline nodes
            offline_nodes = (
                alt.Chart(nodes_df[~nodes_df["online"]])
                .mark_circle(opacity=0.3)
                .encode(
                    x=alt.X("x:Q", scale=alt.Scale(domain=[-1.5, 1.5]), axis=None),
                    y=alt.Y("y:Q", scale=alt.Scale(domain=[-1.5, 1.5]), axis=None),
                    size=alt.value(50),
                    color=alt.value("#bdc3c7"),
                    tooltip=[alt.Tooltip("label:N", title="Validator (Offline)")],
                )
            )

            partition_chart = (edge_chart + partition_nodes + offline_nodes).properties(
                width=width,
                height=height,
                title=f"Network Partitions ({partition_info['num_partitions']} partitions)",
            )
        else:
            # Highlight committee members when not partitioned
            committee_nodes = (
                alt.Chart(nodes_df[nodes_df["committee"] & nodes_df["online"]])
                .mark_circle()
                .encode(
                    x=alt.X("x:Q", scale=alt.Scale(domain=[-1.5, 1.5]), axis=None),
                    y=alt.Y("y:Q", scale=alt.Scale(domain=[-1.5, 1.5]), axis=None),
                    size=alt.value(150),
                    color=alt.value("#f39c12"),
                    tooltip=[
                        alt.Tooltip("label:N", title="Committee Member"),
                        alt.Tooltip("behavior:N", title="Behavior"),
                    ],
                )
            )

            non_committee = (
                alt.Chart(nodes_df[~nodes_df["committee"] & nodes_df["online"]])
                .mark_circle()
                .encode(
                    x=alt.X("x:Q", scale=alt.Scale(domain=[-1.5, 1.5]), axis=None),
                    y=alt.Y("y:Q", scale=alt.Scale(domain=[-1.5, 1.5]), axis=None),
                    size=alt.value(80),
                    color=alt.value("#3498db"),
                    tooltip=[
                        alt.Tooltip("label:N", title="Validator"),
                        alt.Tooltip("behavior:N", title="Behavior"),
                    ],
                )
            )

            offline_nodes = (
                alt.Chart(nodes_df[~nodes_df["online"]])
                .mark_circle(opacity=0.3)
                .encode(
                    x=alt.X("x:Q", scale=alt.Scale(domain=[-1.5, 1.5]), axis=None),
                    y=alt.Y("y:Q", scale=alt.Scale(domain=[-1.5, 1.5]), axis=None),
                    size=alt.value(50),
                    color=alt.value("#bdc3c7"),
                    tooltip=[alt.Tooltip("label:N", title="Validator (Offline)")],
                )
            )

            partition_chart = (
                edge_chart + non_committee + committee_nodes + offline_nodes
            ).properties(
                width=width,
                height=height,
                title="Network Connected (Committee in Orange)",
            )

        # Combine both views side by side
        combined_chart = (edge_chart + behavior_nodes) | partition_chart

        return combined_chart.interactive()

    # Generate the visualization with stable positions

    network_chart = create_network_visualization(
        simulator, network_viz_slot.value, stable_node_positions
    )

    # Get partition info for stats
    partition_details = simulator.detect_partitions_networkx(network_viz_slot.value)
    state = simulator.get_network_state_at_slot(network_viz_slot.value)

    # Calculate statistics
    committee_members = (
        simulator.current_committee.validators if simulator.current_committee else []
    )
    online_committee = sum(
        1
        for v in committee_members
        if state["online_validators"][state["validator_names"].index(v)]
    )
    private_nodes = sum(1 for v in simulator.validators.values() if v.is_private)

    stats_md = f"""
    **Network Statistics for Slot {network_viz_slot.value}:**

    - **Topology**: {"Partitioned" if partition_details["is_partitioned"] else "Connected"} | {partition_details["num_partitions"]} partition(s)
    - **Nodes**: {state["online_validators"].sum()}/{len(state["validator_names"])} online | {private_nodes} private (NAT)
    - **Committee**: {online_committee}/{len(committee_members)} online
    - **Edges**: {partition_details["graph_stats"]["total_edges"]} | Avg degree: {partition_details["graph_stats"]["average_degree"]:.1f}
    """

    if partition_details["is_partitioned"]:
        stats_md += "\n**Partition Sizes**: " + ", ".join(
            [
                f"P{i + 1}: {p['size']} nodes ({p.get('committee_members', 0)} committee)"
                for i, p in enumerate(partition_details["partitions"])
            ]
        )

    mo.vstack([mo.md(stats_md), network_chart])
    return


@app.cell
def _(alt, config, df, get_committee_members, mo, network_viz_slot, pd, pl):
    def create_attestation_timeline(df, slot, deadline_ms):
        """Create an attestation timeline visualization."""
        # Get attestation events for the selected slot
        slot_events_viz = df.filter(pl.col("slot") == slot)

        if slot_events_viz.height == 0:
            return mo.md("No events available for visualization")

        slot_start_viz = slot_events_viz["timestamp_ms"].min()

        # Prepare data for heatmap
        attestation_events = df.filter(
            (pl.col("event") == "ATTESTATION_RECEIVED_P2P") & (pl.col("slot") == slot)
        )

        if attestation_events.height == 0:
            return mo.md("No attestation data available for visualization")

        attestation_events = attestation_events.with_columns(
            [
                ((pl.col("timestamp_ms") - slot_start_viz)).alias("relative_ms"),
                ((pl.col("timestamp_ms") - slot_start_viz) < deadline_ms).alias(
                    "in_time"
                ),
            ]
        )

        # Sample validators for visualization
        sample_validators = get_committee_members(df, slot)
        attestation_sample = attestation_events.filter(
            pl.col("subject").is_in(sample_validators)
        )

        # Create heatmap data
        heatmap_data = []
        for row in attestation_sample.iter_rows(named=True):
            heatmap_data.append(
                {
                    "receiver": row["subject"][-4:],  # Last 4 chars of validator ID
                    "attester": (
                        row["attester"][-4:] if row["attester"] else "unknown"
                    ),
                    "time_ms": row["relative_ms"],
                    "in_time": row["in_time"],
                }
            )

        # Convert to pandas for Altair visualization
        heatmap_df = pd.DataFrame(heatmap_data)

        # Create scatter plot showing attestation arrival times
        attestation_chart = (
            alt.Chart(heatmap_df)
            .mark_circle(size=50)
            .encode(
                x=alt.X(
                    "time_ms:Q",
                    title="Time (ms)",
                    scale=alt.Scale(domain=[0, 36000]),
                ),
                y=alt.Y("receiver:N", title="Validator (receiver)"),
                color=alt.Color(
                    "in_time:N",
                    title="In Time for L1",
                    scale=alt.Scale(domain=[True, False], range=["green", "red"]),
                ),
                tooltip=["receiver:N", "attester:N", "time_ms:Q", "in_time:N"],
            )
            .properties(
                title=f"Attestation Receipt Timeline for Slot {slot}",
                height=500
            )
        )

        # Add vertical line at submission deadline
        deadline_line = (
            alt.Chart(pd.DataFrame({"x": [deadline_ms]}))
            .mark_rule(color="orange", strokeDash=[5, 5])
            .encode(
                x=alt.X(
                    "x:Q",
                    scale=alt.Scale(domain=[0, 36000]),
                )
            )
        )

        return (attestation_chart + deadline_line).interactive()

    mo.vstack(
        [
            mo.md("#### Attestation Timeline Heatmap"),
            create_attestation_timeline(
                df, network_viz_slot.value, config.l1_submission_deadline_ms
            ),
        ]
    )
    return


@app.cell
def _(mo):
    mo.md(r"""# Network Views""")
    return


@app.cell
def _(mo):
    mo.md(
        r"""
    ## Global View

    We create a view of who created attestations using the creation events to get the "true" setup.
    """
    )
    return


@app.cell
def _(config, mo):
    # Selector for slot to analyze
    epoch_selector = mo.ui.number(
        start=0,
        stop=config.epochs_to_simulate - 1,
        value=0,
        step=1,
        label="Select Epoch to Analyze",
    )

    mo.vstack([mo.md("**Select an epoch to analyze:**"), epoch_selector])
    return (epoch_selector,)


@app.cell
def _(
    config,
    df,
    epoch_selector,
    get_committee_members,
    get_expected_attestations,
    pl,
):
    def get_global_creation_view(df):
        """
        Get the created attestations received attestation messages for the specified node
        """
        node_view = (
            (
                df.filter((pl.col("event_type") == "ATTESTATION_CREATED"))
                .select(["timestamp_ms", "slot", "attester"])
                .with_columns(
                    [
                        (
                            pl.col("slot") * config.aztec_slot_duration_seconds * 1000
                            + config.l1_submission_deadline_ms
                        ).alias("deadline")
                    ]
                )
                .with_columns(
                    [(pl.col("timestamp_ms") < pl.col("deadline")).alias("in_time")]
                )
            )
            .sort("timestamp_ms")
            .unique(subset=["slot", "attester"], keep="first")
            .sort("timestamp_ms")
        )

        return node_view

    def get_global_summary_view(df, epoch):
        """
        Use the global view of created attestations do outline number of created and missed attestations for every validator in the committee for the epoch.
        """
        committee_members = get_committee_members(df, epoch)
        df_epoch = df.filter(pl.col("slot") // config.slots_per_epoch == epoch)
        df_epoch = get_global_creation_view(df_epoch)
        expected_attestations = get_expected_attestations(df, epoch)

        # Aggregate attestations per validator
        attestation_summary = df_epoch.group_by("attester").agg(
            pl.col("slot").count().alias("created")
        )

        # Create DataFrame with all committee members
        all_members = pl.DataFrame({"attester": committee_members})

        # Left join to include all committee members
        result = (
            all_members.join(attestation_summary, on="attester", how="left")
            .with_columns(
                [
                    # Fill nulls with 0 for members who didn't attest
                    pl.col("created").fill_null(0),
                    # Calculate missed slots
                    (expected_attestations - pl.col("created").fill_null(0)).alias(
                        "missed"
                    ),
                ]
            )
            .with_columns(
                [
                    (pl.col("missed") / (pl.col("missed") + pl.col("created"))).alias(
                        "fraction_missed"
                    )
                ]
            )
        )

        # Sort by performance (most created first)
        result = result.sort("created", descending=True)

        return result

    get_global_summary_view(df, epoch_selector.value)
    return (get_global_summary_view,)


@app.cell
def _(mo):
    mo.md(
        r"""
    ## Node views

    We use the messages that the node have seen to create a view of its world
    """
    )
    return


@app.cell
def _(config, mo):
    all_validators = [f"validator_{i:04d}" for i in range(config.total_validators)]

    # Create dropdown selector
    node_selector = mo.ui.dropdown(
        options=all_validators,
        value=all_validators[0] if all_validators else None,
        label="Select Validator Node",
    )

    mo.vstack([mo.md("### Select a validator to analyze discrepancies"), node_selector])
    return (node_selector,)


@app.cell
def _(
    df,
    epoch_selector,
    get_node_summary_view,
    get_node_view,
    mo,
    node_selector,
):
    mo.vstack(
        [
            mo.md(f"### View for {node_selector.value}"),
            mo.ui.table(data=get_node_view(df, node_selector.value)),
            mo.md("#### Summary View"),
            mo.ui.table(
                data=get_node_summary_view(
                    df, node_selector.value, epoch_selector.value
                )
            ),
        ]
    )
    return


@app.cell
def _(mo):
    mo.md(r"""### Discrepency between the global view and the view of the node""")
    return


@app.cell
def _(
    config,
    get_global_summary_view,
    get_node_summary_view,
    get_node_view,
    pl,
):
    def get_discrepency_summary_view(df, node, epoch):
        global_summary = get_global_summary_view(df, epoch)
        node_summary = get_node_summary_view(df, node, epoch)

        # Find validators where counts differ
        return (
            global_summary.join(node_summary, on="attester", how="full", suffix="_node")
            .with_columns(
                [
                    (pl.col("created") != pl.col("created_node")).alias(
                        "has_discrepancy"
                    ),
                ]
            )
            .filter(pl.col("has_discrepancy"))
            .drop(["attester_node", "has_discrepancy"])
        )

    def get_discrepancy_detail_view(df, node, validator, epoch):
        """
        Get detailed view of attestation discrepancies for a specific validator.
        Shows exactly which slots are seen differently between global and node views.
        """
        # Get epoch data
        df_epoch = df.filter(pl.col("slot") // config.slots_per_epoch == epoch)

        # Global view - what actually happened
        global_attestations = (
            df_epoch.filter(
                (pl.col("event_type") == "ATTESTATION_CREATED")
                & (pl.col("actor") == validator)
            )
            .select(["slot", "timestamp_ms"])
            .with_columns(pl.lit("created").alias("global_status"))
        )

        # Node view - what the node saw
        node_view_df = get_node_view(df_epoch, node)
        node_attestations = (
            node_view_df.filter(pl.col("attester") == validator)
            .select(
                [
                    "slot",
                    "timestamp_ms",
                    (
                        pl.col("data_hops")
                        if "data_hops" in node_view_df.columns
                        else pl.lit(None).cast(pl.Int64).alias("data_hops")
                    ),
                ]
            )
            .with_columns(pl.lit("seen").alias("node_status"))
        )

        detail = (
            global_attestations.join(
                node_attestations, on="slot", how="full", suffix="_node"
            )
            .with_columns(
                [
                    pl.when(pl.col("global_status").is_null())
                    .then(pl.lit("not_created"))
                    .otherwise(pl.col("global_status"))
                    .alias("global_status"),
                    pl.when(pl.col("node_status").is_null())
                    .then(pl.lit("not_seen"))
                    .otherwise(pl.col("node_status"))
                    .alias("node_status"),
                    (pl.col("timestamp_ms_node") - pl.col("timestamp_ms")).alias(
                        "propagation_delay_ms"
                    ),
                ]
            )
            .select(
                [
                    "slot",
                    "global_status",
                    "node_status",
                    "timestamp_ms",
                    "timestamp_ms_node",
                    "propagation_delay_ms",
                    "data_hops",
                ]
            )
        )

        return detail.sort("slot")

    return get_discrepancy_detail_view, get_discrepency_summary_view


@app.cell
def _(df, epoch_selector, get_discrepency_summary_view, mo, node_selector):
    discrepancy_summary = get_discrepency_summary_view(
        df, node_selector.value, epoch_selector.value
    )
    discrepancy_focus = discrepancy_summary["attester"].to_list()

    # Create dropdown selector
    discrepancy_focus_selector = mo.ui.dropdown(
        options=discrepancy_focus,
        value=discrepancy_focus[0] if discrepancy_focus else None,
        label="Select Validator Node For Discrepency Focus",
    )

    mo.vstack(
        [
            discrepancy_summary,
            mo.md("### Select a validator to analyze discrepancies"),
            discrepancy_focus_selector,
        ]
    )
    return (discrepancy_focus_selector,)


@app.cell
def _(
    df,
    discrepancy_focus_selector,
    epoch_selector,
    get_discrepancy_detail_view,
    node_selector,
):
    get_discrepancy_detail_view(
        df, node_selector.value, discrepancy_focus_selector.value, epoch_selector.value
    )
    return


if __name__ == "__main__":
    app.run()
