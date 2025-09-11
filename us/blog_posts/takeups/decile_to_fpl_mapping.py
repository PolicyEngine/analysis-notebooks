#!/usr/bin/env python3
"""
Map income deciles to FPL percentages to understand which deciles are affected
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

print("MAPPING INCOME DECILES TO FPL PERCENTAGES")
print("="*70)

# Load datasets
old_baseline = Microsimulation(dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")
old_reformed = Microsimulation(reform=reform, dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")

new_baseline = Microsimulation(dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")
new_reformed = Microsimulation(reform=reform, dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")

year = 2026

def analyze_deciles(baseline, reformed, dataset_name):
    print(f"\n{dataset_name} DATASET ANALYSIS")
    print("-"*50)
    
    # Get household income and weights
    income = baseline.calculate("household_net_income", map_to="household", period=year)
    weights = baseline.calculate("household_weight", period=year)
    
    # Get tax unit income for FPL calculation
    tu_income = baseline.calculate("adjusted_gross_income", map_to="tax_unit", period=year)
    tu_size = baseline.calculate("tax_unit_size", map_to="tax_unit", period=year)
    tu_weights = baseline.calculate("tax_unit_weight", period=year)
    
    # Calculate FPL percentage
    fpl_by_size = {
        1: 15570, 2: 21130, 3: 26650, 4: 32200,
        5: 37750, 6: 43300, 7: 48850, 8: 54400,
    }
    fpl_threshold = np.array([fpl_by_size.get(min(int(size), 8), 54400) for size in tu_size])
    fpl_pct = (tu_income / fpl_threshold) * 100
    
    # Get PTC changes
    ptc_base = baseline.calculate("aca_ptc", map_to="household", period=year)
    ptc_reform = reformed.calculate("aca_ptc", map_to="household", period=year)
    ptc_change = ptc_reform - ptc_base
    
    # Calculate weighted income deciles
    sorted_indices = np.argsort(income)
    sorted_income = income[sorted_indices]
    sorted_weights = weights[sorted_indices]
    cumsum_weights = np.cumsum(sorted_weights)
    total_weight = cumsum_weights[-1]
    
    # Find decile thresholds
    decile_thresholds = []
    for i in range(1, 11):
        target_weight = i * total_weight / 10
        idx = np.searchsorted(cumsum_weights, target_weight)
        if idx < len(sorted_income):
            decile_thresholds.append(sorted_income[idx])
    
    # Assign deciles
    deciles = np.zeros_like(income)
    for i, threshold in enumerate(decile_thresholds):
        deciles[income <= threshold] = i + 1
    
    # Create household dataframe
    hh_df = pd.DataFrame({
        'income': income,
        'decile': deciles,
        'ptc_change': ptc_change,
        'weight': weights
    })
    
    # Create tax unit dataframe for FPL analysis
    tu_df = pd.DataFrame({
        'income': tu_income,
        'fpl_pct': fpl_pct,
        'weight': tu_weights
    })
    
    print("\n1. INCOME DECILE THRESHOLDS:")
    print(f"{'Decile':<10} {'Income Range':<30} {'Avg PTC Gain':<15}")
    print("-"*55)
    
    for i in range(10):
        decile_num = i + 1
        decile_data = hh_df[hh_df['decile'] == decile_num]
        
        if len(decile_data) > 0:
            min_income = decile_data['income'].min()
            max_income = decile_data['income'].max()
            weighted_avg_gain = (decile_data['ptc_change'] * decile_data['weight']).sum() / decile_data['weight'].sum()
            
            print(f"{decile_num:<10} ${min_income:>10,.0f} - ${max_income:>10,.0f} ${weighted_avg_gain:>12,.0f}")
    
    print("\n2. FPL DISTRIBUTION BY INCOME PERCENTILE:")
    print(f"{'Percentile':<15} {'Income':<15} {'Typical FPL%':<15}")
    print("-"*45)
    
    percentiles = [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 99]
    for p in percentiles:
        income_at_p = np.percentile(income, p)
        # Find typical FPL% for tax units at this income level
        income_range = (tu_df['income'] >= income_at_p * 0.9) & (tu_df['income'] <= income_at_p * 1.1)
        if income_range.any():
            typical_fpl = tu_df[income_range]['fpl_pct'].median()
        else:
            typical_fpl = np.nan
        
        print(f"P{p:<13} ${income_at_p:>12,.0f} {typical_fpl:>12.0f}%")
    
    print("\n3. PTC GAINS BY DECILE:")
    print(f"{'Decile':<10} {'Total Gain':<15} {'% of Total':<12}")
    print("-"*37)
    
    total_gain = (hh_df['ptc_change'] * hh_df['weight']).sum()
    for i in range(10):
        decile_num = i + 1
        decile_data = hh_df[hh_df['decile'] == decile_num]
        decile_gain = (decile_data['ptc_change'] * decile_data['weight']).sum()
        pct_of_total = (decile_gain / total_gain * 100) if total_gain > 0 else 0
        
        print(f"{decile_num:<10} ${decile_gain/1e9:>12.2f}B {pct_of_total:>10.1f}%")
    
    return hh_df

# Analyze both datasets
old_df = analyze_deciles(old_baseline, old_reformed, "OLD")
new_df = analyze_deciles(new_baseline, new_reformed, "NEW")

print("\n" + "="*70)
print("KEY FINDINGS:")
print("="*70)
print("""
Look at which deciles correspond to which FPL percentages.
The 9th decile might actually be in the 250-400% FPL range where
ACA subsidies are still available but phasing out.

If the 9th decile shows high gains, check if it's because:
1. They're in the sweet spot for ACA subsidies (200-400% FPL)
2. The reform removes caps that were limiting their subsidies
3. There's a concentration of households just below 400% FPL
""")