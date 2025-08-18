"""
Simple simulation wrapper that takes a config and returns a DataFrame.
Now uses the Simulator class internally for better state management.
"""

from typing import Optional, Tuple
import polars as pl
from models import SimulationConfig
from simulator import AztecSimulator


def run_simulation(config: Optional[SimulationConfig] = None) -> pl.DataFrame:
    """
    Run a complete simulation with the given configuration.

    Args:
        config: SimulationConfig object. If None, uses default configuration.

    Returns:
        DataFrame containing all simulation events with derived fields
    """
    # Create and run simulator
    simulator = AztecSimulator(config)
    return simulator.run()


def run_simulation_with_analysis(config: Optional[SimulationConfig] = None) -> Tuple[pl.DataFrame, AztecSimulator]:
    """
    Run a simulation and return both the DataFrame and the simulator instance.
    This allows for advanced analysis like partition detection.

    Args:
        config: SimulationConfig object. If None, uses default configuration.

    Returns:
        Tuple of (DataFrame with events, AztecSimulator instance)
    """
    simulator = AztecSimulator(config)
    df = simulator.run()
    return df, simulator


def quick_simulation() -> pl.DataFrame:
    """
    Run a quick simulation with default settings for testing.

    Returns:
        DataFrame containing all simulation events
    """
    return run_simulation()


if __name__ == "__main__":
    # Run a quick test simulation
    df = quick_simulation()

    # Show some basic stats
    print(f"\nEvent distribution:")
    event_counts = df.group_by("event").count().sort("count", descending=True)
    for row in event_counts.head(10).iter_rows():
        print(f"  {row[0]}: {row[1]}")
