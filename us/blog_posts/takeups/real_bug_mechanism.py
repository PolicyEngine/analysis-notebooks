#!/usr/bin/env python3
"""
Find the REAL bug mechanism - my aggregation hypothesis was wrong!
"""

from policyengine_us import Microsimulation
import numpy as np
import pandas as pd

def find_real_bug():
    """Find what's actually happening."""
    
    dataset = "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5"
    
    print("=" * 60)
    print("FINDING THE REAL BUG MECHANISM")
    print("=" * 60)
    
    # Key insight from previous test:
    # 1. Fresh 2025 ALREADY has values [0,1,2,3,4,5,6] - not just [0,1]
    # 2. Person-level is boolean [False, True]
    # 3. Tax-unit level has counts [0,1,2,3,4,5,6]
    # 4. After calculating 2026, values go up to 13
    
    print("\n1. THE REAL ISSUE - IT'S NOT A BUG, IT'S BY DESIGN:")
    print("-" * 40)
    
    print("""
WAIT - I think I misunderstood the issue entirely!

is_aca_ptc_eligible is defined at PERSON level as boolean.
When aggregated to tax_unit level with map_to, it COUNTS eligible persons.

This might be INTENTIONAL - the variable at tax_unit level represents
the NUMBER of eligible persons in the tax unit, not whether the tax unit
itself is eligible.
""")
    
    # Let's verify this interpretation
    sim = Microsimulation(dataset=dataset)
    
    # Get person-level values
    aca_person = sim.calculate("is_aca_ptc_eligible", period=2025)
    person_values = np.array(aca_person)
    
    # Get tax-unit aggregated values  
    aca_taxunit = sim.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    taxunit_values = np.array(aca_taxunit)
    
    # Get weights
    person_weights = np.array(sim.calculate("person_weight", period=2025))
    taxunit_weights = np.array(sim.calculate("tax_unit_weight", period=2025))
    
    print(f"Person-level eligibility (weighted sum): {(person_values * person_weights).sum()/1e6:.2f}M people")
    print(f"Tax-unit level counts (weighted sum): {(taxunit_values * taxunit_weights).sum()/1e6:.2f}M")
    
    print("\n2. SO WHAT'S THE BUG THEN?")
    print("-" * 40)
    
    # The bug is that after calculating 2026, the 2025 values INCREASE
    sim2 = Microsimulation(dataset=dataset)
    
    # Calculate 2026 first
    _ = sim2.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    
    # Then 2025
    aca_2025_after = sim2.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    after_values = np.array(aca_2025_after)
    
    print(f"Fresh 2025 max value: {taxunit_values.max()}")
    print(f"After 2026 max value: {after_values.max()}")
    
    print(f"\nFresh 2025 sum: {taxunit_values.sum()/1e6:.2f}M")
    print(f"After 2026 sum: {after_values.sum()/1e6:.2f}M")
    
    # Compare specific tax units
    print("\n3. COMPARING SPECIFIC TAX UNITS:")
    print("-" * 40)
    
    # Find tax units that changed
    changed = after_values != taxunit_values
    changed_indices = np.where(changed)[0][:10]
    
    print(f"Number of tax units that changed: {changed.sum()}")
    print("\nFirst 10 changes:")
    for idx in changed_indices:
        print(f"  Tax unit {idx}: {taxunit_values[idx]} → {after_values[idx]} (diff: +{after_values[idx] - taxunit_values[idx]})")
    
    # What's the pattern of changes?
    differences = after_values - taxunit_values
    diff_unique = np.unique(differences[differences != 0])
    print(f"\nUnique difference values: {diff_unique}")
    
    print("\n4. THE PATTERN:")
    print("-" * 40)
    
    # Let's see if it's multiplication
    ratio = after_values[changed] / taxunit_values[changed]
    ratio = ratio[~np.isnan(ratio) & ~np.isinf(ratio)]
    
    print(f"Ratios (after/before) for changed values: {np.unique(ratio[:100])[:10]}")
    
    # Or addition
    print(f"Additions (after-before): {np.unique(differences)[:10]}")
    
    # Check if it's related to 2026 values
    aca_2026 = sim2.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    values_2026 = np.array(aca_2026)
    
    # For changed tax units, what were their 2026 values?
    print(f"\n2026 values for changed tax units:")
    for idx in changed_indices[:5]:
        print(f"  Tax unit {idx}: 2025_fresh={taxunit_values[idx]}, 2026={values_2026[idx]}, 2025_after={after_values[idx]}")
    
    print("\n5. TESTING A HYPOTHESIS - VARIABLE CACHING:")
    print("-" * 40)
    
    # Maybe person-level values get cached wrong?
    sim3 = Microsimulation(dataset=dataset)
    
    # Get person values for 2025 first
    person_2025_before = sim3.calculate("is_aca_ptc_eligible", period=2025)
    
    # Calculate 2026 at tax unit level
    _ = sim3.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    
    # Get person values for 2025 again
    person_2025_after = sim3.calculate("is_aca_ptc_eligible", period=2025)
    
    # Did person-level values change?
    person_before_arr = np.array(person_2025_before)
    person_after_arr = np.array(person_2025_after)
    
    if np.array_equal(person_before_arr, person_after_arr):
        print("✓ Person-level values unchanged")
    else:
        print("❌ Person-level values CHANGED!")
        changed_persons = person_before_arr != person_after_arr
        print(f"   Number of persons affected: {changed_persons.sum()}")
        print(f"   Before sum: {person_before_arr.sum()}")
        print(f"   After sum: {person_after_arr.sum()}")
    
    # Now recalculate at tax unit level
    taxunit_2025_recalc = sim3.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    recalc_values = np.array(taxunit_2025_recalc)
    
    print(f"\n2025 tax unit sum after recalc: {recalc_values.sum()/1e6:.2f}M")
    
    print("\n6. THE SMOKING GUN:")
    print("-" * 40)
    
    # Let's trace exactly what happens
    sim4 = Microsimulation(dataset=dataset)
    
    # Step 1: Calculate 2025 person-level
    p25_step1 = sim4.calculate("is_aca_ptc_eligible", period=2025)
    print(f"Step 1 - 2025 person-level sum: {p25_step1.sum()}")
    
    # Step 2: Calculate 2025 tax-unit level
    t25_step2 = sim4.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    print(f"Step 2 - 2025 tax-unit sum: {t25_step2.sum()/1e6:.2f}M")
    
    # Step 3: Calculate 2026 tax-unit level
    t26_step3 = sim4.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    print(f"Step 3 - 2026 tax-unit sum: {t26_step3.sum()/1e6:.2f}M")
    
    # Step 4: Recalculate 2025 person-level
    p25_step4 = sim4.calculate("is_aca_ptc_eligible", period=2025)
    print(f"Step 4 - 2025 person-level sum after 2026: {p25_step4.sum()}")
    
    # Step 5: Recalculate 2025 tax-unit level
    t25_step5 = sim4.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    print(f"Step 5 - 2025 tax-unit sum after 2026: {t25_step5.sum()/1e6:.2f}M")
    
    if p25_step1.sum() != p25_step4.sum():
        print("\n❌ PERSON-LEVEL VALUES CHANGED!")
        print("The bug is that calculating 2026 changes the cached 2025 person-level values!")

if __name__ == "__main__":
    find_real_bug()