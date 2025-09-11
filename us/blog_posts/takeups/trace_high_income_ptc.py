#!/usr/bin/env python3
"""
Trace through the PTC calculation for specific high-income households
to understand why they're getting benefits
"""

from policyengine_us import Microsimulation
from policyengine_core.reforms import Reform
import pandas as pd
import numpy as np

reform = Reform.from_dict({
    "gov.aca.ptc_phase_out_rate[0].amount": {
        "2026-01-01.2100-12-31": 0
    },
    "gov.aca.ptc_phase_out_rate[1].amount": {
        "2025-01-01.2100-12-31": 0
    },
    "gov.aca.ptc_phase_out_rate[2].amount": {
        "2026-01-01.2100-12-31": 0
    },
    "gov.aca.ptc_phase_out_rate[3].amount": {
        "2026-01-01.2100-12-31": 0.02
    },
    "gov.aca.ptc_phase_out_rate[4].amount": {
        "2026-01-01.2100-12-31": 0.04
    },
    "gov.aca.ptc_phase_out_rate[5].amount": {
        "2026-01-01.2100-12-31": 0.06
    },
    "gov.aca.ptc_phase_out_rate[6].amount": {
        "2026-01-01.2100-12-31": 0.085
    }
}, country_id="us")

print("TRACING PTC CALCULATION FOR HIGH-INCOME HOUSEHOLDS")
print("="*70)

baseline = Microsimulation(dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")
reformed = Microsimulation(reform=reform, dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")

year = 2026

# Get household variables
hh_income = baseline.calculate("household_market_income", map_to="household", period=year)
ptc_base_hh = baseline.calculate("aca_ptc", map_to="household", period=year)
ptc_reform_hh = reformed.calculate("aca_ptc", map_to="household", period=year)

# Find a specific high-income household with PTC
# Let's look at household 24251 which has $66M income but gets PTC
target_idx = 24251

print(f"\nANALYZING HOUSEHOLD {target_idx}")
print("-"*50)

# Get all relevant variables for this household
variables_to_check = [
    # Household level
    ("household_market_income", "household"),
    ("household_net_income", "household"),
    ("household_size", "household"),
    ("state_code_str", "household"),
    
    # Tax unit level - these are key for PTC
    ("adjusted_gross_income", "tax_unit"),
    ("aca_magi", "tax_unit"),
    ("tax_unit_size", "tax_unit"),
    ("is_aca_ptc_eligible", "tax_unit"),
    ("would_claim_aca_ptc", "tax_unit"),
    ("aca_ptc", "tax_unit"),
    
    # SLCSP and premium info
    ("second_lowest_silver_plan_cost", "tax_unit"),
    ("aca_max_payment", "tax_unit"),
    ("aca_max_payment_rate", "tax_unit"),
    
    # Person level - check insurance status
    ("has_esi", "person"),
    ("is_medicaid_eligible", "person"),
    ("age", "person"),
]

print("\nBASELINE VALUES:")
print("-"*30)
for var_name, entity in variables_to_check:
    try:
        value = baseline.calculate(var_name, map_to=entity, period=year)
        if entity == "household":
            print(f"{var_name}: {value[target_idx]:,.0f}" if isinstance(value[target_idx], (int, float)) else f"{var_name}: {value[target_idx]}")
        elif entity == "tax_unit":
            # Get tax units in this household
            # This is approximate - we'll just show the first few values
            print(f"{var_name}: {value[:5]}")  # Show first 5 tax units
        else:
            # Person level - show first few
            print(f"{var_name}: {value[:5]}")
    except Exception as e:
        print(f"{var_name}: Error - {e}")

print("\nREFORM VALUES (key variables):")
print("-"*30)
reform_vars = [
    ("aca_ptc", "tax_unit"),
    ("is_aca_ptc_eligible", "tax_unit"),
    ("aca_max_payment", "tax_unit"),
    ("aca_max_payment_rate", "tax_unit"),
]

for var_name, entity in reform_vars:
    try:
        value = reformed.calculate(var_name, map_to=entity, period=year)
        print(f"{var_name}: {value[:5]}")
    except Exception as e:
        print(f"{var_name}: Error - {e}")

# Now let's check aggregate statistics to understand the scale
print("\n" + "="*70)
print("AGGREGATE STATISTICS")
print("="*70)

# How many households have both high income AND PTC?
hh_df = pd.DataFrame({
    'income': hh_income,
    'ptc_base': ptc_base_hh,
    'ptc_reform': ptc_reform_hh,
})

# Define high income thresholds
thresholds = [500_000, 1_000_000, 5_000_000, 10_000_000, 50_000_000]

print("\nHouseholds with PTC by income level:")
print(f"{'Income Threshold':<20} {'With Base PTC':<15} {'With Reform PTC':<15}")
print("-"*50)

for threshold in thresholds:
    high_income = hh_df[hh_df['income'] > threshold]
    with_base = (high_income['ptc_base'] > 0).sum()
    with_reform = (high_income['ptc_reform'] > 0).sum()
    print(f">${threshold:>15,} {with_base:>14,} {with_reform:>14,}")

# Check if these might be data errors
print("\n" + "="*70)
print("CHECKING FOR DATA ANOMALIES")
print("="*70)

# Get employment income to compare
emp_income = baseline.calculate("employment_income", map_to="household", period=year)
self_emp_income = baseline.calculate("self_employment_income", map_to="household", period=year)

anomaly_df = pd.DataFrame({
    'market_income': hh_income,
    'employment_income': emp_income,
    'self_emp_income': self_emp_income,
    'ptc_base': ptc_base_hh,
})

# Find cases with very high income but PTC
anomalies = anomaly_df[(anomaly_df['market_income'] > 1_000_000) & (anomaly_df['ptc_base'] > 0)]

print(f"\nFound {len(anomalies)} households with >$1M income and PTC")
if len(anomalies) > 0:
    print("\nExamples:")
    print(f"{'Market Income':<15} {'Employ Income':<15} {'Self-Emp Income':<15} {'PTC':<10}")
    print("-"*55)
    for _, row in anomalies.head(5).iterrows():
        print(f"${row['market_income']:>13,.0f} ${row['employment_income']:>13,.0f} "
              f"${row['self_emp_income']:>13,.0f} ${row['ptc_base']:>9,.0f}")

print("\n" + "="*70)
print("CONCLUSION:")
print("="*70)
print("""
The presence of households with tens of millions in income receiving PTC
suggests one of these issues:

1. DATA ERROR: These might be data entry errors or outliers in the CPS
2. CALCULATION BUG: The PTC eligibility might not be checking income correctly
3. SPECIAL CASES: These could be households with huge losses offsetting income
4. AGGREGATION ISSUE: Household income might be miscalculated

The fact that they get PTC in BOTH baseline and reform suggests this is
a fundamental issue with either the data or the PTC calculation, not the reform.
""")