#!/usr/bin/env python3
"""
Test if the issue exists with the new dataset too
"""

from policyengine_us import Microsimulation
import numpy as np

print("TESTING BOTH DATASETS")
print("="*70)

year = 2026

print("\n1. OLD DATASET (local file)")
print("-"*50)

old_sim = Microsimulation(dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")

# Get household and person counts
person_hh_id_old = old_sim.calculate("household_id", map_to="person", period=year)
hh_size_old = old_sim.calculate("household_size", map_to="household", period=year)

# Check a specific household
hh_idx = 20731
persons_in_hh_old = (person_hh_id_old == hh_idx).sum()
print(f"Household {hh_idx}:")
print(f"  Reported size: {hh_size_old[hh_idx] if hh_idx < len(hh_size_old) else 'N/A'}")
print(f"  Person records: {persons_in_hh_old}")

# Check income
hh_income_old = old_sim.calculate("household_market_income", map_to="household", period=year)
cap_gains_old = old_sim.calculate("capital_gains", map_to="household", period=year)
print(f"\nIncome statistics:")
print(f"  Max household income: ${hh_income_old.max():,.0f}")
print(f"  Max capital gains: ${cap_gains_old.max():,.0f}")
print(f"  Households with >$10M capital gains: {(cap_gains_old > 10_000_000).sum()}")

print("\n2. NEW DATASET (huggingface)")
print("-"*50)

new_sim = Microsimulation(dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")

# Get household and person counts
person_hh_id_new = new_sim.calculate("household_id", map_to="person", period=year)
hh_size_new = new_sim.calculate("household_size", map_to="household", period=year)

# Check the same household
persons_in_hh_new = (person_hh_id_new == hh_idx).sum()
print(f"Household {hh_idx}:")
print(f"  Reported size: {hh_size_new[hh_idx] if hh_idx < len(hh_size_new) else 'N/A'}")
print(f"  Person records: {persons_in_hh_new}")

# Check income
hh_income_new = new_sim.calculate("household_market_income", map_to="household", period=year)
cap_gains_new = new_sim.calculate("capital_gains", map_to="household", period=year)
print(f"\nIncome statistics:")
print(f"  Max household income: ${hh_income_new.max():,.0f}")
print(f"  Max capital gains: ${cap_gains_new.max():,.0f}")
print(f"  Households with >$10M capital gains: {(cap_gains_new > 10_000_000).sum()}")

print("\n3. COMPARISON")
print("-"*50)

print(f"Number of households:")
print(f"  Old: {len(hh_size_old):,}")
print(f"  New: {len(hh_size_new):,}")

print(f"\nNumber of person records:")
print(f"  Old: {len(person_hh_id_old):,}")
print(f"  New: {len(person_hh_id_new):,}")

# Check if the mapping is broken
print("\n4. CHECKING HOUSEHOLD-PERSON MAPPING")
print("-"*50)

# In old dataset
unique_hh_ids_old = np.unique(person_hh_id_old)
print(f"Old dataset:")
print(f"  Unique household IDs in person table: {len(unique_hh_ids_old)}")
print(f"  Max household ID: {unique_hh_ids_old.max() if len(unique_hh_ids_old) > 0 else 'N/A'}")
print(f"  Should match number of households: {len(hh_size_old)}")

# In new dataset  
unique_hh_ids_new = np.unique(person_hh_id_new)
print(f"\nNew dataset:")
print(f"  Unique household IDs in person table: {len(unique_hh_ids_new)}")
print(f"  Max household ID: {unique_hh_ids_new.max() if len(unique_hh_ids_new) > 0 else 'N/A'}")
print(f"  Should match number of households: {len(hh_size_new)}")

print("\n" + "="*70)
print("DIAGNOSIS:")
print("="*70)
print("""
If both datasets show the same issue, it's a PolicyEngine calculation bug.
If only one shows it, that specific dataset file is corrupted.
""")