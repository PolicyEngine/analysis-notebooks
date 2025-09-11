#!/usr/bin/env python3
"""
Diagnose why high-income households (9th decile) are getting such large benefits
This should NOT be happening if the 400% FPL cliff is properly implemented
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

print("DIAGNOSING HIGH-INCOME BENEFIT ANOMALY")
print("="*70)

# Use local dataset
baseline = Microsimulation(dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")
reformed = Microsimulation(reform=reform, dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")

year = 2026

# Get key variables
income = baseline.calculate("adjusted_gross_income", map_to="tax_unit", period=year)
ptc_base = baseline.calculate("aca_ptc", map_to="tax_unit", period=year)
ptc_reform = reformed.calculate("aca_ptc", map_to="tax_unit", period=year)
weights = baseline.calculate("tax_unit_weight", period=year)

# Get household size for FPL calculation
household_size = baseline.calculate("tax_unit_size", map_to="tax_unit", period=year)

# Approximate FPL thresholds for 2026
fpl_single = 15570
fpl_by_size = {
    1: 15570,
    2: 21130,
    3: 26650,
    4: 32200,
    5: 37750,
    6: 43300,
    7: 48850,
    8: 54400,
}

# Calculate FPL percentage for each household
fpl_threshold = np.array([fpl_by_size.get(min(int(size), 8), 54400) for size in household_size])
fpl_percentage = (income / fpl_threshold) * 100

# Create analysis dataframe
df = pd.DataFrame({
    'income': income,
    'household_size': household_size,
    'fpl_threshold': fpl_threshold,
    'fpl_pct': fpl_percentage,
    'ptc_base': ptc_base,
    'ptc_reform': ptc_reform,
    'ptc_change': ptc_reform - ptc_base,
    'weight': weights
})

print("\n1. WHO IS GETTING BENEFITS ABOVE 400% FPL?")
print("-"*50)

# Households above 400% FPL
above_400 = df[df['fpl_pct'] > 400]
print(f"Households above 400% FPL: {len(above_400):,}")
print(f"Weighted count: {above_400['weight'].sum()/1e6:.2f}M")

# In baseline (should be zero or very small)
above_400_with_base = above_400[above_400['ptc_base'] > 0]
print(f"\nWith PTC in baseline: {len(above_400_with_base):,}")
print(f"Weighted: {above_400_with_base['weight'].sum()/1e6:.2f}M")
print(f"Average baseline PTC: ${above_400_with_base['ptc_base'].mean():.0f}")

# In reform
above_400_with_reform = above_400[above_400['ptc_reform'] > 0]
print(f"\nWith PTC in reform: {len(above_400_with_reform):,}")
print(f"Weighted: {above_400_with_reform['weight'].sum()/1e6:.2f}M")
print(f"Average reform PTC: ${above_400_with_reform['ptc_reform'].mean():.0f}")

print("\n2. INCOME RANGES WITH LARGEST GAINS")
print("-"*50)

fpl_ranges = [
    (0, 138, "0-138% (Medicaid)"),
    (138, 200, "138-200%"),
    (200, 250, "200-250%"),
    (250, 300, "250-300%"),
    (300, 350, "300-350%"),
    (350, 400, "350-400%"),
    (400, 500, "400-500%"),
    (500, 600, "500-600%"),
    (600, 1000, "600-1000%"),
    (1000, 10000, ">1000%"),
]

print(f"{'FPL Range':<20} {'Households':<12} {'Avg Gain':<12} {'Total Gain':<12}")
print("-"*60)

for low, high, label in fpl_ranges:
    mask = (df['fpl_pct'] >= low) & (df['fpl_pct'] < high)
    subset = df[mask]
    if len(subset) > 0:
        weighted_avg = (subset['ptc_change'] * subset['weight']).sum() / subset['weight'].sum()
        total = (subset['ptc_change'] * subset['weight']).sum()
        print(f"{label:<20} {subset['weight'].sum()/1e6:>10.2f}M ${weighted_avg:>10.0f} ${total/1e9:>10.2f}B")

print("\n3. SPECIFIC HIGH-INCOME EXAMPLES")
print("-"*50)

# Find high-income households with big gains
high_gainers = df[(df['fpl_pct'] > 400) & (df['ptc_change'] > 1000)]
high_gainers = high_gainers.sort_values('ptc_change', ascending=False)

print("Examples of high-income households with large PTC gains:")
print(f"{'Income':<12} {'FPL%':<8} {'Size':<6} {'Base PTC':<10} {'Reform PTC':<12} {'Gain':<10}")
print("-"*70)

for _, row in high_gainers.head(10).iterrows():
    print(f"${row['income']:>10,.0f} {row['fpl_pct']:>7.0f}% {row['household_size']:>5.0f} "
          f"${row['ptc_base']:>9,.0f} ${row['ptc_reform']:>11,.0f} ${row['ptc_change']:>9,.0f}")

print("\n4. CHECKING THE 400% FPL CLIFF")
print("-"*50)

# Check households right around 400% FPL
near_cliff = df[(df['fpl_pct'] >= 380) & (df['fpl_pct'] <= 420)]
print(f"Households near 400% FPL (380-420%): {len(near_cliff):,}")

# Group by baseline vs reform eligibility
patterns = near_cliff.groupby(['ptc_base'] > 0)['ptc_reform'].apply(lambda x: (x > 0).sum())
print("\nEligibility patterns near cliff:")
print(patterns)

print("\n" + "="*70)
print("CONCLUSIONS:")
print("="*70)
print("""
If high-income households (>400% FPL) are getting large PTC amounts in the
reform scenario, this means:

1. The reform is CORRECTLY removing the 400% FPL cliff (as intended)

2. BUT the benefits should still be small for high-income households because
   the subsidies phase out based on the percentage of income

3. The fact that 9th decile gets the MOST benefits suggests either:
   - The phase-out rates aren't working correctly
   - The income distribution has many households just above 400% FPL
   - There's a calculation bug giving excessive subsidies to high earners

Your June results were likely using a version where either:
- The 400% cliff was more strictly enforced
- The phase-out rates were different
- The income distribution was different

Without the exact June dataset/code version, we can't recreate those results.
""")