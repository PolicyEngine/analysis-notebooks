#!/usr/bin/env python3
"""
Investigate why even the NEW dataset shows high-income households getting ACA benefits
"""

from policyengine_us import Microsimulation
from policyengine_core.reforms import Reform
import pandas as pd
import numpy as np

# Define the reform
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

print("ANALYZING NEW DATASET FOR HIGH-INCOME ACA RECIPIENTS")
print("="*70)

# Use NEW dataset
baseline = Microsimulation(dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")
reformed = Microsimulation(reform=reform, dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")

year = 2026

# Get household income and PTC
hh_income = baseline.calculate("household_net_income", map_to="household", period=year)
hh_market_income = baseline.calculate("household_market_income", map_to="household", period=year)
hh_weights = baseline.calculate("household_weight", period=year)
hh_size = baseline.calculate("household_size", map_to="household", period=year)

# Get PTC in baseline and reform
ptc_base = baseline.calculate("aca_ptc", map_to="household", period=year)
ptc_reform = reformed.calculate("aca_ptc", map_to="household", period=year)
ptc_change = ptc_reform - ptc_base

# Calculate FPL percentage
fpl_by_size = {
    1: 15570, 2: 21130, 3: 26650, 4: 32200,
    5: 37750, 6: 43300, 7: 48850, 8: 54400,
}
hh_fpl_threshold = np.array([fpl_by_size.get(min(int(size), 8), 54400) for size in hh_size])
hh_fpl_pct = (hh_market_income / hh_fpl_threshold) * 100

# Create dataframe
df = pd.DataFrame({
    'net_income': hh_income,
    'market_income': hh_market_income,
    'fpl_pct': hh_fpl_pct,
    'size': hh_size,
    'ptc_base': ptc_base,
    'ptc_reform': ptc_reform,
    'ptc_change': ptc_change,
    'weight': hh_weights
})

# Calculate weighted income deciles based on net income
sorted_indices = np.argsort(df['net_income'])
sorted_df = df.iloc[sorted_indices].copy()
sorted_df['cumweight'] = sorted_df['weight'].cumsum()
total_weight = sorted_df['weight'].sum()

# Assign deciles
decile_cutoffs = []
for i in range(1, 10):
    cutoff_weight = i * total_weight / 10
    cutoff_idx = (sorted_df['cumweight'] <= cutoff_weight).sum()
    if cutoff_idx < len(sorted_df):
        decile_cutoffs.append(sorted_df.iloc[cutoff_idx]['net_income'])
    else:
        decile_cutoffs.append(sorted_df['net_income'].max())

# Assign deciles to all households
df['decile'] = 1
for i, cutoff in enumerate(decile_cutoffs):
    df.loc[df['net_income'] > cutoff, 'decile'] = i + 2

print("\n1. PTC BENEFITS BY INCOME DECILE")
print("-"*70)
print(f"{'Decile':<8} {'Income Range':<25} {'FPL Range':<20} {'Avg Base PTC':<15} {'Avg Reform PTC':<15} {'Avg Gain':<12}")
print("-"*100)

for d in range(1, 11):
    decile_data = df[df['decile'] == d]
    if len(decile_data) > 0:
        inc_min = decile_data['net_income'].min()
        inc_max = decile_data['net_income'].max()
        fpl_min = decile_data['fpl_pct'].min()
        fpl_max = decile_data['fpl_pct'].max()
        
        # Weighted averages
        total_weight = decile_data['weight'].sum()
        avg_base = (decile_data['ptc_base'] * decile_data['weight']).sum() / total_weight
        avg_reform = (decile_data['ptc_reform'] * decile_data['weight']).sum() / total_weight
        avg_gain = (decile_data['ptc_change'] * decile_data['weight']).sum() / total_weight
        
        print(f"{d:<8} ${inc_min:>8,.0f}-${inc_max:>8,.0f}  {fpl_min:>6.0f}%-{fpl_max:>8.0f}%  "
              f"${avg_base:>12,.0f}  ${avg_reform:>14,.0f}  ${avg_gain:>10,.0f}")

print("\n2. SHARE OF TOTAL PTC GAINS BY DECILE")
print("-"*70)

total_gain = (df['ptc_change'] * df['weight']).sum()
print(f"Total PTC gain from reform: ${total_gain/1e9:.2f}B\n")

print(f"{'Decile':<8} {'Share of Gains':<15} {'Cumulative':<12}")
print("-"*35)

cumulative = 0
for d in range(1, 11):
    decile_data = df[df['decile'] == d]
    decile_gain = (decile_data['ptc_change'] * decile_data['weight']).sum()
    share = (decile_gain / total_gain * 100) if total_gain > 0 else 0
    cumulative += share
    print(f"{d:<8} {share:>12.1f}%  {cumulative:>10.1f}%")

print("\n3. HIGH-INCOME RECIPIENTS (>400% FPL)")
print("-"*70)

high_income = df[df['fpl_pct'] > 400]
high_with_base = high_income[high_income['ptc_base'] > 0]
high_with_reform = high_income[high_income['ptc_reform'] > 0]

print(f"Households >400% FPL: {(high_income['weight'].sum()/1e6):.1f}M")
print(f"  With PTC in baseline: {(high_with_base['weight'].sum()/1e6):.2f}M")
print(f"  With PTC in reform: {(high_with_reform['weight'].sum()/1e6):.2f}M")
print(f"  Gaining PTC from reform: {((high_income[high_income['ptc_change'] > 0]['weight'].sum())/1e6):.2f}M")

# Check tax unit level for more accuracy
print("\n4. TAX UNIT LEVEL ANALYSIS")
print("-"*70)

tu_magi = baseline.calculate("aca_magi", map_to="tax_unit", period=year)
tu_ptc_base = baseline.calculate("aca_ptc", map_to="tax_unit", period=year)
tu_ptc_reform = reformed.calculate("aca_ptc", map_to="tax_unit", period=year)
tu_eligible_base = baseline.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=year)
tu_eligible_reform = reformed.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=year)
tu_size = baseline.calculate("tax_unit_size", map_to="tax_unit", period=year)
tu_weights = baseline.calculate("tax_unit_weight", period=year)

# Calculate FPL for tax units
tu_fpl_threshold = np.array([fpl_by_size.get(min(int(size), 8), 54400) for size in tu_size])
tu_fpl_pct = (tu_magi / tu_fpl_threshold) * 100

print(f"Tax units with MAGI >400% FPL: {((tu_fpl_pct > 400) * tu_weights).sum()/1e6:.1f}M")
print(f"  Eligible in baseline: {((tu_fpl_pct > 400) & tu_eligible_base).sum()}")
print(f"  Eligible in reform: {((tu_fpl_pct > 400) & tu_eligible_reform).sum()}")
print(f"  With PTC in baseline: {((tu_fpl_pct > 400) & (tu_ptc_base > 0)).sum()}")
print(f"  With PTC in reform: {((tu_fpl_pct > 400) & (tu_ptc_reform > 0)).sum()}")

# Show examples of high-income tax units with PTC
high_tu = (tu_fpl_pct > 400) & (tu_ptc_reform > 0)
if high_tu.any():
    print("\n5. EXAMPLES OF TAX UNITS >400% FPL WITH PTC IN REFORM")
    print("-"*70)
    
    tu_df = pd.DataFrame({
        'magi': tu_magi,
        'fpl_pct': tu_fpl_pct,
        'size': tu_size,
        'ptc_base': tu_ptc_base,
        'ptc_reform': tu_ptc_reform,
        'eligible_base': tu_eligible_base,
        'eligible_reform': tu_eligible_reform,
        'weight': tu_weights
    })
    
    high_examples = tu_df[high_tu].sort_values('magi', ascending=False).head(10)
    
    print(f"{'MAGI':<12} {'FPL%':<8} {'Size':<6} {'Base PTC':<10} {'Reform PTC':<12} {'Weight':<10}")
    print("-"*60)
    
    for _, row in high_examples.iterrows():
        print(f"${row['magi']:>10,.0f} {row['fpl_pct']:>7.0f}% {row['size']:>5.0f} "
              f"${row['ptc_base']:>9,.0f} ${row['ptc_reform']:>11,.0f} {row['weight']:>10.2f}")

print("\n" + "="*70)
print("KEY FINDINGS:")
print("="*70)