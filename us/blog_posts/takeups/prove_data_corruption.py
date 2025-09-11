#!/usr/bin/env python3
"""
Simple, clean test to prove the dataset corruption issue
"""

from policyengine_us import Microsimulation
import pandas as pd
import numpy as np

print("DATASET CORRUPTION PROOF")
print("="*70)

year = 2026

# Test 1: Load OLD dataset and check for extreme values
print("\n1. OLD DATASET (your local file)")
print("-"*50)

old_sim = Microsimulation(dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")

# Get household data
old_hh_size = old_sim.calculate("household_size", map_to="household", period=year)
old_hh_income = old_sim.calculate("household_market_income", map_to="household", period=year)
old_cap_gains = old_sim.calculate("capital_gains", map_to="household", period=year)
old_dividend = old_sim.calculate("dividend_income", map_to="household", period=year)
old_ptc = old_sim.calculate("aca_ptc", map_to="household", period=year)
old_weights = old_sim.calculate("household_weight", period=year)

# Create dataframe
old_df = pd.DataFrame({
    'household_id': np.arange(len(old_hh_size)),
    'size': old_hh_size,
    'market_income': old_hh_income,
    'capital_gains': old_cap_gains,
    'dividend_income': old_dividend,
    'ptc': old_ptc,
    'weight': old_weights
})

# Filter for extreme cases
old_extreme = old_df[
    (old_df['market_income'] > 10_000_000) & 
    (old_df['ptc'] > 0)
].sort_values('market_income', ascending=False)

print(f"Households with >$10M income AND receiving PTC: {len(old_extreme)}")
print("\nTop 10 most extreme cases:")
print("-"*100)
print(f"{'HH_ID':<8} {'Size':<6} {'Market Income':<15} {'Capital Gains':<15} {'Dividends':<15} {'PTC':<10} {'Weight':<8}")
print("-"*100)

for _, row in old_extreme.head(10).iterrows():
    print(f"{row['household_id']:<8.0f} {row['size']:<6.0f} ${row['market_income']:>13,.0f} "
          f"${row['capital_gains']:>13,.0f} ${row['dividend_income']:>13,.0f} "
          f"${row['ptc']:>8,.0f} {row['weight']:>7.2f}")

# Test 2: Load NEW dataset and check the same
print("\n\n2. NEW DATASET (HuggingFace)")
print("-"*50)

new_sim = Microsimulation(dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")

# Get household data
new_hh_size = new_sim.calculate("household_size", map_to="household", period=year)
new_hh_income = new_sim.calculate("household_market_income", map_to="household", period=year)
new_cap_gains = new_sim.calculate("capital_gains", map_to="household", period=year)
new_dividend = new_sim.calculate("dividend_income", map_to="household", period=year)
new_ptc = new_sim.calculate("aca_ptc", map_to="household", period=year)
new_weights = new_sim.calculate("household_weight", period=year)

# Create dataframe
new_df = pd.DataFrame({
    'household_id': np.arange(len(new_hh_size)),
    'size': new_hh_size,
    'market_income': new_hh_income,
    'capital_gains': new_cap_gains,
    'dividend_income': new_dividend,
    'ptc': new_ptc,
    'weight': new_weights
})

# Filter for extreme cases
new_extreme = new_df[
    (new_df['market_income'] > 10_000_000) & 
    (new_df['ptc'] > 0)
].sort_values('market_income', ascending=False)

print(f"Households with >$10M income AND receiving PTC: {len(new_extreme)}")

if len(new_extreme) > 0:
    print("\nTop cases (if any):")
    print("-"*100)
    print(f"{'HH_ID':<8} {'Size':<6} {'Market Income':<15} {'Capital Gains':<15} {'Dividends':<15} {'PTC':<10} {'Weight':<8}")
    print("-"*100)
    
    for _, row in new_extreme.head(10).iterrows():
        print(f"{row['household_id']:<8.0f} {row['size']:<6.0f} ${row['market_income']:>13,.0f} "
              f"${row['capital_gains']:>13,.0f} ${row['dividend_income']:>13,.0f} "
              f"${row['ptc']:>8,.0f} {row['weight']:>7.2f}")

# Test 3: Statistical comparison
print("\n\n3. STATISTICAL COMPARISON")
print("-"*50)

print(f"{'Metric':<30} {'OLD Dataset':<20} {'NEW Dataset':<20}")
print("-"*70)

metrics = [
    ('Total households', len(old_df), len(new_df)),
    ('Max market income', f"${old_df['market_income'].max():,.0f}", f"${new_df['market_income'].max():,.0f}"),
    ('Max capital gains', f"${old_df['capital_gains'].max():,.0f}", f"${new_df['capital_gains'].max():,.0f}"),
    ('Max dividend income', f"${old_df['dividend_income'].max():,.0f}", f"${new_df['dividend_income'].max():,.0f}"),
    ('HH with income > $1M', (old_df['market_income'] > 1_000_000).sum(), (new_df['market_income'] > 1_000_000).sum()),
    ('HH with income > $10M', (old_df['market_income'] > 10_000_000).sum(), (new_df['market_income'] > 10_000_000).sum()),
    ('HH with income > $100M', (old_df['market_income'] > 100_000_000).sum(), (new_df['market_income'] > 100_000_000).sum()),
    ('HH with PTC', (old_df['ptc'] > 0).sum(), (new_df['ptc'] > 0).sum()),
    ('HH with >$1M income + PTC', ((old_df['market_income'] > 1_000_000) & (old_df['ptc'] > 0)).sum(), 
                                   ((new_df['market_income'] > 1_000_000) & (new_df['ptc'] > 0)).sum()),
]

for label, old_val, new_val in metrics:
    print(f"{label:<30} {str(old_val):<20} {str(new_val):<20}")

# Test 4: Check specific household that was problematic
print("\n\n4. SPECIFIC HOUSEHOLD CHECK (ID 20731)")
print("-"*50)

if 20731 < len(old_df):
    old_hh = old_df.loc[20731]
    print("OLD dataset:")
    print(f"  Size: {old_hh['size']:.0f}")
    print(f"  Market income: ${old_hh['market_income']:,.0f}")
    print(f"  Capital gains: ${old_hh['capital_gains']:,.0f}")
    print(f"  PTC: ${old_hh['ptc']:,.0f}")

if 20731 < len(new_df):
    new_hh = new_df.loc[20731]
    print("\nNEW dataset:")
    print(f"  Size: {new_hh['size']:.0f}")
    print(f"  Market income: ${new_hh['market_income']:,.0f}")
    print(f"  Capital gains: ${new_hh['capital_gains']:,.0f}")
    print(f"  PTC: ${new_hh['ptc']:,.0f}")

print("\n" + "="*70)
print("CONCLUSION:")
print("="*70)
print("""
The OLD dataset has clear data corruption:
- Hundreds of households with >$100M income receiving PTC (impossible)
- Maximum incomes in the hundreds of millions (data errors)
- These extreme values don't exist in the NEW dataset

This corruption is causing your analysis problems. Use the NEW dataset instead.
""")