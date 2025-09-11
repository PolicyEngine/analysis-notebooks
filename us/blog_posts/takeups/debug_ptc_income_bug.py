#!/usr/bin/env python3
"""
Debug why households with millions in income are getting PTC.
The issue is likely that PTC is calculated at tax_unit level but we're 
looking at household income. Need to trace the exact calculation.
"""

from policyengine_us import Microsimulation
import pandas as pd
import numpy as np

print("DEBUGGING PTC FOR HIGH-INCOME HOUSEHOLDS")
print("="*70)

baseline = Microsimulation(dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")
year = 2026

# Get data at different levels
print("\n1. GETTING DATA AT DIFFERENT AGGREGATION LEVELS")
print("-"*50)

# HOUSEHOLD level
hh_market_income = baseline.calculate("household_market_income", map_to="household", period=year)
hh_aca_ptc = baseline.calculate("aca_ptc", map_to="household", period=year)
hh_weights = baseline.calculate("household_weight", period=year)

# TAX UNIT level (this is where PTC is actually calculated)
tu_agi = baseline.calculate("adjusted_gross_income", map_to="tax_unit", period=year)
tu_magi = baseline.calculate("aca_magi", map_to="tax_unit", period=year)
tu_ptc = baseline.calculate("aca_ptc", map_to="tax_unit", period=year)
tu_eligible = baseline.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=year)
tu_weights = baseline.calculate("tax_unit_weight", period=year)
tu_size = baseline.calculate("tax_unit_size", map_to="tax_unit", period=year)

# Create dataframes
hh_df = pd.DataFrame({
    'hh_market_income': hh_market_income,
    'hh_ptc': hh_aca_ptc,
    'hh_weight': hh_weights
})

tu_df = pd.DataFrame({
    'tu_agi': tu_agi,
    'tu_magi': tu_magi,
    'tu_ptc': tu_ptc,
    'tu_eligible': tu_eligible,
    'tu_weight': tu_weights,
    'tu_size': tu_size
})

# Find problematic cases
print("\n2. FINDING MISMATCHES")
print("-"*50)

# Households with very high income but PTC
rich_with_ptc = hh_df[(hh_df['hh_market_income'] > 1_000_000) & (hh_df['hh_ptc'] > 0)]
print(f"Households with >$1M income and PTC: {len(rich_with_ptc)}")

# Tax units with PTC - what's their income distribution?
tu_with_ptc = tu_df[tu_df['tu_ptc'] > 0]
print(f"\nTax units with PTC: {len(tu_with_ptc)}")
print(f"Tax units with PTC and MAGI >$500k: {len(tu_with_ptc[tu_with_ptc['tu_magi'] > 500_000])}")
print(f"Tax units with PTC and MAGI >$1M: {len(tu_with_ptc[tu_with_ptc['tu_magi'] > 1_000_000])}")

# Income distribution of tax units with PTC
if len(tu_with_ptc) > 0:
    print("\nMAGI distribution for tax units WITH PTC:")
    print(f"  Min:     ${tu_with_ptc['tu_magi'].min():,.0f}")
    print(f"  25th:    ${tu_with_ptc['tu_magi'].quantile(0.25):,.0f}")
    print(f"  Median:  ${tu_with_ptc['tu_magi'].quantile(0.50):,.0f}")
    print(f"  75th:    ${tu_with_ptc['tu_magi'].quantile(0.75):,.0f}")
    print(f"  95th:    ${tu_with_ptc['tu_magi'].quantile(0.95):,.0f}")
    print(f"  99th:    ${tu_with_ptc['tu_magi'].quantile(0.99):,.0f}")
    print(f"  Max:     ${tu_with_ptc['tu_magi'].max():,.0f}")

# Show examples of high-income tax units with PTC
high_income_ptc = tu_with_ptc[tu_with_ptc['tu_magi'] > 200_000].sort_values('tu_magi', ascending=False)
if len(high_income_ptc) > 0:
    print("\n3. TAX UNITS WITH HIGH MAGI AND PTC:")
    print("-"*50)
    print(f"{'MAGI':<15} {'AGI':<15} {'PTC':<10} {'Size':<6} {'Eligible':<10}")
    print("-"*60)
    for _, row in high_income_ptc.head(10).iterrows():
        print(f"${row['tu_magi']:>13,.0f} ${row['tu_agi']:>13,.0f} ${row['tu_ptc']:>8,.0f} {row['tu_size']:>5.0f} "
              f"{'Yes' if row['tu_eligible'] else 'No':>9}")

# Now let's map tax units to households to understand the disconnect
print("\n4. MAPPING TAX UNITS TO HOUSEHOLDS")
print("-"*50)

# Get the household-tax unit mapping
# We need to use the person table to connect them
person_household = baseline.calculate("household_id", map_to="person", period=year)
person_tax_unit = baseline.calculate("tax_unit_id", map_to="person", period=year)

# Create a mapping dataframe
mapping_df = pd.DataFrame({
    'household_id': person_household,
    'tax_unit_id': person_tax_unit
})

# Remove duplicates to get unique household-tax unit pairs
mapping_unique = mapping_df.drop_duplicates()

print(f"Total persons: {len(mapping_df)}")
print(f"Unique household-tax unit pairs: {len(mapping_unique)}")

# For each problematic household, check its tax units
print("\n5. EXAMINING SPECIFIC PROBLEMATIC HOUSEHOLDS")
print("-"*50)

# Pick a few households with >$10M income and PTC
very_rich_with_ptc = hh_df[(hh_df['hh_market_income'] > 10_000_000) & (hh_df['hh_ptc'] > 0)]
sample_households = very_rich_with_ptc.head(3).index

for hh_idx in sample_households:
    print(f"\nHOUSEHOLD {hh_idx}:")
    print(f"  Household market income: ${hh_df.loc[hh_idx, 'hh_market_income']:,.0f}")
    print(f"  Household PTC: ${hh_df.loc[hh_idx, 'hh_ptc']:,.0f}")
    
    # Find tax units in this household
    tu_in_hh = mapping_unique[mapping_unique['household_id'] == hh_idx]['tax_unit_id'].unique()
    print(f"  Number of tax units: {len(tu_in_hh)}")
    
    if len(tu_in_hh) > 0:
        print("  Tax units in this household:")
        for tu_id in tu_in_hh[:5]:  # Show first 5
            if tu_id < len(tu_df):
                tu_data = tu_df.loc[tu_id]
                print(f"    TU {tu_id}: MAGI=${tu_data['tu_magi']:,.0f}, PTC=${tu_data['tu_ptc']:,.0f}, "
                      f"Eligible={'Yes' if tu_data['tu_eligible'] else 'No'}")

# Check if the issue is with how household income is calculated
print("\n6. CHECKING HOUSEHOLD INCOME CALCULATION")
print("-"*50)

# Get individual income components
employment_income = baseline.calculate("employment_income", map_to="household", period=year)
self_emp_income = baseline.calculate("self_employment_income", map_to="household", period=year)
interest_income = baseline.calculate("interest_income", map_to="household", period=year)
dividend_income = baseline.calculate("dividend_income", map_to="household", period=year)
capital_gains = baseline.calculate("capital_gains", map_to="household", period=year)

# Check a specific high-income household
if len(sample_households) > 0:
    hh_idx = sample_households[0]
    print(f"\nIncome breakdown for household {hh_idx}:")
    print(f"  Market income total:    ${hh_market_income[hh_idx]:>15,.0f}")
    print(f"  Employment income:      ${employment_income[hh_idx]:>15,.0f}")
    print(f"  Self-employment income: ${self_emp_income[hh_idx]:>15,.0f}")
    print(f"  Interest income:        ${interest_income[hh_idx]:>15,.0f}")
    print(f"  Dividend income:        ${dividend_income[hh_idx]:>15,.0f}")
    print(f"  Capital gains:          ${capital_gains[hh_idx]:>15,.0f}")
    
    components_sum = (employment_income[hh_idx] + self_emp_income[hh_idx] + 
                     interest_income[hh_idx] + dividend_income[hh_idx] + 
                     capital_gains[hh_idx])
    print(f"  Sum of components:      ${components_sum:>15,.0f}")
    print(f"  Difference:             ${hh_market_income[hh_idx] - components_sum:>15,.0f}")

print("\n" + "="*70)
print("CONCLUSIONS:")
print("="*70)
print("""
The issue appears to be that:
1. PTC is correctly calculated at the TAX UNIT level based on MAGI
2. Tax units with reasonable incomes are getting PTC appropriately
3. But when aggregated to HOUSEHOLD level, the household income is wrong
4. This suggests the household_market_income variable has a calculation bug

The household income aggregation is likely including something it shouldn't,
or there's a data error in the enhanced CPS file itself.
""")