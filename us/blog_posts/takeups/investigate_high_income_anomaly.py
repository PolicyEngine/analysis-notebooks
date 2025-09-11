#!/usr/bin/env python3
"""
Deep dive into specific high-income households that are getting large ACA benefits
This should NOT be happening - let's trace through the calculation
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

print("INVESTIGATING HIGH-INCOME HOUSEHOLDS WITH ACA BENEFITS")
print("="*70)

# Use local dataset
baseline = Microsimulation(dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")
reformed = Microsimulation(reform=reform, dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")

year = 2026

# Get household-level variables
hh_income = baseline.calculate("household_net_income", map_to="household", period=year)
hh_market_income = baseline.calculate("household_market_income", map_to="household", period=year)
hh_size = baseline.calculate("household_size", map_to="household", period=year)
hh_weights = baseline.calculate("household_weight", period=year)

# Get ACA benefits
ptc_base_hh = baseline.calculate("aca_ptc", map_to="household", period=year)
ptc_reform_hh = reformed.calculate("aca_ptc", map_to="household", period=year)
ptc_change_hh = ptc_reform_hh - ptc_base_hh

# Get tax unit level data for more detail
tu_income = baseline.calculate("adjusted_gross_income", map_to="tax_unit", period=year)
tu_size = baseline.calculate("tax_unit_size", map_to="tax_unit", period=year)
tu_weights = baseline.calculate("tax_unit_weight", period=year)
ptc_base_tu = baseline.calculate("aca_ptc", map_to="tax_unit", period=year)
ptc_reform_tu = reformed.calculate("aca_ptc", map_to="tax_unit", period=year)

# Calculate FPL for households
fpl_by_size = {
    1: 15570, 2: 21130, 3: 26650, 4: 32200,
    5: 37750, 6: 43300, 7: 48850, 8: 54400,
}
hh_fpl_threshold = np.array([fpl_by_size.get(min(int(size), 8), 54400) for size in hh_size])
hh_fpl_pct = (hh_market_income / hh_fpl_threshold) * 100

# Create household dataframe
hh_df = pd.DataFrame({
    'hh_income': hh_income,
    'hh_market_income': hh_market_income,
    'hh_size': hh_size,
    'hh_fpl_pct': hh_fpl_pct,
    'ptc_base': ptc_base_hh,
    'ptc_reform': ptc_reform_hh,
    'ptc_change': ptc_change_hh,
    'weight': hh_weights
})

# Find high-income households with large gains
high_income_gainers = hh_df[(hh_df['hh_fpl_pct'] > 600) & (hh_df['ptc_change'] > 100)]
high_income_gainers = high_income_gainers.sort_values('ptc_change', ascending=False)

print(f"\nFound {len(high_income_gainers)} high-income households (>600% FPL) with PTC gains > $100")
print(f"Total weighted count: {high_income_gainers['weight'].sum()/1e6:.3f}M households")

if len(high_income_gainers) > 0:
    print("\nTOP 20 HIGH-INCOME HOUSEHOLDS WITH PTC GAINS:")
    print("-"*70)
    print(f"{'Index':<8} {'HH Income':<12} {'FPL%':<8} {'Size':<6} {'Base PTC':<10} {'Reform PTC':<12} {'Gain':<10}")
    print("-"*70)
    
    for idx, row in high_income_gainers.head(20).iterrows():
        print(f"{idx:<8} ${row['hh_market_income']:>10,.0f} {row['hh_fpl_pct']:>7.0f}% {row['hh_size']:>5.0f} "
              f"${row['ptc_base']:>9,.0f} ${row['ptc_reform']:>11,.0f} ${row['ptc_change']:>9,.0f}")
    
    # Let's trace through a specific example
    print("\n" + "="*70)
    print("DETAILED ANALYSIS OF SPECIFIC CASES")
    print("="*70)
    
    # Pick the top few cases to analyze in detail
    for i, (idx, row) in enumerate(high_income_gainers.head(3).iterrows()):
        print(f"\nCASE {i+1}: Household index {idx}")
        print("-"*50)
        print(f"Household market income: ${row['hh_market_income']:,.0f}")
        print(f"Household net income: ${row['hh_income']:,.0f}")
        print(f"Household size: {row['hh_size']:.0f}")
        print(f"FPL percentage: {row['hh_fpl_pct']:.0f}%")
        print(f"PTC in baseline: ${row['ptc_base']:,.0f}")
        print(f"PTC in reform: ${row['ptc_reform']:,.0f}")
        print(f"PTC gain: ${row['ptc_change']:,.0f}")
        
        # Get more detailed information about this household
        # Note: We need to be careful about indexing
        household_id = idx
        
        # Get tax unit level info for this household
        # This is tricky because we need to map household to tax units
        # Let's check eligibility status
        
        # Get some key variables to understand why they're eligible
        print("\nChecking eligibility factors...")
        
        # Create a simple simulation just for this household to trace values
        # We'll check key intermediate variables
        
    # Check distribution of these anomalies
    print("\n" + "="*70)
    print("DISTRIBUTION OF HIGH-INCOME GAINERS")
    print("="*70)
    
    fpl_ranges = [(600, 800), (800, 1000), (1000, 1500), (1500, 2000), (2000, 10000)]
    
    print(f"{'FPL Range':<15} {'Count':<10} {'Weighted':<12} {'Avg Gain':<12}")
    print("-"*50)
    
    for low, high in fpl_ranges:
        mask = (high_income_gainers['hh_fpl_pct'] >= low) & (high_income_gainers['hh_fpl_pct'] < high)
        subset = high_income_gainers[mask]
        if len(subset) > 0:
            weighted_count = subset['weight'].sum()
            weighted_avg_gain = (subset['ptc_change'] * subset['weight']).sum() / weighted_count
            print(f"{low}-{high}%".ljust(15) + f"{len(subset):<10} {weighted_count/1e6:>10.3f}M ${weighted_avg_gain:>10.0f}")

# Now let's check if there's something wrong with the eligibility determination
print("\n" + "="*70)
print("CHECKING ELIGIBILITY LOGIC")
print("="*70)

# Get eligibility flags
is_eligible_base = baseline.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=year)
is_eligible_reform = reformed.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=year)

# Create tax unit dataframe
tu_df = pd.DataFrame({
    'tu_income': tu_income,
    'tu_size': tu_size,
    'eligible_base': is_eligible_base,
    'eligible_reform': is_eligible_reform,
    'ptc_base': ptc_base_tu,
    'ptc_reform': ptc_reform_tu,
    'weight': tu_weights
})

# Calculate FPL for tax units
tu_fpl_threshold = np.array([fpl_by_size.get(min(int(size), 8), 54400) for size in tu_size])
tu_df['fpl_pct'] = (tu_df['tu_income'] / tu_fpl_threshold) * 100

# Check high-income eligible tax units
high_income_eligible = tu_df[(tu_df['fpl_pct'] > 600) & (tu_df['eligible_reform'] == True)]

print(f"\nTax units >600% FPL marked as eligible in reform: {len(high_income_eligible)}")
print(f"Weighted count: {high_income_eligible['weight'].sum()/1e6:.3f}M")

if len(high_income_eligible) > 0:
    print("\nExamples of high-income eligible tax units:")
    print(f"{'Income':<12} {'FPL%':<8} {'Size':<6} {'Base Elig':<10} {'Reform Elig':<12} {'Reform PTC':<12}")
    print("-"*70)
    
    for _, row in high_income_eligible.head(10).iterrows():
        print(f"${row['tu_income']:>10,.0f} {row['fpl_pct']:>7.0f}% {row['tu_size']:>5.0f} "
              f"{'Yes' if row['eligible_base'] else 'No':>10} "
              f"{'Yes' if row['eligible_reform'] else 'No':>12} "
              f"${row['ptc_reform']:>11,.0f}")

print("\n" + "="*70)
print("HYPOTHESIS:")
print("="*70)
print("""
If high-income households are getting PTC in the reform scenario, possible causes:

1. The reform is removing the 400% FPL cliff as intended, BUT...
2. There might be a bug in how the phase-out is calculated for high incomes
3. Or these households have special circumstances (self-employed, deductions?)
4. Or there's an issue with income measurement (AGI vs MAGI vs household income)

The fact that ANY household >600% FPL is getting PTC suggests there's either:
- A calculation bug in the reform implementation
- These aren't really high-income when properly measured for ACA purposes
- They have unusual tax situations that reduce their MAGI below their market income
""")