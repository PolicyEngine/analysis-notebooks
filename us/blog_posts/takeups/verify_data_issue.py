#!/usr/bin/env python3
"""
Verify if this is really a data issue or a calculation error
"""

from policyengine_us import Microsimulation
import pandas as pd
import numpy as np

print("VERIFYING DATA INTEGRITY")
print("="*70)

baseline = Microsimulation(dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")
year = 2026

# Get basic counts
print("\n1. BASIC DATASET STATISTICS")
print("-"*50)

# Household level
household_weights = baseline.calculate("household_weight", period=year)
household_ids = np.arange(len(household_weights))
print(f"Number of household records: {len(household_weights):,}")
print(f"Total weighted households: {household_weights.sum():,.0f}")

# Person level
person_weights = baseline.calculate("person_weight", period=year)
person_household_id = baseline.calculate("household_id", map_to="person", period=year)
print(f"Number of person records: {len(person_weights):,}")
print(f"Total weighted persons: {person_weights.sum():,.0f}")

# Tax unit level
tax_unit_weights = baseline.calculate("tax_unit_weight", period=year)
print(f"Number of tax unit records: {len(tax_unit_weights):,}")
print(f"Total weighted tax units: {tax_unit_weights.sum():,.0f}")

# Check household sizes
print("\n2. HOUSEHOLD SIZE DISTRIBUTION")
print("-"*50)

household_size = baseline.calculate("household_size", map_to="household", period=year)
print(f"Min household size: {household_size.min()}")
print(f"Max household size: {household_size.max()}")
print(f"Mean household size: {household_size.mean():.2f}")
print(f"Median household size: {np.median(household_size):.0f}")

# Check for outliers
large_households = household_size > 10
print(f"\nHouseholds with >10 members: {large_households.sum()}")
very_large_households = household_size > 20
print(f"Households with >20 members: {very_large_households.sum()}")

# Show distribution of large households
if large_households.any():
    large_sizes = household_size[large_households]
    print("\nLarge household sizes:")
    unique_sizes, counts = np.unique(large_sizes, return_counts=True)
    for size, count in zip(unique_sizes[:10], counts[:10]):
        print(f"  Size {size:>3.0f}: {count:>4} households")

# Check specific household 20731
print("\n3. EXAMINING HOUSEHOLD 20731")
print("-"*50)

hh_idx = 20731
if hh_idx < len(household_weights):
    print(f"Household weight: {household_weights[hh_idx]:.2f}")
    print(f"Household size: {household_size[hh_idx]:.0f}")
    
    # Count actual persons in this household
    persons_in_hh = person_household_id == hh_idx
    actual_person_count = persons_in_hh.sum()
    print(f"Actual person records in household: {actual_person_count}")
    
    if actual_person_count > 0 and actual_person_count < 100:
        # Show person details if reasonable number
        person_ages = baseline.calculate("age", map_to="person", period=year)
        ages_in_hh = person_ages[persons_in_hh]
        print(f"Ages of persons: {ages_in_hh.tolist()}")
        
        person_weights_in_hh = person_weights[persons_in_hh]
        print(f"Person weights: {person_weights_in_hh.tolist()}")
        print(f"Sum of person weights: {person_weights_in_hh.sum():.2f}")

# Now check income distributions
print("\n4. INCOME DISTRIBUTION CHECK")
print("-"*50)

# Get key income variables
capital_gains = baseline.calculate("capital_gains", map_to="household", period=year)
dividend_income = baseline.calculate("dividend_income", map_to="household", period=year)
partnership_income = baseline.calculate("partnership_s_corp_income", map_to="household", period=year)

print("Capital gains distribution:")
print(f"  Non-zero values: {(capital_gains != 0).sum():,}")
print(f"  Positive values: {(capital_gains > 0).sum():,}")
print(f"  > $1M: {(capital_gains > 1_000_000).sum():,}")
print(f"  > $10M: {(capital_gains > 10_000_000).sum():,}")
print(f"  > $100M: {(capital_gains > 100_000_000).sum():,}")
print(f"  Maximum: ${capital_gains.max():,.0f}")

print("\nDividend income distribution:")
print(f"  Non-zero values: {(dividend_income != 0).sum():,}")
print(f"  > $1M: {(dividend_income > 1_000_000).sum():,}")
print(f"  > $10M: {(dividend_income > 10_000_000).sum():,}")
print(f"  Maximum: ${dividend_income.max():,.0f}")

print("\nPartnership/S-corp income distribution:")
print(f"  Non-zero values: {(partnership_income != 0).sum():,}")
print(f"  > $1M: {(partnership_income > 1_000_000).sum():,}")
print(f"  > $10M: {(partnership_income > 10_000_000).sum():,}")
print(f"  Maximum: ${partnership_income.max():,.0f}")

# Check if these extreme values are in the raw data or calculated
print("\n5. CHECKING IF VALUES ARE RAW OR CALCULATED")
print("-"*50)

# Try to trace back to person level
person_cap_gains = baseline.calculate("capital_gains", map_to="person", period=year)
print(f"Person-level capital gains max: ${person_cap_gains.max():,.0f}")
print(f"Person-level capital gains > $10M: {(person_cap_gains > 10_000_000).sum()}")

# Check the specific household with extreme income
extreme_income_hh = np.argmax(capital_gains)
print(f"\nHousehold with max capital gains: {extreme_income_hh}")
print(f"  Capital gains: ${capital_gains[extreme_income_hh]:,.0f}")
print(f"  Household size: {household_size[extreme_income_hh]:.0f}")
print(f"  Household weight: {household_weights[extreme_income_hh]:.2f}")

# Count persons in this household
persons_in_extreme = person_household_id == extreme_income_hh
print(f"  Person records in household: {persons_in_extreme.sum()}")

print("\n" + "="*70)
print("DIAGNOSIS:")
print("="*70)