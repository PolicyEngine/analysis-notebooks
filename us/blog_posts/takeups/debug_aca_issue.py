#!/usr/bin/env python3
"""
Debug script to investigate ACA eligibility calculation order dependency issue.
"""

from policyengine_us import Microsimulation
import pandas as pd

def test_calculation_order():
    """Test how calculation order affects ACA eligibility results."""
    
    dataset = "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5"
    
    print("=" * 60)
    print("Testing ACA Eligibility Calculation Order Dependency")
    print("=" * 60)
    
    # Test 1: Fresh simulation for each year
    print("\n1. FRESH SIMULATIONS (baseline expected values):")
    print("-" * 40)
    
    sim1 = Microsimulation(dataset=dataset)
    aca_2026_fresh = sim1.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026).sum()
    print(f"2026 only: {aca_2026_fresh/1e6:.2f} million eligible")
    
    sim2 = Microsimulation(dataset=dataset)
    aca_2025_fresh = sim2.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025).sum()
    print(f"2025 only: {aca_2025_fresh/1e6:.2f} million eligible")
    
    # Test 2: Same simulation, 2025 then 2026
    print("\n2. SAME SIMULATION - 2025 first, then 2026:")
    print("-" * 40)
    
    sim3 = Microsimulation(dataset=dataset)
    aca_2025_first = sim3.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025).sum()
    aca_2026_after_2025 = sim3.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026).sum()
    print(f"2025 (calculated first): {aca_2025_first/1e6:.2f} million eligible")
    print(f"2026 (after 2025): {aca_2026_after_2025/1e6:.2f} million eligible")
    
    # Test 3: Same simulation, 2026 then 2025 (problematic order)
    print("\n3. SAME SIMULATION - 2026 first, then 2025:")
    print("-" * 40)
    
    sim4 = Microsimulation(dataset=dataset)
    aca_2026_first = sim4.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026).sum()
    aca_2025_after_2026 = sim4.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025).sum()
    print(f"2026 (calculated first): {aca_2026_first/1e6:.2f} million eligible")
    print(f"2025 (after 2026): {aca_2025_after_2026/1e6:.2f} million eligible")
    print(f"⚠️  2025 value inflated by {(aca_2025_after_2026/aca_2025_fresh - 1)*100:.1f}%!")
    
    # Test 4: Check weights to see if they're being modified
    print("\n4. CHECKING WEIGHTS:")
    print("-" * 40)
    
    sim5 = Microsimulation(dataset=dataset)
    weights_before = sim5.calculate("tax_unit_weight", period=2025).sum()
    _ = sim5.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    weights_after = sim5.calculate("tax_unit_weight", period=2025).sum()
    
    print(f"2025 weights before 2026 calculation: {weights_before/1e6:.2f} million")
    print(f"2025 weights after 2026 calculation: {weights_after/1e6:.2f} million")
    
    if abs(weights_before - weights_after) > 1:
        print("⚠️  Weights changed!")
    else:
        print("✓ Weights unchanged")
    
    # Test 5: Look at individual values
    print("\n5. SAMPLE INDIVIDUAL VALUES (first 10 tax units):")
    print("-" * 40)
    
    sim6 = Microsimulation(dataset=dataset)
    
    # Calculate 2026 first
    eligible_2026 = sim6.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    weights_2026 = sim6.calculate("tax_unit_weight", period=2026)
    
    # Then calculate 2025
    eligible_2025 = sim6.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    weights_2025 = sim6.calculate("tax_unit_weight", period=2025)
    
    df = pd.DataFrame({
        '2026_eligible': eligible_2026[:10],
        '2026_weight': weights_2026[:10],
        '2025_eligible': eligible_2025[:10],
        '2025_weight': weights_2025[:10],
    })
    
    print(df)
    
    # Check if weights are being multiplied by eligibility somehow
    print("\n6. DIAGNOSTIC CHECKS:")
    print("-" * 40)
    
    weighted_2025_bad = (eligible_2025 * weights_2025).sum()
    weighted_2026 = (eligible_2026 * weights_2026).sum()
    
    print(f"Weighted sum 2025 (after 2026 calc): {weighted_2025_bad/1e6:.2f} million")
    print(f"Weighted sum 2026: {weighted_2026/1e6:.2f} million")
    
    # Check with fresh simulation for comparison
    sim7 = Microsimulation(dataset=dataset)
    eligible_2025_clean = sim7.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    weights_2025_clean = sim7.calculate("tax_unit_weight", period=2025)
    weighted_2025_clean = (eligible_2025_clean * weights_2025_clean).sum()
    
    print(f"Weighted sum 2025 (fresh simulation): {weighted_2025_clean/1e6:.2f} million")
    
    # Check if the actual boolean values are different
    # Convert to numpy arrays for comparison
    import numpy as np
    eligible_2025_arr = np.array(eligible_2025[:1000])
    eligible_2025_clean_arr = np.array(eligible_2025_clean[:1000])
    
    diff_count = (eligible_2025_arr != eligible_2025_clean_arr).sum()
    print(f"\nNumber of different eligibility values (first 1000): {diff_count}")
    
    if diff_count > 0:
        print("Sample of differences:")
        diff_indices = np.where(eligible_2025_arr != eligible_2025_clean_arr)[0]
        for i in range(min(5, len(diff_indices))):
            idx = diff_indices[i]
            print(f"  Tax unit {idx}: bad={eligible_2025_arr[idx]}, clean={eligible_2025_clean_arr[idx]}")

if __name__ == "__main__":
    test_calculation_order()