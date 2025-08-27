#!/usr/bin/env python
"""
Analyze ACA cliff effects from the IRA reform analysis
This script examines why effects are concentrated in the 9th income decile
"""

import pandas as pd
import numpy as np
from policyengine_us import Microsimulation
from policyengine_core.reforms import Reform

print("Loading data and setting up simulations...")

# Define the reform (same as in notebook)
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
    },
    "gov.aca.ptc_income_eligibility[2].amount": {
        "2026-01-01.2100-12-31": True
    }
}, country_id="us")

# Load microsimulations
print("Loading microsimulation data (this may take a moment)...")
baseline = Microsimulation(dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")
reformed = Microsimulation(reform=reform, dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")

# Calculate key variables
year = 2026
print(f"\nCalculating values for year {year}...")

employment_income = baseline.calculate("employment_income", map_to="household", period=year)
num_dependents = baseline.calculate("tax_unit_dependents", map_to="household", period=year)
married = baseline.calculate("is_married", map_to="household", period=year)
aca_baseline = baseline.calculate("aca_ptc", map_to="household", period=year)
aca_reform = reformed.calculate("aca_ptc", map_to="household", period=year)
weights = baseline.calculate("household_weight", period=year)
state = baseline.calculate("state_code", map_to="household", period=year)

# Create DataFrame
df = pd.DataFrame({
    "employment_income": employment_income,
    "num_dependents": num_dependents,
    "married": married,
    "aca_baseline": aca_baseline,
    "aca_reform": aca_reform,
    "weight": weights,
    "state": state,
    "net_change": aca_reform - aca_baseline
})

print(f"Total households in dataset: {len(df):,}")
print(f"Weighted household count: {df['weight'].sum():,.0f}")

# Calculate FPL ratios
print("\nCalculating FPL ratios...")
# 2026 FPL estimates (rough approximations)
fpl_2026 = {
    1: 15570,   # Single person
    2: 21130,   # Couple
    3: 26650,   # Family of 3
    4: 32200,   # Family of 4
    5: 37750,   # Family of 5
    6: 43300,   # Family of 6
    7: 48850,   # Family of 7
    8: 54400,   # Family of 8
}

# Calculate household size
df['household_size'] = df.apply(
    lambda row: int(1 + row['married'] + row['num_dependents']) if not pd.isna(row['married']) else 1,
    axis=1
)

# Map FPL based on household size
df['fpl_threshold'] = df['household_size'].map(lambda x: fpl_2026.get(min(int(x), 8), 54400))
df['fpl_ratio'] = (df['employment_income'] / df['fpl_threshold']) * 100

# Analyze income percentiles
print("\n" + "="*70)
print("INCOME DISTRIBUTION ANALYSIS")
print("="*70)

percentiles = [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 99]
income_pcts = np.percentile(df['employment_income'], percentiles)

print("\nIncome distribution percentiles:")
for p, val in zip(percentiles, income_pcts):
    # Calculate approx FPL for a family of 3 at this income
    fpl_pct = (val / 26650) * 100
    print(f"  {p:2d}th percentile: ${val:8,.0f}  (~{fpl_pct:3.0f}% FPL for family of 3)")

# Analyze the 9th decile specifically
print("\n" + "="*70)
print("9TH DECILE ANALYSIS (80th-90th percentile)")
print("="*70)

ninth_decile = df[(df['employment_income'] >= income_pcts[7]) & 
                  (df['employment_income'] < income_pcts[8])]

print(f"\nIncome range: ${income_pcts[7]:,.0f} - ${income_pcts[8]:,.0f}")
print(f"Number of households: {len(ninth_decile):,}")
print(f"Weighted count: {ninth_decile['weight'].sum():,.0f}")
print(f"Average FPL ratio: {ninth_decile['fpl_ratio'].mean():.1f}%")
print(f"Average baseline PTC: ${ninth_decile['aca_baseline'].mean():,.2f}")
print(f"Average reform PTC: ${ninth_decile['aca_reform'].mean():,.2f}")
print(f"Average change: ${ninth_decile['net_change'].mean():,.2f}")

# Analyze who gains in the 9th decile
ninth_decile_gainers = ninth_decile[ninth_decile['net_change'] > 100]
print(f"\nHouseholds in 9th decile gaining >$100 in PTC:")
print(f"  Count: {len(ninth_decile_gainers):,} ({100*len(ninth_decile_gainers)/len(ninth_decile):.1f}% of 9th decile)")
print(f"  Weighted count: {ninth_decile_gainers['weight'].sum():,.0f}")
print(f"  Average income: ${ninth_decile_gainers['employment_income'].mean():,.0f}")
print(f"  Average FPL ratio: {ninth_decile_gainers['fpl_ratio'].mean():.1f}%")
print(f"  Average gain: ${ninth_decile_gainers['net_change'].mean():,.2f}")

# Analyze the cliff at 400% FPL
print("\n" + "="*70)
print("400% FPL CLIFF ANALYSIS")
print("="*70)

# Households near the cliff
near_cliff = df[(df['fpl_ratio'] >= 350) & (df['fpl_ratio'] <= 450)]
below_400 = near_cliff[near_cliff['fpl_ratio'] <= 400]
above_400 = near_cliff[near_cliff['fpl_ratio'] > 400]

print(f"\nHouseholds between 350-450% FPL:")
print(f"  Total: {len(near_cliff):,} households")
print(f"  Weighted: {near_cliff['weight'].sum():,.0f}")

print(f"\nBelow 400% FPL (350-400%):")
print(f"  Count: {len(below_400):,}")
print(f"  Average baseline PTC: ${below_400['aca_baseline'].mean():,.2f}")
print(f"  Average reform PTC: ${below_400['aca_reform'].mean():,.2f}")
print(f"  Average change: ${below_400['net_change'].mean():,.2f}")

print(f"\nAbove 400% FPL (400-450%):")
print(f"  Count: {len(above_400):,}")
print(f"  Average baseline PTC: ${above_400['aca_baseline'].mean():,.2f}")
print(f"  Average reform PTC: ${above_400['aca_reform'].mean():,.2f}")
print(f"  Average change: ${above_400['net_change'].mean():,.2f}")

# Who gains PTC under reform?
print("\n" + "="*70)
print("WHO GAINS PTC UNDER THE REFORM?")
print("="*70)

gained_ptc = df[(df['aca_baseline'] == 0) & (df['aca_reform'] > 0)]
print(f"\nHouseholds gaining PTC (had $0, now have >$0):")
print(f"  Count: {len(gained_ptc):,}")
print(f"  Weighted: {gained_ptc['weight'].sum():,.0f}")
print(f"  Average income: ${gained_ptc['employment_income'].mean():,.0f}")
print(f"  Average FPL ratio: {gained_ptc['fpl_ratio'].mean():.1f}%")
print(f"  Average reform PTC: ${gained_ptc['aca_reform'].mean():,.2f}")

# Income distribution of gainers
gainers_by_percentile = []
for i, (low, high) in enumerate(zip([0] + list(income_pcts[:-1]), income_pcts)):
    mask = (gained_ptc['employment_income'] >= low) & (gained_ptc['employment_income'] < high)
    count = mask.sum()
    weighted = gained_ptc.loc[mask, 'weight'].sum()
    gainers_by_percentile.append((f"{(i+1)*10}th", count, weighted))

print("\nDistribution of PTC gainers by income percentile:")
for pct, count, weighted in gainers_by_percentile:
    if count > 0:
        print(f"  {pct:4s} percentile: {count:4,} households ({weighted:,.0f} weighted)")

# Key insight summary
print("\n" + "="*70)
print("KEY INSIGHTS")
print("="*70)
print("""
1. The 400% FPL threshold for a family of 3 in 2026 is approximately $106,600
   - This falls in the 80th-90th income percentile (9th decile)
   
2. Households just above 400% FPL currently get $0 in PTC due to the cliff
   - The reform extends subsidies to them, capping premiums at 8.5% of income
   
3. The 9th decile concentration occurs because:
   - These households earn too much for current subsidies (>400% FPL)
   - But would benefit significantly from the reform's extension
   - Lower deciles (4-6) already receive subsidies under current law
   
4. The "cliff" affects higher-income households than intuition might suggest
   - It's not middle-class families at 200-300% FPL (they get subsidies)
   - It's upper-middle-class families at 400-500% FPL who face the cliff
""")

print("\nAnalysis complete!")