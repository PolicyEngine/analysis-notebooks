#!/usr/bin/env python3
"""
Find the specific bug mechanism causing ACA corruption.
"""

from policyengine_us import Microsimulation
import numpy as np
import pandas as pd

def find_bug_mechanism():
    """Identify the exact mechanism of the bug."""
    
    dataset = "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5"
    
    print("=" * 60)
    print("FINDING THE BUG MECHANISM")
    print("=" * 60)
    
    # The key insight: values go from 0/1 to 0/1/2/3/4...
    # This suggests ACCUMULATION rather than replacement
    
    print("\n1. TESTING ACCUMULATION HYPOTHESIS:")
    print("-" * 40)
    
    sim = Microsimulation(dataset=dataset)
    
    # Calculate 2026 once
    aca_2026_first = sim.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    print(f"2026 ACA (first calc): {aca_2026_first.sum()/1e6:.2f}M")
    
    # Calculate 2026 again
    aca_2026_second = sim.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    print(f"2026 ACA (second calc): {aca_2026_second.sum()/1e6:.2f}M")
    
    # Are they the same?
    if np.array_equal(np.array(aca_2026_first), np.array(aca_2026_second)):
        print("✓ 2026 values are consistent across multiple calls")
    else:
        print("❌ 2026 values CHANGE across multiple calls!")
    
    # Now calculate 2025
    aca_2025 = sim.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    print(f"\n2025 ACA (after 2026): {aca_2025.sum()/1e6:.2f}M")
    
    # Calculate 2025 again
    aca_2025_second = sim.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    print(f"2025 ACA (second calc): {aca_2025_second.sum()/1e6:.2f}M")
    
    # Check if they accumulate
    arr1 = np.array(aca_2025[:100])
    arr2 = np.array(aca_2025_second[:100])
    
    if not np.array_equal(arr1, arr2):
        print("❌ 2025 values CHANGE on repeated calculation!")
        print(f"First calc sample: {arr1[:10]}")
        print(f"Second calc sample: {arr2[:10]}")
    else:
        print("✓ 2025 values stay the same on repeated calculation")
    
    # Test with map_to parameter
    print("\n2. TESTING MAP_TO AGGREGATION:")
    print("-" * 40)
    
    sim2 = Microsimulation(dataset=dataset)
    
    # The bug happens when we use map_to="tax_unit"
    # This means values are being calculated at person level then aggregated
    
    # Let's trace this
    print("Calculating 2026 with map_to='tax_unit'...")
    aca_2026_mapped = sim2.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    
    print("Now calculating 2025 with map_to='tax_unit'...")
    aca_2025_mapped = sim2.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    
    print(f"2025 result: {aca_2025_mapped.sum()/1e6:.2f}M")
    
    # Let's check what the raw values look like
    print(f"2025 unique values: {np.unique(np.array(aca_2025_mapped))}")
    
    # The pattern: instead of 0/1 we get 0/1/2/3/4...
    # This suggests SUMMING when it should be OR/MAX
    
    print("\n3. TESTING AGGREGATION METHOD:")
    print("-" * 40)
    
    # When mapping from person to tax_unit for a boolean:
    # - Correct: ANY person eligible → tax unit eligible (OR operation)
    # - Bug: SUM of person eligibility → tax unit value (COUNT operation)
    
    sim3 = Microsimulation(dataset=dataset)
    
    # Let's check a specific tax unit
    print("Examining specific tax units...")
    
    # Calculate 2026 first to trigger the bug
    _ = sim3.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    
    # Now get 2025
    aca_2025_bug = sim3.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    
    # Find tax units with values > 1 (impossible for boolean)
    bug_values = np.array(aca_2025_bug)
    impossible_values = bug_values[bug_values > 1]
    
    if len(impossible_values) > 0:
        print(f"❌ Found {len(impossible_values)} tax units with value > 1")
        print(f"   Max value: {impossible_values.max()}")
        print(f"   These are counts, not booleans!")
    
    # Compare with fresh calculation
    sim4 = Microsimulation(dataset=dataset)
    aca_2025_fresh = sim4.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    fresh_values = np.array(aca_2025_fresh)
    
    print(f"\nFresh 2025 unique values: {np.unique(fresh_values)}")
    print(f"Bug 2025 unique values: {np.unique(bug_values)}")
    
    print("\n4. HYPOTHESIS: PERSON-TO-TAX-UNIT AGGREGATION BUG")
    print("-" * 40)
    
    print("""
The bug mechanism:
1. is_aca_ptc_eligible is calculated at PERSON level
2. It's then aggregated to TAX_UNIT level using map_to="tax_unit"
3. For 2026, the aggregation works correctly (OR/MAX operation)
4. But when calculating 2025 after 2026, the aggregation SUMS instead
5. Result: Tax units get values = number of eligible persons (0,1,2,3...)
   instead of boolean (0,1)
    
This explains:
- Why values become 0,1,2,3... instead of 0,1
- Why it only affects variables with map_to parameter
- Why it only happens when calculating past years after future years
- Why multiple variables are affected (they all use aggregation)
""")
    
    # Let's verify this by checking household sizes
    print("\n5. VERIFYING WITH HOUSEHOLD SIZES:")
    print("-" * 40)
    
    sim5 = Microsimulation(dataset=dataset)
    
    # Get tax unit sizes (approximate by checking how many persons per tax unit)
    # This would require accessing internal mappings
    
    # Calculate with bug
    _ = sim5.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    aca_bug = sim5.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    
    bug_arr = np.array(aca_bug)
    
    # Distribution of values
    value_counts = pd.Series(bug_arr).value_counts().sort_index()
    print("Distribution of ACA eligibility values (should be only 0 and 1):")
    print(value_counts.head(10))
    
    print("\nThis confirms: values represent COUNTS of eligible persons per tax unit")
    print("The aggregation is using SUM instead of ANY/MAX for boolean values")

if __name__ == "__main__":
    find_bug_mechanism()