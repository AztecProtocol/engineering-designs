#!/usr/bin/env python3
"""
Benchmark to compare performance with Polars
"""

import time
from models import SimulationConfig
from simulation import run_simulation

def benchmark_simulation():
    """Run simulation with different configurations and measure performance"""
    
    configs = [
        ("Small (50 validators, 1 epoch)", SimulationConfig(
            total_validators=50,
            epochs_to_simulate=1,
            slots_per_epoch=4
        )),
        ("Medium (100 validators, 2 epochs)", SimulationConfig(
            total_validators=100,
            epochs_to_simulate=2,
            slots_per_epoch=8
        )),
        ("Large (200 validators, 4 epochs)", SimulationConfig(
            total_validators=200,
            epochs_to_simulate=4,
            slots_per_epoch=16
        ))
    ]
    
    print("=" * 80)
    print("PERFORMANCE BENCHMARK WITH POLARS")
    print("=" * 80)
    
    for name, config in configs:
        print(f"\n{name}:")
        print(f"  Total slots: {config.epochs_to_simulate * config.slots_per_epoch}")
        
        start = time.time()
        df = run_simulation(config)
        elapsed = time.time() - start
        
        events_per_second = len(df) / elapsed
        slots_per_second = (config.epochs_to_simulate * config.slots_per_epoch) / elapsed
        
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Events: {len(df):,}")
        print(f"  Events/sec: {events_per_second:,.0f}")
        print(f"  Slots/sec: {slots_per_second:.1f}")

if __name__ == "__main__":
    benchmark_simulation()