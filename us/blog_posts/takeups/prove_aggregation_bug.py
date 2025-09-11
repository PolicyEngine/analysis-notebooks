#!/usr/bin/env python3
"""
Prove the aggregation bug hypothesis with concrete evidence.
"""

from policyengine_us import Microsimulation
import numpy as np
import pandas as pd

def prove_aggregation_bug():
    """Prove that the bug is in person-to-tax-unit aggregation."""
    
    dataset = "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5"
    
    print("=" * 60)
    print("PROVING THE AGGREGATION BUG HYPOTHESIS")
    print("=" * 60)
    
    # PROOF 1: Check if fresh calculations also have the problem
    print("\n1. TESTING FRESH CALCULATION:")
    print("-" * 40)
    
    sim_fresh = Microsimulation(dataset=dataset)
    aca_2025_fresh = sim_fresh.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    fresh_values = np.array(aca_2025_fresh)
    
    print(f"Fresh 2025 unique values: {np.unique(fresh_values)}")
    print(f"Fresh 2025 sum: {aca_2025_fresh.sum()/1e6:.2f}M")
    
    # If fresh also has values > 1, then my hypothesis is WRONG
    if fresh_values.max() > 1:
        print("❌ Fresh calculation ALSO has values > 1!")
        print("   This means the bug might be in the variable definition itself")
    else:
        print("✓ Fresh calculation only has 0 and 1 (correct boolean)")
    
    # PROOF 2: Check person-level values
    print("\n2. CHECKING PERSON-LEVEL VALUES:")
    print("-" * 40)
    
    # Try to calculate without map_to to see person-level values
    try:
        sim_person = Microsimulation(dataset=dataset)
        # First try without map_to parameter
        aca_person_2025 = sim_person.calculate("is_aca_ptc_eligible", period=2025)
        person_values = np.array(aca_person_2025)
        print(f"Person-level unique values: {np.unique(person_values)}")
        print(f"Person-level sum: {aca_person_2025.sum()/1e6:.2f}M")
        
        # Now with map_to
        aca_taxunit_2025 = sim_person.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
        taxunit_values = np.array(aca_taxunit_2025)
        print(f"Tax-unit level unique values: {np.unique(taxunit_values)}")
        print(f"Tax-unit level sum: {aca_taxunit_2025.sum()/1e6:.2f}M")
        
    except Exception as e:
        print(f"Can't calculate at person level: {e}")
        print("This variable might be defined only at tax_unit level")
    
    # PROOF 3: Test if it's actually about household size
    print("\n3. TESTING HOUSEHOLD SIZE CORRELATION:")
    print("-" * 40)
    
    sim_test = Microsimulation(dataset=dataset)
    
    # Trigger the bug
    _ = sim_test.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    aca_bug = sim_test.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    bug_values = np.array(aca_bug)
    
    # Get tax unit sizes if possible
    try:
        # Try to get household/tax unit size
        tax_unit_size = sim_test.calculate("tax_unit_size", period=2025)
        sizes = np.array(tax_unit_size)
        
        # Create a dataframe to analyze
        df = pd.DataFrame({
            'aca_value': bug_values[:10000],  # First 10k for speed
            'tax_unit_size': sizes[:10000]
        })
        
        # Check if max ACA value <= tax unit size
        print("Checking if ACA values exceed tax unit sizes:")
        exceeded = df[df['aca_value'] > df['tax_unit_size']]
        if len(exceeded) > 0:
            print(f"❌ Found {len(exceeded)} cases where ACA value > tax unit size")
            print("   This would be impossible if it were counting eligible persons")
            print(exceeded.head())
        else:
            print("✓ ACA values never exceed tax unit size (consistent with counting)")
        
        # Check correlation
        print(f"\nMax ACA value by tax unit size:")
        print(df.groupby('tax_unit_size')['aca_value'].max().head(10))
        
    except Exception as e:
        print(f"Can't get tax unit size: {e}")
    
    # PROOF 4: Test with a different variable
    print("\n4. TESTING WITH OTHER VARIABLES:")
    print("-" * 40)
    
    # Test with SNAP which also showed corruption
    sim_snap = Microsimulation(dataset=dataset)
    
    # Fresh SNAP
    snap_2025_fresh = sim_snap.calculate("snap", map_to="spm_unit", period=2025)
    print(f"Fresh SNAP 2025: {snap_2025_fresh.sum()/1e6:.2f}M")
    
    # Calculate 2026 first
    _ = sim_snap.calculate("snap", map_to="spm_unit", period=2026)
    
    # Then 2025
    snap_2025_after = sim_snap.calculate("snap", map_to="spm_unit", period=2025)
    print(f"SNAP 2025 after 2026: {snap_2025_after.sum()/1e6:.2f}M")
    
    ratio = snap_2025_after.sum() / snap_2025_fresh.sum() if snap_2025_fresh.sum() > 0 else 0
    print(f"Ratio: {ratio:.2f}x")
    
    # PROOF 5: Test the actual mechanism
    print("\n5. TESTING THE MECHANISM DIRECTLY:")
    print("-" * 40)
    
    # If it's an aggregation bug, let's test different map_to scenarios
    test_cases = [
        ("is_aca_ptc_eligible", "tax_unit", "ACA → tax_unit"),
        ("medicaid", "person", "Medicaid → person (no aggregation)"),
        ("snap", "spm_unit", "SNAP → spm_unit"),
    ]
    
    for var, map_to, desc in test_cases:
        try:
            sim_mech = Microsimulation(dataset=dataset)
            
            # Calculate 2026 first
            val_2026 = sim_mech.calculate(var, map_to=map_to, period=2026)
            
            # Then 2025
            val_2025 = sim_mech.calculate(var, map_to=map_to, period=2025)
            
            # Compare with fresh
            sim_fresh_mech = Microsimulation(dataset=dataset)
            val_2025_fresh = sim_fresh_mech.calculate(var, map_to=map_to, period=2025)
            
            corrupted = abs(val_2025.sum() - val_2025_fresh.sum()) / val_2025_fresh.sum() > 0.01 if val_2025_fresh.sum() > 0 else False
            
            status = "❌ CORRUPTED" if corrupted else "✓ OK"
            print(f"{desc}: {status}")
            
            if corrupted:
                print(f"  Fresh: {val_2025_fresh.sum()/1e6:.2f}M")
                print(f"  After 2026: {val_2025.sum()/1e6:.2f}M")
                
        except Exception as e:
            print(f"{desc}: Error - {e}")
    
    # PROOF 6: Check if it's about the variable formula
    print("\n6. CHECKING VARIABLE DEFINITION:")
    print("-" * 40)
    
    # Get the variable definition
    sim_def = Microsimulation(dataset=dataset)
    tbs = sim_def.tax_benefit_system
    
    if 'is_aca_ptc_eligible' in tbs.variables:
        aca_var = tbs.variables['is_aca_ptc_eligible']
        print(f"Variable entity: {aca_var.entity.key if hasattr(aca_var, 'entity') else 'Unknown'}")
        print(f"Variable value_type: {aca_var.value_type if hasattr(aca_var, 'value_type') else 'Unknown'}")
        
        # Check if it has a formula
        if hasattr(aca_var, 'formulas'):
            print(f"Has formulas for years: {list(aca_var.formulas.keys()) if aca_var.formulas else 'None'}")
    
    # FINAL PROOF: Direct evidence
    print("\n7. FINAL PROOF - DIRECT EVIDENCE:")
    print("-" * 40)
    
    sim_final = Microsimulation(dataset=dataset)
    
    # Calculate 2026 to trigger bug
    _ = sim_final.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    
    # Get 2025 with bug
    aca_2025_bug = sim_final.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    bug_arr = np.array(aca_2025_bug)
    
    # Count how many tax units have each value
    value_counts = pd.Series(bug_arr).value_counts().sort_index()
    
    print("If this is counting eligible persons per tax unit, we'd expect:")
    print("- Value 0: Tax units with 0 eligible persons")
    print("- Value 1: Tax units with 1 eligible person") 
    print("- Value 2: Tax units with 2 eligible persons")
    print("- etc.")
    print("\nActual distribution:")
    for val, count in value_counts.items():
        if val <= 5 or val == value_counts.index.max():
            print(f"  {val}: {count:,} tax units")
    
    print(f"\nTotal 'eligible' count: {bug_arr.sum()/1e6:.2f}M")
    print(f"This is {bug_arr.sum()/len(bug_arr):.2f} per tax unit on average")
    print(f"If it were boolean, max would be {len(bug_arr)/1e6:.2f}M")

if __name__ == "__main__":
    prove_aggregation_bug()