#!/usr/bin/env python3
"""
Precisely reproduce the bug with exact conditions.
"""

from policyengine_us import Microsimulation
import numpy as np

def precise_bug_test():
    """Reproduce the exact bug behavior."""
    
    dataset = "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5"
    
    print("=" * 60)
    print("PRECISE BUG REPRODUCTION")
    print("=" * 60)
    
    # EXACT TEST 1: Reproduce the original issue
    print("\n1. REPRODUCING ORIGINAL ISSUE:")
    print("-" * 40)
    
    # Fresh simulation for 2025 only
    sim1 = Microsimulation(dataset=dataset)
    aca_2025_only = sim1.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    sum_2025_only = aca_2025_only.sum()
    print(f"2025 calculated alone: {sum_2025_only/1e6:.2f}M")
    
    # Fresh simulation for 2026 only
    sim2 = Microsimulation(dataset=dataset)
    aca_2026_only = sim2.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    sum_2026_only = aca_2026_only.sum()
    print(f"2026 calculated alone: {sum_2026_only/1e6:.2f}M")
    
    # Now the problematic order: 2026 then 2025
    sim3 = Microsimulation(dataset=dataset)
    aca_2026_first = sim3.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    sum_2026_first = aca_2026_first.sum()
    print(f"\n2026 calculated first: {sum_2026_first/1e6:.2f}M")
    
    aca_2025_after_2026 = sim3.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    sum_2025_after_2026 = aca_2025_after_2026.sum()
    print(f"2025 after 2026: {sum_2025_after_2026/1e6:.2f}M")
    
    # Calculate the inflation
    inflation = sum_2025_after_2026 / sum_2025_only
    print(f"\nInflation factor: {inflation:.2f}x")
    
    # EXACT TEST 2: Check the values themselves
    print("\n2. CHECKING VALUES:")
    print("-" * 40)
    
    values_2025_only = np.array(aca_2025_only)
    values_2025_after = np.array(aca_2025_after_2026)
    
    print(f"2025 alone - unique values: {np.unique(values_2025_only)}")
    print(f"2025 after 2026 - unique values: {np.unique(values_2025_after)}")
    
    # Look at distribution
    print(f"\n2025 alone - max value: {values_2025_only.max()}")
    print(f"2025 after 2026 - max value: {values_2025_after.max()}")
    
    # Check how many changed
    changed = values_2025_only != values_2025_after
    print(f"\nNumber of tax units that changed: {changed.sum()} out of {len(values_2025_only)}")
    print(f"Percentage changed: {100 * changed.sum() / len(values_2025_only):.1f}%")
    
    # EXACT TEST 3: Look at the changes
    print("\n3. ANALYZING CHANGES:")
    print("-" * 40)
    
    # What kind of changes happened?
    differences = values_2025_after - values_2025_only
    
    # Count each type of change
    from collections import Counter
    change_counter = Counter(differences[changed])
    
    print("Types of changes (difference: count):")
    for diff, count in sorted(change_counter.items())[:10]:
        print(f"  +{diff}: {count} tax units")
    
    # EXACT TEST 4: Check person-level
    print("\n4. CHECKING PERSON-LEVEL:")
    print("-" * 40)
    
    # Fresh simulation
    sim4 = Microsimulation(dataset=dataset)
    
    # Get person-level for 2025
    person_2025_fresh = sim4.calculate("is_aca_ptc_eligible", period=2025)
    person_values_fresh = np.array(person_2025_fresh)
    
    # Calculate 2026 at tax unit level
    _ = sim4.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    
    # Get person-level for 2025 again
    person_2025_after = sim4.calculate("is_aca_ptc_eligible", period=2025)
    person_values_after = np.array(person_2025_after)
    
    # Did they change?
    if np.array_equal(person_values_fresh, person_values_after):
        print("✓ Person-level values UNCHANGED after calculating 2026")
        print(f"  Person sum stays at: {person_values_fresh.sum()}")
    else:
        print("❌ Person-level values CHANGED after calculating 2026!")
        print(f"  Before: {person_values_fresh.sum()}")
        print(f"  After: {person_values_after.sum()}")
        
        # Where did they change?
        person_changed = person_values_fresh != person_values_after
        print(f"  {person_changed.sum()} persons changed out of {len(person_values_fresh)}")
    
    # EXACT TEST 5: The aggregation step
    print("\n5. TESTING AGGREGATION:")
    print("-" * 40)
    
    # When we use map_to="tax_unit", what happens?
    # The person values get aggregated to tax unit level
    
    # Fresh simulation
    sim5 = Microsimulation(dataset=dataset)
    
    # Manual aggregation test
    # Get person eligibility
    person_elig = sim5.calculate("is_aca_ptc_eligible", period=2025)
    
    # Get tax unit aggregation
    taxunit_elig = sim5.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    
    print(f"Person-level sum: {person_elig.sum()}")
    print(f"Tax-unit aggregated sum: {taxunit_elig.sum()}")
    print(f"These should match for COUNT aggregation: {abs(person_elig.sum() - taxunit_elig.sum()) < 1}")
    
    # Now after 2026
    _ = sim5.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    
    person_elig_after = sim5.calculate("is_aca_ptc_eligible", period=2025)
    taxunit_elig_after = sim5.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    
    print(f"\nAfter 2026 calculation:")
    print(f"Person-level sum: {person_elig_after.sum()}")
    print(f"Tax-unit aggregated sum: {taxunit_elig_after.sum()}")
    
    if taxunit_elig_after.sum() > taxunit_elig.sum() * 2:
        print(f"\n❌ Tax-unit sum inflated by {taxunit_elig_after.sum()/taxunit_elig.sum():.2f}x!")
        print("BUG CONFIRMED: The aggregation is broken after calculating future year")

if __name__ == "__main__":
    precise_bug_test()