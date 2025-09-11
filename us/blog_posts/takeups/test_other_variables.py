#!/usr/bin/env python3
"""
Test if the calculation order bug affects other variables beyond ACA eligibility.
"""

from policyengine_us import Microsimulation
import numpy as np

def test_variable_corruption(variable_name, map_to="person", test_name=None):
    """Test if a variable gets corrupted by calculation order."""
    
    if test_name is None:
        test_name = variable_name
        
    dataset = "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5"
    
    print(f"\nTesting: {test_name}")
    print("-" * 40)
    
    # Test with fresh simulations
    sim1 = Microsimulation(dataset=dataset)
    val_2025_fresh = sim1.calculate(variable_name, map_to=map_to, period=2025)
    
    sim2 = Microsimulation(dataset=dataset)
    val_2026_fresh = sim2.calculate(variable_name, map_to=map_to, period=2026)
    
    # Test with 2026 first, then 2025 (problematic order for ACA)
    sim3 = Microsimulation(dataset=dataset)
    val_2026_first = sim3.calculate(variable_name, map_to=map_to, period=2026)
    val_2025_after = sim3.calculate(variable_name, map_to=map_to, period=2025)
    
    # Compare sums
    sum_2025_fresh = val_2025_fresh.sum()
    sum_2025_after = val_2025_after.sum()
    sum_2026_fresh = val_2026_fresh.sum()
    
    # Check for corruption
    if abs(sum_2025_fresh - sum_2025_after) > 0.01:
        ratio = sum_2025_after / sum_2025_fresh if sum_2025_fresh != 0 else float('inf')
        print(f"❌ CORRUPTED!")
        print(f"   2025 fresh: {sum_2025_fresh/1e6:.2f}M")
        print(f"   2025 after 2026: {sum_2025_after/1e6:.2f}M")
        print(f"   Ratio: {ratio:.2f}x")
        
        # Check value differences
        arr_fresh = np.array(val_2025_fresh[:100])
        arr_after = np.array(val_2025_after[:100])
        if not np.array_equal(arr_fresh, arr_after):
            diff_count = (arr_fresh != arr_after).sum()
            print(f"   Different values in first 100: {diff_count}")
            print(f"   Sample fresh: {arr_fresh[:10]}")
            print(f"   Sample after: {arr_after[:10]}")
        return True
    else:
        print(f"✓ OK - No corruption detected")
        print(f"   2025: {sum_2025_fresh/1e6:.2f}M")
        print(f"   2026: {sum_2026_fresh/1e6:.2f}M")
        return False

def main():
    print("=" * 60)
    print("TESTING MULTIPLE VARIABLES FOR CALCULATION ORDER CORRUPTION")
    print("=" * 60)
    
    corrupted_vars = []
    
    # Test the known problematic variable
    if test_variable_corruption("is_aca_ptc_eligible", map_to="tax_unit", 
                                test_name="ACA PTC Eligibility (known issue)"):
        corrupted_vars.append("is_aca_ptc_eligible")
    
    # Test other ACA-related variables
    aca_vars = [
        ("aca_ptc", "tax_unit", "ACA Premium Tax Credit Amount"),
        ("aca_max_ptc", "tax_unit", "ACA Max PTC"),
        ("aca_slcsp_premium", "tax_unit", "ACA SLCSP Premium"),
        ("is_aca_ptc_phase_out_eligible", "tax_unit", "ACA PTC Phase Out Eligible"),
    ]
    
    for var, map_to, name in aca_vars:
        try:
            if test_variable_corruption(var, map_to=map_to, test_name=name):
                corrupted_vars.append(var)
        except Exception as e:
            print(f"   Error testing {var}: {e}")
    
    # Test some non-ACA variables
    other_vars = [
        ("employment_income", "person", "Employment Income"),
        ("adjusted_gross_income", "tax_unit", "AGI"),
        ("snap", "spm_unit", "SNAP Benefits"),
        ("federal_income_tax", "tax_unit", "Federal Income Tax"),
        ("earned_income_tax_credit", "tax_unit", "EITC"),
        ("child_tax_credit", "tax_unit", "Child Tax Credit"),
        ("is_tax_unit_dependent", "person", "Is Tax Unit Dependent"),
        ("medicaid", "person", "Medicaid Eligibility"),
    ]
    
    print("\n" + "=" * 60)
    print("TESTING NON-ACA VARIABLES")
    print("=" * 60)
    
    for var, map_to, name in other_vars:
        try:
            if test_variable_corruption(var, map_to=map_to, test_name=name):
                corrupted_vars.append(var)
        except Exception as e:
            print(f"   Error testing {var}: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if corrupted_vars:
        print(f"\n❌ Found {len(corrupted_vars)} corrupted variable(s):")
        for var in corrupted_vars:
            print(f"   - {var}")
    else:
        print("\n✓ Only ACA PTC eligibility appears to be affected")
    
    # Let's dig deeper into why ACA is special
    print("\n" + "=" * 60)
    print("INVESTIGATING ACA CALCULATION DEPENDENCIES")
    print("=" * 60)
    
    sim = Microsimulation(dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")
    
    # Try to trace what happens during calculation
    print("\nChecking what variables ACA PTC eligibility depends on...")
    
    # These are likely dependencies based on ACA rules
    dependency_tests = [
        ("has_marketplace_health_coverage", "person"),
        ("is_medicaid_eligible", "person"),
        ("is_enrolled_in_esi", "person"),
        ("tax_unit_income", "tax_unit"),
        ("tax_unit_medicaid_income", "tax_unit"),
    ]
    
    for var, map_to in dependency_tests:
        try:
            print(f"\nTesting dependency: {var}")
            # Calculate 2026 first
            sim_test = Microsimulation(dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")
            val_2026 = sim_test.calculate(var, map_to=map_to, period=2026)
            val_2025 = sim_test.calculate(var, map_to=map_to, period=2025)
            
            # Now calculate ACA eligibility
            aca_2025 = sim_test.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
            
            if aca_2025.sum() / 1e6 > 100:  # If corrupted (>100M)
                print(f"   → This dependency might be involved in corruption")
        except Exception as e:
            print(f"   Error: {e}")

if __name__ == "__main__":
    main()