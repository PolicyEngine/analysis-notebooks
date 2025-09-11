#!/usr/bin/env python3
"""
Check what FPL percentages correspond to each income decile
The 9th decile might actually be middle-income relative to FPL
"""

from policyengine_us import Microsimulation
import pandas as pd
import numpy as np

baseline = Microsimulation(dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")
year = 2026

# Get incomes and calculate deciles
net_income = baseline.calculate("household_net_income_including_health_benefits", map_to="household", period=year)
weights = baseline.calculate("household_weight", period=year)

# Get household composition for FPL
household_size = baseline.calculate("household_size", map_to="household", period=year)
income = baseline.calculate("household_market_income", map_to="household", period=year)

# Calculate FPL percentage
fpl_by_size = {
    1: 15570, 2: 21130, 3: 26650, 4: 32200,
    5: 37750, 6: 43300, 7: 48850, 8: 54400,
}

fpl_threshold = np.array([fpl_by_size.get(min(int(size), 8), 54400) for size in household_size])
fpl_percentage = (income / fpl_threshold) * 100

# Calculate weighted deciles
def wquantile(values, qs, w):
    values = np.array(values)
    w = np.array(w)
    srt = np.argsort(values)
    values, w = values[srt], w[srt]
    cum_w = np.cumsum(w) / np.sum(w)
    return np.interp(qs, cum_w, values)

edges = wquantile(net_income, np.linspace(0, 1, 11), weights)

df = pd.DataFrame({
    'net_income': net_income,
    'income': income,
    'fpl_pct': fpl_percentage,
    'weight': weights,
    'household_size': household_size
})

df['decile'] = pd.cut(df['net_income'], bins=edges, labels=np.arange(1, 11), include_lowest=True)

print("FPL PERCENTAGE BY INCOME DECILE")
print("="*70)
print("\nIncome deciles and their FPL ranges:")
print(f"{'Decile':<8} {'Income Range':<30} {'FPL Range':<25} {'Avg Size':<10}")
print("-"*70)

for decile in range(1, 11):
    decile_data = df[df['decile'] == decile]
    if len(decile_data) > 0:
        inc_min = decile_data['income'].min()
        inc_max = decile_data['income'].max()
        inc_median = decile_data['income'].median()
        
        fpl_min = decile_data['fpl_pct'].min()
        fpl_max = decile_data['fpl_pct'].max()
        fpl_median = decile_data['fpl_pct'].median()
        
        avg_size = (decile_data['household_size'] * decile_data['weight']).sum() / decile_data['weight'].sum()
        
        print(f"{decile:<8} ${inc_min:>7,.0f} - ${inc_max:>7,.0f}   "
              f"{fpl_min:>5.0f}% - {fpl_max:>6.0f}%   {avg_size:>8.1f}")
        print(f"{'':8} Median: ${inc_median:>12,.0f}     Median: {fpl_median:>6.0f}%")
        print()

print("\n" + "="*70)
print("KEY INSIGHT:")
print("="*70)
print("""
If the 9th decile corresponds to households around 300-500% FPL, then
they WOULD benefit significantly from removing the 400% cliff.

But your June chart showed benefits peaking in the 6th decile, suggesting
the income distribution was different then - the 6th decile may have been
where the 300-400% FPL households were.

This indicates the dataset's income distribution has shifted significantly,
moving middle-income households (by FPL standards) into higher deciles.
""")