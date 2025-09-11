#!/usr/bin/env python3
"""
Diagnose the specific mechanism causing the ACA calculation corruption.
"""

from policyengine_us import Microsimulation
import numpy as np

def diagnose_mechanism():
    """Find the specific mechanism causing the corruption."""
    
    dataset = "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5"
    
    print("=" * 60)
    print("DIAGNOSING THE CORRUPTION MECHANISM")
    print("=" * 60)
    
    # First, let's see if we can access the calculation internals
    sim = Microsimulation(dataset=dataset)
    
    print("\n1. EXAMINING SIMULATION INTERNALS:")
    print("-" * 40)
    
    # Check what attributes the simulation has
    print("Key simulation attributes:")
    for attr in dir(sim):
        if not attr.startswith('_') and not attr.startswith('__'):
            if attr in ['situations', 'simulation', 'tax_benefit_system']:
                print(f"  - {attr}: {type(getattr(sim, attr))}")
    
    # Let's trace through a calculation
    print("\n2. TRACING CALCULATION PROCESS:")
    print("-" * 40)
    
    # Get the variable object for ACA eligibility
    if hasattr(sim, 'tax_benefit_system'):
        tbs = sim.tax_benefit_system
        if hasattr(tbs, 'variables'):
            if 'is_aca_ptc_eligible' in tbs.variables:
                aca_var = tbs.variables['is_aca_ptc_eligible']
                print(f"ACA variable class: {type(aca_var)}")
                print(f"ACA variable attributes: {[a for a in dir(aca_var) if not a.startswith('_')][:10]}")
    
    # Check for the actual calculation object
    # Microsimulation might wrap the actual simulation
    actual_sim = None
    if hasattr(sim, 'simulation'):
        actual_sim = sim.simulation
    elif hasattr(sim, 'sim'):
        actual_sim = sim.sim
    elif hasattr(sim, '_sim'):
        actual_sim = sim._sim
    else:
        # Try to find it through calculate method
        print("\nLooking for simulation object...")
        
    # Now let's look at how values are stored
    print("\n3. CHECKING VALUE STORAGE:")
    print("-" * 40)
    
    # Calculate 2026 and inspect what changes
    print("Before 2026 calculation:")
    if hasattr(sim.simulation, '_holders'):
        aca_holder_before = sim.simulation._holders.get('is_aca_ptc_eligible', None)
        if aca_holder_before:
            print(f"  ACA holder exists: {type(aca_holder_before)}")
            if hasattr(aca_holder_before, '_array_by_period'):
                print(f"  Arrays by period: {list(aca_holder_before._array_by_period.keys()) if aca_holder_before._array_by_period else 'None'}")
    
    # Calculate 2026
    aca_2026 = sim.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    print(f"\n2026 ACA calculated: {aca_2026.sum()/1e6:.2f}M")
    
    print("\nAfter 2026 calculation:")
    if hasattr(sim.simulation, '_holders'):
        aca_holder_after = sim.simulation._holders.get('is_aca_ptc_eligible', None)
        if aca_holder_after:
            if hasattr(aca_holder_after, '_array_by_period'):
                print(f"  Arrays by period: {list(aca_holder_after._array_by_period.keys()) if aca_holder_after._array_by_period else 'None'}")
                
                # Check the actual arrays
                if aca_holder_after._array_by_period:
                    for period, array in list(aca_holder_after._array_by_period.items())[:3]:
                        if array is not None:
                            arr_sample = array[:10] if hasattr(array, '__getitem__') else array
                            print(f"    {period}: shape={array.shape if hasattr(array, 'shape') else 'N/A'}, sample={arr_sample}")
    
    # Now calculate 2025 and see what happens
    aca_2025 = sim.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    print(f"\n2025 ACA calculated: {aca_2025.sum()/1e6:.2f}M")
    
    print("\nAfter 2025 calculation:")
    if hasattr(sim.simulation, '_holders'):
        aca_holder_final = sim.simulation._holders.get('is_aca_ptc_eligible', None)
        if aca_holder_final and hasattr(aca_holder_final, '_array_by_period'):
            if aca_holder_final._array_by_period:
                for period, array in list(aca_holder_final._array_by_period.items())[:3]:
                    if array is not None:
                        arr_sample = array[:10] if hasattr(array, '__getitem__') else array
                        print(f"    {period}: shape={array.shape if hasattr(array, 'shape') else 'N/A'}, sample={arr_sample}")
    
    # Let's check if it's a mapping issue
    print("\n4. CHECKING ENTITY MAPPING:")
    print("-" * 40)
    
    # The calculate function maps from person to tax_unit
    # Let's see if this mapping gets corrupted
    
    sim2 = Microsimulation(dataset=dataset)
    
    # First check person-level calculation
    print("Testing person vs tax_unit calculations...")
    
    # Get person count
    if hasattr(sim2.simulation, 'persons'):
        person_entity = sim2.simulation.persons
        print(f"Number of persons: {person_entity.count}")
    
    # Get tax_unit count  
    if hasattr(sim2.simulation, 'tax_units'):
        tax_unit_entity = sim2.simulation.tax_units
        print(f"Number of tax_units: {tax_unit_entity.count}")
    
    # Check the mapping
    if hasattr(sim2.simulation, 'persons') and hasattr(sim2.simulation.persons, 'tax_unit'):
        # This tells us which tax_unit each person belongs to
        person_to_tax_unit = sim2.simulation.persons.tax_unit
        print(f"Person to tax_unit mapping shape: {person_to_tax_unit.shape if hasattr(person_to_tax_unit, 'shape') else 'N/A'}")
    
    # Now let's test if the mapping changes after calculation
    print("\n5. TESTING IF MAPPING CHANGES:")
    print("-" * 40)
    
    sim3 = Microsimulation(dataset=dataset)
    
    # Get initial mapping
    if hasattr(sim3.simulation.persons, 'tax_unit'):
        mapping_before = np.array(sim3.simulation.persons.tax_unit)
        print(f"Mapping before (first 20): {mapping_before[:20]}")
    
    # Calculate 2026
    _ = sim3.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    
    # Check mapping after
    if hasattr(sim3.simulation.persons, 'tax_unit'):
        mapping_after = np.array(sim3.simulation.persons.tax_unit)
        print(f"Mapping after (first 20): {mapping_after[:20]}")
        
        if not np.array_equal(mapping_before, mapping_after):
            print("❌ MAPPING CHANGED!")
        else:
            print("✓ Mapping unchanged")
    
    # Check if it's an aggregation issue
    print("\n6. CHECKING AGGREGATION:")
    print("-" * 40)
    
    sim4 = Microsimulation(dataset=dataset)
    
    # Calculate at person level first (if possible)
    try:
        # Some variables might be calculated at person level then aggregated
        medicaid_person_2026 = sim4.calculate("medicaid", period=2026)
        print(f"Medicaid 2026 (person level): {medicaid_person_2026.sum()/1e6:.2f}M")
        
        medicaid_person_2025 = sim4.calculate("medicaid", period=2025)
        print(f"Medicaid 2025 (person level, after 2026): {medicaid_person_2025.sum()/1e6:.2f}M")
        
        # Fresh sim for comparison
        sim5 = Microsimulation(dataset=dataset)
        medicaid_person_2025_fresh = sim5.calculate("medicaid", period=2025)
        print(f"Medicaid 2025 (fresh): {medicaid_person_2025_fresh.sum()/1e6:.2f}M")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    diagnose_mechanism()