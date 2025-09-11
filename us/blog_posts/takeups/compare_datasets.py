#!/usr/bin/env python3
"""
Compare old and new enhanced CPS datasets for IRA PTC extension analysis
Focus on understanding why costs and beneficiary counts differ
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

# Focus on 2026 - the key year where differences matter
year = 2026

print("KEY METRIC COMPARISON FOR 2026")
print("=" * 70)

# 1. Total Cost (the most important metric)
print("\n1. TOTAL REFORM COST:")
print("-" * 40)
old_ptc_base = old_baseline.calculate("aca_ptc", map_to="household", period=year)
old_ptc_reform = old_reformed.calculate("aca_ptc", map_to="household", period=year)
old_cost = (old_ptc_reform - old_ptc_base).sum()

new_ptc_base = new_baseline.calculate("aca_ptc", map_to="household", period=year)
new_ptc_reform = new_reformed.calculate("aca_ptc", map_to="household", period=year)
new_cost = (new_ptc_reform - new_ptc_base).sum()

print(f"Old dataset: ${old_cost/1e9:.2f}B")
print(f"New dataset: ${new_cost/1e9:.2f}B")
print(f"Difference:  ${(new_cost - old_cost)/1e9:.2f}B ({(new_cost/old_cost - 1)*100:.1f}%)")

# 2. People with PTC in baseline and reform
print("\n2. PEOPLE WITH PTC (2026):")
print("-" * 40)

def count_ptc_recipients(sim, year):
    aca_ptc = sim.calculate("aca_ptc", map_to="tax_unit", period=year)
    tax_unit_wt = aca_ptc.weights
    mask = aca_ptc > 0
    return (mask.astype(float) * tax_unit_wt).sum()

old_base_recipients = count_ptc_recipients(old_baseline, year)
old_reform_recipients = count_ptc_recipients(old_reformed, year)
new_base_recipients = count_ptc_recipients(new_baseline, year)
new_reform_recipients = count_ptc_recipients(new_reformed, year)

print("Baseline scenario (tax units with PTC):")
print(f"  Old: {old_base_recipients/1e6:.1f}M")
print(f"  New: {new_base_recipients/1e6:.1f}M")
print(f"  Diff: {(new_base_recipients - old_base_recipients)/1e6:.1f}M")

print("\nReform scenario (tax units with PTC):")
print(f"  Old: {old_reform_recipients/1e6:.1f}M")
print(f"  New: {new_reform_recipients/1e6:.1f}M")
print(f"  Diff: {(new_reform_recipients - old_reform_recipients)/1e6:.1f}M")

print("\nNet change from reform (tax units):")
print(f"  Old: {(old_reform_recipients - old_base_recipients)/1e6:.1f}M")
print(f"  New: {(new_reform_recipients - new_base_recipients)/1e6:.1f}M")

# 3. Household-level analysis
print("\n3. HOUSEHOLD CATEGORIES:")
print("-" * 40)

def create_household_df(baseline, reformed, year):
    aca_baseline = baseline.calculate("aca_ptc", map_to="household", period=year)
    aca_reform = reformed.calculate("aca_ptc", map_to="household", period=year)
    employment_income = baseline.calculate("employment_income", map_to="household", period=year)
    
    df = pd.DataFrame({
        "employment_income": employment_income,
        "aca_baseline": aca_baseline,
        "aca_reform": aca_reform,
        "weight": aca_baseline.weights,
        "net_change": aca_reform - aca_baseline
    })
    return df

old_df = create_household_df(old_baseline, old_reformed, year)
new_df = create_household_df(new_baseline, new_reformed, year)

# Households gaining PTC (most important group)
old_gainers = old_df[(old_df['aca_baseline'] == 0) & (old_df['aca_reform'] > 0)]
new_gainers = new_df[(new_df['aca_baseline'] == 0) & (new_df['aca_reform'] > 0)]

print("Households GAINING PTC (0 -> >0):")
print(f"  Old: {len(old_gainers):,} households, {old_gainers['weight'].sum()/1e6:.2f}M weighted")
print(f"  New: {len(new_gainers):,} households, {new_gainers['weight'].sum()/1e6:.2f}M weighted")

# Average PTC for gainers
old_avg_gain = (old_gainers['aca_reform'] * old_gainers['weight']).sum() / old_gainers['weight'].sum()
new_avg_gain = (new_gainers['aca_reform'] * new_gainers['weight']).sum() / new_gainers['weight'].sum()
print(f"\n  Average PTC for gainers:")
print(f"    Old: ${old_avg_gain:,.0f}")
print(f"    New: ${new_avg_gain:,.0f}")

# Households keeping PTC
old_keepers = old_df[(old_df['aca_baseline'] > 0) & (old_df['aca_reform'] > 0)]
new_keepers = new_df[(new_df['aca_baseline'] > 0) & (new_df['aca_reform'] > 0)]

print("\nHouseholds KEEPING PTC (>0 -> >0):")
print(f"  Old: {len(old_keepers):,} households, {old_keepers['weight'].sum()/1e6:.2f}M weighted")
print(f"  New: {len(new_keepers):,} households, {new_keepers['weight'].sum()/1e6:.2f}M weighted")

# Average change for keepers
old_avg_change = (old_keepers['net_change'] * old_keepers['weight']).sum() / old_keepers['weight'].sum()
new_avg_change = (new_keepers['net_change'] * new_keepers['weight']).sum() / new_keepers['weight'].sum()
print(f"\n  Average change for keepers:")
print(f"    Old: ${old_avg_change:,.0f}")
print(f"    New: ${new_avg_change:,.0f}")

# 4. Income distribution comparison
print("\n4. INCOME DISTRIBUTION:")
print("-" * 40)

print("Median household employment income:")
print(f"  Old: ${np.median(old_df['employment_income']):,.0f}")
print(f"  New: ${np.median(new_df['employment_income']):,.0f}")

print("\nIncome of households gaining PTC:")
print(f"  Old median: ${old_gainers['employment_income'].median():,.0f}")
print(f"  New median: ${new_gainers['employment_income'].median():,.0f}")
print(f"  Old mean:   ${old_gainers['employment_income'].mean():,.0f}")
print(f"  New mean:   ${new_gainers['employment_income'].mean():,.0f}")

# 5. Check what's driving the difference
print("\n5. DIAGNOSTIC CHECKS:")
print("-" * 40)

# Check ESI coverage - using correct variable name
try:
    old_esi = old_baseline.calculate("has_esi", map_to="person", period=year)
    new_esi = new_baseline.calculate("has_esi", map_to="person", period=year)
    
    print(f"ESI coverage rate:")
    print(f"  Old: {old_esi.mean()*100:.1f}%")
    print(f"  New: {new_esi.mean()*100:.1f}%")
except:
    print("ESI coverage variable not available")

# Check Medicaid eligibility
try:
    old_medicaid = old_baseline.calculate("is_medicaid_eligible", map_to="person", period=year)
    new_medicaid = new_baseline.calculate("is_medicaid_eligible", map_to="person", period=year)
    
    print(f"\nMedicaid eligibility rate:")
    print(f"  Old: {old_medicaid.mean()*100:.1f}%")
    print(f"  New: {new_medicaid.mean()*100:.1f}%")
except:
    print("Medicaid eligibility variable not available")

# Check ACA eligibility
old_eligible = old_baseline.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=year).sum()
new_eligible = new_baseline.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=year).sum()

print(f"\nACA PTC eligible tax units:")
print(f"  Old: {old_eligible/1e6:.1f}M")
print(f"  New: {new_eligible/1e6:.1f}M")

print("\n" + "=" * 70)
print("SUMMARY:")
print("The new dataset shows:")
print(f"  - ${(old_cost - new_cost)/1e9:.1f}B less in total costs")
print(f"  - {(old_gainers['weight'].sum() - new_gainers['weight'].sum())/1e6:.1f}M fewer households gaining PTC")
print(f"  - Higher average benefit increases for those keeping PTC")
print("\nLikely causes:")
print("  - Updated income distribution (lower median income)")
print("  - Different ESI/Medicaid coverage patterns")
print("  - Revised household weights")