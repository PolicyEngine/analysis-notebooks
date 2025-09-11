#!/usr/bin/env python3
"""
Investigate the root cause of the calculation order corruption.
"""

from policyengine_us import Microsimulation
import numpy as np

def investigate_simulation_state():
    """Check what changes in the simulation state between calculations."""
    
    dataset = "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5"
    
    print("=" * 60)
    print("INVESTIGATING SIMULATION STATE CHANGES")
    print("=" * 60)
    
    # Create a simulation
    sim = Microsimulation(dataset=dataset)
    
    # Check initial state
    print("\n1. CHECKING SIMULATION ATTRIBUTES:")
    print("-" * 40)
    
    # Get some initial values for 2025
    print("Calculating some 2025 values first...")
    employment_2025_before = sim.calculate("employment_income", period=2025)
    
    # Look at the simulation's internal state
    print(f"Simulation has {len(sim.tax_benefit_system.variables)} variables")
    
    # Check if there are any cached values or internal state
    if hasattr(sim, 'default_input_period'):
        print(f"Default input period: {sim.default_input_period}")
    if hasattr(sim, '_cached_values'):
        print(f"Cached values: {len(sim._cached_values) if sim._cached_values else 0}")
    
    # Now calculate 2026
    print("\n2. CALCULATING 2026 VALUES:")
    print("-" * 40)
    aca_2026 = sim.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    print(f"ACA 2026 sum: {aca_2026.sum()/1e6:.2f}M")
    
    # Check what changed
    print("\n3. CHECKING WHAT CHANGED AFTER 2026 CALCULATION:")
    print("-" * 40)
    
    # Recalculate the same 2025 value
    employment_2025_after = sim.calculate("employment_income", period=2025)
    
    if not np.array_equal(np.array(employment_2025_before), np.array(employment_2025_after)):
        print("❌ Employment income values changed!")
    else:
        print("✓ Employment income unchanged")
    
    # Check ACA for 2025
    aca_2025 = sim.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    print(f"ACA 2025 sum: {aca_2025.sum()/1e6:.2f}M (should be ~49.7M)")
    
    # Look for patterns in what gets corrupted
    print("\n4. TESTING HYPOTHESIS - BENEFITS INTERACTION:")
    print("-" * 40)
    
    # Fresh simulation
    sim_fresh = Microsimulation(dataset=dataset)
    
    # These all got corrupted - check if they're related
    print("Getting 2025 values with fresh simulation:")
    medicaid_2025_fresh = sim_fresh.calculate("medicaid", period=2025)
    snap_2025_fresh = sim_fresh.calculate("snap", map_to="spm_unit", period=2025)
    
    print(f"Medicaid 2025 (fresh): {medicaid_2025_fresh.sum()/1e6:.2f}M")
    print(f"SNAP 2025 (fresh): {snap_2025_fresh.sum()/1e6:.2f}M")
    
    # Now with corrupted simulation
    medicaid_2025_corrupt = sim.calculate("medicaid", period=2025)
    snap_2025_corrupt = sim.calculate("snap", map_to="spm_unit", period=2025)
    
    print(f"Medicaid 2025 (after 2026): {medicaid_2025_corrupt.sum()/1e6:.2f}M")
    print(f"SNAP 2025 (after 2026): {snap_2025_corrupt.sum()/1e6:.2f}M")
    
    # Check if the corruption happens during specific variable calculations
    print("\n5. TESTING INCREMENTAL CORRUPTION:")
    print("-" * 40)
    
    sim_test = Microsimulation(dataset=dataset)
    
    # Calculate different 2026 variables to see which causes corruption
    test_vars_2026 = [
        ("employment_income", "person", "Employment Income"),
        ("has_marketplace_health_coverage", "person", "Marketplace Coverage"),
        ("medicaid", "person", "Medicaid"),
        ("is_aca_ptc_eligible", "tax_unit", "ACA Eligibility"),
    ]
    
    for var, map_to, name in test_vars_2026:
        try:
            print(f"\nTesting effect of calculating {name} for 2026:")
            sim_isolated = Microsimulation(dataset=dataset)
            
            # Calculate this variable for 2026
            val_2026 = sim_isolated.calculate(var, map_to=map_to, period=2026)
            
            # Then check if ACA 2025 is corrupted
            aca_2025_test = sim_isolated.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
            
            if aca_2025_test.sum()/1e6 > 100:  # Corrupted
                print(f"   ❌ Calculating {name} 2026 CAUSES corruption!")
                print(f"      ACA 2025: {aca_2025_test.sum()/1e6:.2f}M")
            else:
                print(f"   ✓ No corruption from {name} 2026")
                print(f"      ACA 2025: {aca_2025_test.sum()/1e6:.2f}M")
        except Exception as e:
            print(f"   Error: {e}")
    
    # Check if it's related to year transitions
    print("\n6. TESTING YEAR TRANSITION EFFECTS:")
    print("-" * 40)
    
    sim_years = Microsimulation(dataset=dataset)
    
    # Test different year combinations
    year_tests = [
        (2024, 2025),
        (2025, 2024),
        (2027, 2025),
        (2025, 2027),
    ]
    
    for year1, year2 in year_tests:
        try:
            sim_year_test = Microsimulation(dataset=dataset)
            
            # Calculate ACA for year1
            aca_year1 = sim_year_test.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=year1)
            
            # Then for year2
            aca_year2 = sim_year_test.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=year2)
            
            # Check if year2 looks corrupted
            if year2 == 2025:
                status = "❌ CORRUPTED" if aca_year2.sum()/1e6 > 100 else "✓ OK"
                print(f"{year1} → {year2}: {status} ({aca_year2.sum()/1e6:.2f}M)")
            else:
                print(f"{year1} → {year2}: {aca_year2.sum()/1e6:.2f}M")
                
        except Exception as e:
            print(f"{year1} → {year2}: Error - {e}")

if __name__ == "__main__":
    investigate_simulation_state()