#!/usr/bin/env python3
"""
Deep dive into the ACA eligibility calculation corruption issue.
"""

from policyengine_us import Microsimulation
import numpy as np
import pandas as pd

def investigate_value_corruption():
    """Investigate how the eligibility values are getting corrupted."""
    
    dataset = "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5"
    
    print("=" * 60)
    print("INVESTIGATING VALUE CORRUPTION")
    print("=" * 60)
    
    # Create two simulations - one clean, one to corrupt
    sim_clean = Microsimulation(dataset=dataset)
    sim_corrupt = Microsimulation(dataset=dataset)
    
    # Get clean 2025 values
    print("\n1. CLEAN 2025 VALUES (no prior calculations):")
    print("-" * 40)
    eligible_2025_clean = sim_clean.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    clean_values = np.array(eligible_2025_clean[:20])
    print(f"First 20 values: {clean_values}")
    print(f"Unique values: {np.unique(clean_values)}")
    print(f"Sum: {eligible_2025_clean.sum()/1e6:.2f} million")
    
    # Corrupt the simulation by calculating 2026 first
    print("\n2. CALCULATING 2026 FIRST:")
    print("-" * 40)
    eligible_2026 = sim_corrupt.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    values_2026 = np.array(eligible_2026[:20])
    print(f"2026 first 20 values: {values_2026}")
    print(f"2026 sum: {eligible_2026.sum()/1e6:.2f} million")
    
    # Now get corrupted 2025 values
    print("\n3. CORRUPTED 2025 VALUES (after 2026 calc):")
    print("-" * 40)
    eligible_2025_corrupt = sim_corrupt.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    corrupt_values = np.array(eligible_2025_corrupt[:20])
    print(f"First 20 values: {corrupt_values}")
    print(f"Unique values in full array: {np.unique(np.array(eligible_2025_corrupt))}")
    print(f"Sum: {eligible_2025_corrupt.sum()/1e6:.2f} million")
    
    # Compare the values
    print("\n4. VALUE COMPARISON:")
    print("-" * 40)
    comparison_df = pd.DataFrame({
        'index': range(20),
        'clean_2025': clean_values,
        'corrupt_2025': corrupt_values,
        'difference': corrupt_values - clean_values,
        '2026_value': values_2026
    })
    print(comparison_df)
    
    # Analyze the pattern
    print("\n5. PATTERN ANALYSIS:")
    print("-" * 40)
    
    # Check if corrupt values are related to clean values
    clean_arr = np.array(eligible_2025_clean[:1000])
    corrupt_arr = np.array(eligible_2025_corrupt[:1000])
    values_2026_arr = np.array(eligible_2026[:1000])
    
    # Where clean is 0 and corrupt is not 0
    false_to_nonzero = (clean_arr == 0) & (corrupt_arr != 0)
    print(f"Cases where clean=0 but corrupt≠0: {false_to_nonzero.sum()}")
    
    # Where clean is 1 and corrupt is not 1
    true_to_different = (clean_arr == 1) & (corrupt_arr != 1)
    print(f"Cases where clean=1 but corrupt≠1: {true_to_different.sum()}")
    
    # Check if there's a pattern with 2026 values
    print(f"\nCorrelation with 2026 values:")
    
    # When 2026 is 0
    when_2026_is_0 = values_2026_arr == 0
    print(f"When 2026=0, corrupt 2025 values: {np.unique(corrupt_arr[when_2026_is_0])}")
    
    # When 2026 is 1
    when_2026_is_1 = values_2026_arr == 1
    if when_2026_is_1.any():
        print(f"When 2026=1, corrupt 2025 values: {np.unique(corrupt_arr[when_2026_is_1])}")
    
    # Check if corruption is additive
    print(f"\n6. CHECKING IF CORRUPTION IS ADDITIVE:")
    print("-" * 40)
    
    # It looks like corrupt values might be clean + something
    # Let's check if corrupt = clean + 2026 + 1 or similar
    potential_sum = clean_arr + values_2026_arr
    matches_sum = np.all(corrupt_arr[:100] == potential_sum[:100])
    print(f"corrupt = clean + 2026? {matches_sum}")
    
    potential_sum_plus_1 = clean_arr + values_2026_arr + 1
    matches_sum_plus_1 = np.all(corrupt_arr[:100] == potential_sum_plus_1[:100])
    print(f"corrupt = clean + 2026 + 1? {matches_sum_plus_1}")
    
    # Check a few other patterns
    potential_double = clean_arr * 2
    matches_double = np.all(corrupt_arr[:100] == potential_double[:100])
    print(f"corrupt = clean * 2? {matches_double}")
    
    # Manual inspection of pattern
    print(f"\n7. MANUAL PATTERN CHECK (first 10 non-zero corruptions):")
    print("-" * 40)
    
    non_zero_corrupt = corrupt_arr != 0
    indices = np.where(non_zero_corrupt)[0][:10]
    
    for idx in indices:
        print(f"Index {idx}: clean={clean_arr[idx]}, corrupt={corrupt_arr[idx]}, 2026={values_2026_arr[idx]}")
        
    # Check for cumulative effect
    print(f"\n8. CHECKING FOR CUMULATIVE EFFECT:")
    print("-" * 40)
    
    sim_multi = Microsimulation(dataset=dataset)
    
    # Calculate 2026 multiple times
    for i in range(3):
        _ = sim_multi.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    
    # Now check 2025
    eligible_2025_multi = sim_multi.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    multi_values = np.array(eligible_2025_multi[:20])
    
    print(f"After calculating 2026 three times, 2025 first 20 values: {multi_values}")
    print(f"Sum: {eligible_2025_multi.sum()/1e6:.2f} million")
    
    # Check if it's more corrupted
    if not np.array_equal(multi_values, corrupt_values):
        print("Values are DIFFERENT after multiple 2026 calculations!")
    else:
        print("Values are the SAME after multiple 2026 calculations")

if __name__ == "__main__":
    investigate_value_corruption()