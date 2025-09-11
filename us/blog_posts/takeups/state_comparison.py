#!/usr/bin/env python3
"""
Compare old and new enhanced CPS datasets at the STATE level
Focus on understanding which states drive the differences
"""

from policyengine_us import Microsimulation
from policyengine_core.reforms import Reform
import pandas as pd
import numpy as np

# Define the reform (same for both)
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

print("Loading datasets...")
print("=" * 70)

# Load OLD dataset
old_baseline = Microsimulation(dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")
old_reformed = Microsimulation(reform=reform, dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")

# Load NEW dataset  
new_baseline = Microsimulation(dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")
new_reformed = Microsimulation(reform=reform, dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")

print("Datasets loaded successfully\n")

year = 2026

# Get state codes for all households
old_states = old_baseline.calculate("state_code", map_to="household", period=year)
new_states = new_baseline.calculate("state_code", map_to="household", period=year)

# Calculate PTC values for all households
old_ptc_base = old_baseline.calculate("aca_ptc", map_to="household", period=year)
old_ptc_reform = old_reformed.calculate("aca_ptc", map_to="household", period=year)
old_weights = old_ptc_base.weights

new_ptc_base = new_baseline.calculate("aca_ptc", map_to="household", period=year)
new_ptc_reform = new_reformed.calculate("aca_ptc", map_to="household", period=year)
new_weights = new_ptc_base.weights

# Create dataframes
old_df = pd.DataFrame({
    'state': old_states,
    'ptc_base': old_ptc_base,
    'ptc_reform': old_ptc_reform,
    'weight': old_weights,
    'net_change': old_ptc_reform - old_ptc_base
})

new_df = pd.DataFrame({
    'state': new_states,
    'ptc_base': new_ptc_base,
    'ptc_reform': new_ptc_reform,
    'weight': new_weights,
    'net_change': new_ptc_reform - new_ptc_base
})

# Aggregate by state
def state_summary(df, name):
    # Total cost by state
    state_costs = df.groupby('state').apply(
        lambda x: (x['net_change'] * x['weight']).sum()
    ).reset_index(name='total_cost')
    
    # Households gaining PTC
    gainers = df[(df['ptc_base'] == 0) & (df['ptc_reform'] > 0)]
    state_gainers = gainers.groupby('state').agg({
        'weight': 'sum',
        'ptc_reform': lambda x: np.average(x, weights=gainers.loc[x.index, 'weight'])
    }).reset_index()
    state_gainers.columns = ['state', 'gainers_weight', 'avg_gain']
    
    # Households keeping PTC
    keepers = df[(df['ptc_base'] > 0) & (df['ptc_reform'] > 0)]
    state_keepers = keepers.groupby('state').agg({
        'weight': 'sum',
        'net_change': lambda x: np.average(x, weights=keepers.loc[x.index, 'weight'])
    }).reset_index()
    state_keepers.columns = ['state', 'keepers_weight', 'avg_keeper_change']
    
    # Merge all
    result = state_costs.merge(state_gainers, on='state', how='left')
    result = result.merge(state_keepers, on='state', how='left')
    result['dataset'] = name
    
    return result

old_summary = state_summary(old_df, 'old')
new_summary = state_summary(new_df, 'new')

# Compare the datasets
comparison = old_summary.merge(new_summary, on='state', suffixes=('_old', '_new'))

# Calculate differences
comparison['cost_diff'] = comparison['total_cost_new'] - comparison['total_cost_old']
comparison['cost_pct_change'] = (comparison['total_cost_new'] / comparison['total_cost_old'] - 1) * 100
comparison['gainers_diff'] = comparison['gainers_weight_new'] - comparison['gainers_weight_old']

# Sort by absolute cost difference
comparison['abs_cost_diff'] = abs(comparison['cost_diff'])
comparison = comparison.sort_values('abs_cost_diff', ascending=False)

print("TOP 10 STATES BY ABSOLUTE COST DIFFERENCE")
print("=" * 100)
print(f"{'State':<6} {'Old Cost':<12} {'New Cost':<12} {'Diff ($)':<12} {'% Change':<10} {'Gainers Diff':<12}")
print("-" * 100)

for _, row in comparison.head(10).iterrows():
    print(f"{row['state']:<6} ${row['total_cost_old']/1e6:>10.1f}M ${row['total_cost_new']/1e6:>10.1f}M "
          f"${row['cost_diff']/1e6:>10.1f}M {row['cost_pct_change']:>9.1f}% {row['gainers_diff']:>11,.0f}")

print("\nSTATES WITH LARGEST PERCENTAGE CHANGES")
print("=" * 100)
# Filter out states with very small baseline costs to avoid misleading percentages
significant = comparison[comparison['total_cost_old'] > 1e8]  # > $100M baseline
significant = significant.sort_values('cost_pct_change')

print(f"{'State':<6} {'Old Cost':<12} {'New Cost':<12} {'% Change':<10} {'Old Gainers':<12} {'New Gainers':<12}")
print("-" * 100)

# Show biggest decreases
for _, row in significant.head(5).iterrows():
    print(f"{row['state']:<6} ${row['total_cost_old']/1e6:>10.1f}M ${row['total_cost_new']/1e6:>10.1f}M "
          f"{row['cost_pct_change']:>9.1f}% {row['gainers_weight_old']:>11,.0f} {row['gainers_weight_new']:>11,.0f}")

print("\nBiggest increases:")
for _, row in significant.tail(5).iterrows():
    print(f"{row['state']:<6} ${row['total_cost_old']/1e6:>10.1f}M ${row['total_cost_new']/1e6:>10.1f}M "
          f"{row['cost_pct_change']:>9.1f}% {row['gainers_weight_old']:>11,.0f} {row['gainers_weight_new']:>11,.0f}")

# Check ESI coverage by state
print("\n" + "=" * 100)
print("ESI COVERAGE CHANGES BY STATE (Top 10 states by population)")
print("=" * 100)

# Get ESI coverage by state
old_esi = old_baseline.calculate("has_esi", map_to="person", period=year)
old_person_state = old_baseline.calculate("state_code", map_to="person", period=year)
old_person_weight = old_baseline.calculate("person_weight", period=year)

new_esi = new_baseline.calculate("has_esi", map_to="person", period=year)
new_person_state = new_baseline.calculate("state_code", map_to="person", period=year)
new_person_weight = new_baseline.calculate("person_weight", period=year)

old_esi_df = pd.DataFrame({
    'state': old_person_state,
    'esi': old_esi,
    'weight': old_person_weight
})

new_esi_df = pd.DataFrame({
    'state': new_person_state,
    'esi': new_esi,
    'weight': new_person_weight
})

# Calculate ESI rates by state
old_esi_rates = old_esi_df.groupby('state').apply(
    lambda x: (x['esi'] * x['weight']).sum() / x['weight'].sum()
).reset_index(name='esi_rate_old')

new_esi_rates = new_esi_df.groupby('state').apply(
    lambda x: (x['esi'] * x['weight']).sum() / x['weight'].sum()
).reset_index(name='esi_rate_new')

# Get population by state for sorting
state_pop = new_esi_df.groupby('state')['weight'].sum().reset_index(name='population')

esi_comparison = old_esi_rates.merge(new_esi_rates, on='state')
esi_comparison = esi_comparison.merge(state_pop, on='state')
esi_comparison['esi_diff'] = esi_comparison['esi_rate_new'] - esi_comparison['esi_rate_old']
esi_comparison = esi_comparison.sort_values('population', ascending=False)

print(f"{'State':<6} {'Old ESI':<10} {'New ESI':<10} {'Change (pp)':<12} {'Population':<12}")
print("-" * 100)

for _, row in esi_comparison.head(10).iterrows():
    print(f"{row['state']:<6} {row['esi_rate_old']*100:>9.1f}% {row['esi_rate_new']*100:>9.1f}% "
          f"{row['esi_diff']*100:>11.1f} {row['population']/1e6:>11.1f}M")

print("\nSTATES WITH LARGEST ESI COVERAGE CHANGES")
print("-" * 100)
esi_sorted = esi_comparison.sort_values('esi_diff', ascending=False)

print("Biggest ESI increases:")
for _, row in esi_sorted.head(5).iterrows():
    print(f"{row['state']:<6} {row['esi_rate_old']*100:>9.1f}% → {row['esi_rate_new']*100:>9.1f}% "
          f"(+{row['esi_diff']*100:.1f} pp)")

print("\nBiggest ESI decreases:")
for _, row in esi_sorted.tail(5).iterrows():
    print(f"{row['state']:<6} {row['esi_rate_old']*100:>9.1f}% → {row['esi_rate_new']*100:>9.1f}% "
          f"({row['esi_diff']*100:.1f} pp)")

# Summary statistics
print("\n" + "=" * 100)
print("SUMMARY STATISTICS")
print("=" * 100)

total_old = comparison['total_cost_old'].sum()
total_new = comparison['total_cost_new'].sum()

print(f"Total cost old: ${total_old/1e9:.2f}B")
print(f"Total cost new: ${total_new/1e9:.2f}B")
print(f"Difference: ${(total_new - total_old)/1e9:.2f}B")

# States with directional changes
increases = comparison[comparison['cost_diff'] > 0]
decreases = comparison[comparison['cost_diff'] < 0]

print(f"\nStates with cost increases: {len(increases)}")
print(f"States with cost decreases: {len(decreases)}")
print(f"States with no change: {len(comparison[comparison['cost_diff'] == 0])}")

print(f"\nAverage ESI change: {esi_comparison['esi_diff'].mean()*100:.1f} percentage points")
print(f"Correlation between ESI change and cost change: {np.corrcoef(esi_comparison['esi_diff'], comparison.set_index('state').loc[esi_comparison['state']]['cost_pct_change'])[0,1]:.3f}")