# Aztec P2P Network Slashing Simulation

## Overview
Interactive simulation of the Aztec blockchain's peer-to-peer network to analyze validator behavior, consensus mechanisms, and potential slashing scenarios. Features a user-friendly notebook interface with real-time visualizations.

The main value of the notebook comes from the network simulation, and then being able to apply different slashing models on top of those events to see how they would behave. The models provided in here are somewhat following what we had in the repo prior to latest work, where payloads are created based on individual epochs.

## Architecture

### Core Components
- `events.py` - Event model and EventStore (single source of truth)
- `collector.py` - Records events during simulation with post-processing for L1 submission
- `models.py` - Core data models (Config, Block, Attestation, etc.)
- `network.py` - GossipSub P2P network simulation
- `validator.py` - Validator behavior profiles (Honest/Lazy/Byzantine)
- `committee.py` - Committee selection and proposer assignment

### Analysis Tools
- `simulation_notebook.py` - Full interactive simulation and analysis notebook
- `view_events.py` - Command-line event viewer with DataFrame support
- `simulator.py` - Core simulator class with network partition detection

## Key Design Principles

1. **Events are the single source of truth** - Everything is derived from the event stream
2. **Clean separation** - Core simulation only records events, transformers derive views
3. **Reproducible** - Same event stream always produces same results
4. **Debuggable** - Can replay events to see any validator's view at any timestamp

## Getting Started

### Prerequisites
- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/AztecProtocol/engineering-designs.git
cd docs/slashing-sim

# Install dependencies using uv
uv sync

# This creates a virtual environment and installs all required packages
uv venv
```

### Running the Simulation

```bash
# Launch the interactive simulation notebook
marimo run simulation_notebook.py

# This will open your browser with the simulation interface
# If browser doesn't open automatically, navigate to http://localhost:2718

# If you need to edit use
marimo edit simulation_notebook.py
```

That's it! The notebook will guide you through:
1. Configuring simulation parameters
2. Running the simulation
3. Exploring results with interactive visualizations

## Event Types

- **Simulation**: SIMULATION_START, EPOCH_START, SLOT_START/END
- **Committee**: COMMITTEE_SELECTED, PROPOSER_ASSIGNED  
- **Blocks**: BLOCK_PROPOSED, BLOCK_RECEIVED_P2P
- **Attestations**: ATTESTATION_CREATED, ATTESTATION_RECEIVED_P2P
- **L1**: L1_SUBMISSION (with status field), L1_FINALIZED

## Example Output

The `view_events.py` script shows:
1. **Key Events** - Block proposal, L1 submission, and finalization
2. **Validator Timeline** - What each validator sees with attestation count `[XX/48]`
3. **Event Summary** - Statistics on attestations and L1 submission
4. **DataFrame Export** - Events available as pandas DataFrame for analysis

## What You'll See in the Notebook

The simulation notebook provides:
- **Configuration sliders** to adjust network parameters
- **Run button** to start the simulation with progress indicators
- **Network visualizations** displaying validator connections and partitions
- **Slashing analysis** identifying misbehaving validators
- **Interactive charts** for exploring attestation patterns and timing

## Configuration Parameters

Key parameters you can adjust in the notebook:

### Network Settings
- **Total Validators**: Number of validators in the network (minimum 48)
- **Epochs to Simulate**: How many epochs to run (4 slots per epoch by default)
- **Network Latency**: Base latency and variance for message propagation

### Validator Mix
- **Honest/Lazy/Byzantine Ratios**: Must sum to 1.0
- **NAT Probabilities**: Percentage of each type behind NAT/firewall
- **Response Times**: Mean and standard deviation for each validator type

### Advanced Settings
- **GossipSub Parameters**: D, D_low, D_high, D_lazy for network topology
- **Downtime/Recovery Probabilities**: Node failure and recovery rates

Example programmatic config:
```python
from models import SimulationConfig

config = SimulationConfig(
    total_validators=100,
    epochs_to_simulate=10,
    honest_ratio=0.85,
    lazy_ratio=0.10,
    byzantine_ratio=0.05,
    random_seed=42  # For reproducible results
)
```

## Troubleshooting

- **Browser doesn't open**: Navigate manually to http://localhost:2718
- **Port already in use**: Run with `marimo run simulation_notebook.py --port 2719`
- **Dependencies missing**: Ensure you ran `uv sync` in the project root
- **Simulation takes too long**: Reduce validator count or epochs in configuration