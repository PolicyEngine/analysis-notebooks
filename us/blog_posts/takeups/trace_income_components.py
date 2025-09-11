#!/usr/bin/env python3
"""
Trace all components of household_market_income to find the bug
"""

from policyengine_us import Microsimulation
import pandas as pd
import numpy as np

print("TRACING HOUSEHOLD MARKET INCOME COMPONENTS")
print("="*70)

baseline = Microsimulation(dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")
year = 2026

# List of all market income sources from the YAML file
income_sources = [
    "employment_income",
    "self_employment_income",
    "partnership_s_corp_income",
    "gi_cash_assistance",
    "farm_income",
    "farm_rent_income",
    "capital_gains",
    "interest_income",
    "rental_income",
    "dividend_income",
    "pension_income",
    "debt_relief",
    "unemployment_compensation",
    "social_security",
    "illicit_income",
    "retirement_distributions",
    "miscellaneous_income",
    "ak_permanent_fund_dividend"
]

# Get household market income
hh_market_income = baseline.calculate("household_market_income", map_to="household", period=year)
hh_ptc = baseline.calculate("aca_ptc", map_to="household", period=year)

# Find a problematic household
problematic = (hh_market_income > 10_000_000) & (hh_ptc > 0)
problematic_indices = np.where(problematic)[0]

if len(problematic_indices) > 0:
    # Pick the first problematic household
    hh_idx = problematic_indices[0]
    
    print(f"\nANALYZING HOUSEHOLD {hh_idx}")
    print("-"*50)
    print(f"Household market income: ${hh_market_income[hh_idx]:,.0f}")
    print(f"Household PTC: ${hh_ptc[hh_idx]:,.0f}")
    
    print("\nINCOME COMPONENTS:")
    print("-"*50)
    
    total_components = 0
    component_values = {}
    
    for source in income_sources:
        try:
            value = baseline.calculate(source, map_to="household", period=year)[hh_idx]
            component_values[source] = value
            total_components += value
            if value != 0:
                print(f"{source:30} ${value:>15,.0f}")
        except Exception as e:
            print(f"{source:30} Error: {str(e)[:40]}")
    
    print("-"*50)
    print(f"{'Sum of components:':30} ${total_components:>15,.0f}")
    print(f"{'Reported market income:':30} ${hh_market_income[hh_idx]:>15,.0f}")
    print(f"{'Unexplained difference:':30} ${hh_market_income[hh_idx] - total_components:>15,.0f}")
    
    # Now let's check person-level income for this household
    print("\n" + "="*70)
    print("CHECKING PERSON-LEVEL INCOME")
    print("-"*50)
    
    # Get person-level data
    person_hh_id = baseline.calculate("household_id", map_to="person", period=year)
    persons_in_hh = person_hh_id == hh_idx
    
    if persons_in_hh.any():
        # Check key person-level income variables
        person_sources = [
            "employment_income",
            "self_employment_income",
            "capital_gains",
            "interest_income",
            "dividend_income"
        ]
        
        print(f"Number of persons in household: {persons_in_hh.sum()}")
        
        for source in person_sources:
            try:
                person_values = baseline.calculate(source, map_to="person", period=year)
                hh_total = person_values[persons_in_hh].sum()
                print(f"{source:30} ${hh_total:>15,.0f} (sum of persons)")
            except:
                pass
    
    # Check if it's a specific component causing issues
    print("\n" + "="*70)
    print("CHECKING ALL HOUSEHOLDS FOR ANOMALIES")
    print("-"*50)
    
    # Check which component has the most extreme values
    for source in ["capital_gains", "dividend_income", "interest_income", "retirement_distributions"]:
        try:
            values = baseline.calculate(source, map_to="household", period=year)
            max_val = values.max()
            if max_val > 1_000_000:
                count_over_1m = (values > 1_000_000).sum()
                count_over_10m = (values > 10_000_000).sum()
                print(f"{source}:")
                print(f"  Max value: ${max_val:,.0f}")
                print(f"  Households > $1M: {count_over_1m}")
                print(f"  Households > $10M: {count_over_10m}")
        except:
            pass

print("\n" + "="*70)
print("CONCLUSION:")
print("="*70)
print("""
The unexplained difference in household market income suggests either:
1. One of the income components has a calculation bug causing extreme values
2. The aggregation from person to household level has an error
3. There's a data issue in the enhanced CPS file itself

Look for the component with the most extreme values - that's likely the source of the bug.
""")