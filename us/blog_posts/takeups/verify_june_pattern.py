#!/usr/bin/env python3
"""
Try to understand why the June results were so different
Check if there's a calculation order issue or parameter change
"""

from policyengine_us import Microsimulation
from policyengine_core.reforms import Reform
import pandas as pd
import numpy as np

# Use the exact same reform
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

print("INVESTIGATING THE JUNE PATTERN MYSTERY")
print("="*70)

# Try both datasets
datasets = [
    ("Local old", "/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5"),
    ("HuggingFace", "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")
]

for name, dataset_path in datasets:
    print(f"\n{name} dataset:")
    print("-"*40)
    
    # Fresh simulations to avoid any caching
    baseline = Microsimulation(dataset=dataset_path)
    reformed = Microsimulation(reform=reform, dataset=dataset_path)
    
    year = 2026
    
    # Calculate net income for deciles
    net_base = baseline.calculate(
        "household_net_income_including_health_benefits", 
        map_to="household", 
        period=year
    )
    net_reform = reformed.calculate(
        "household_net_income_including_health_benefits", 
        map_to="household", 
        period=year
    )
    weights = baseline.calculate("household_weight", period=year)
    
    # Create DataFrame
    df = pd.DataFrame({
        "net_base": net_base,
        "delta": net_reform - net_base,
        "weight": weights,
    })
    
    # Calculate weighted deciles
    def wquantile(values, qs, w):
        srt = np.argsort(values)
        values, w = values[srt], w[srt]
        cum_w = np.cumsum(w) / np.sum(w)
        return np.interp(qs, cum_w, values)
    
    edges = wquantile(df["net_base"].values, np.linspace(0, 1, 11), df["weight"].values)
    df["decile"] = pd.cut(df["net_base"], bins=edges, labels=np.arange(1, 11), include_lowest=True)
    
    # Calculate average change by decile
    decile_avg = df.groupby("decile").apply(
        lambda g: np.average(g["delta"], weights=g["weight"])
    ).reset_index(name="avg_change")
    
    print("Average change by income decile:")
    for _, row in decile_avg.iterrows():
        decile = int(row["decile"])
        change = row["avg_change"]
        print(f"  Decile {decile:2d}: ${change:>7.0f}")
    
    # Check what the peak decile characteristics are
    peak_decile = decile_avg.loc[decile_avg["avg_change"].idxmax(), "decile"]
    peak_households = df[df["decile"] == peak_decile]
    
    print(f"\nPeak decile ({peak_decile}) characteristics:")
    print(f"  Households: {len(peak_households):,}")
    print(f"  Weighted: {peak_households['weight'].sum()/1e6:.2f}M")
    print(f"  Median baseline income: ${peak_households['net_base'].median():,.0f}")

# Now let's check if the PARAMETERS changed
print("\n" + "="*70)
print("CHECKING FOR PARAMETER CHANGES")
print("="*70)

# Check key parameters that affect ACA calculations
baseline = Microsimulation(dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")

# Check FPL values
print("\nFederal Poverty Line (2026):")
fpl = baseline.tax_benefit_system.parameters.gov.hhs.fpg.us.amount
print(f"  Single person: ${fpl('2026-01-01'):,.0f}")

# Check if 400% FPL limit exists
print("\n400% FPL cliff status:")
print("  Looking for income eligibility limits...")

# Check phase-out rates
print("\nCurrent phase-out rates (2026):")
for i in range(7):
    try:
        rate = baseline.tax_benefit_system.parameters.gov.aca.ptc_phase_out_rate.brackets[i].amount
        print(f"  Bracket {i}: {rate('2026-01-01'):.3f}")
    except:
        pass

print("\n" + "="*70)
print("HYPOTHESIS:")
print("="*70)
print("""
Your June results show the EXPECTED pattern for the IRA extension:
- Peak benefits in middle-income deciles (5-7)
- These are households around 200-400% FPL
- They benefit most from removing the cliff at 400% FPL

Current results show benefits concentrated in decile 9:
- This suggests high-income households (>400% FPL)
- They shouldn't get much benefit under normal circumstances

Possible explanations:
1. The MODEL CODE changed - the 400% FPL cliff may not be properly implemented
2. The DATASET changed - income distribution or household composition shifted
3. A BUG was introduced - the reform isn't being applied correctly
4. PARAMETER VALUES changed - FPL or phase-out rates were updated

The fact that BOTH datasets now show the wrong pattern suggests it's a 
code/parameter issue, not a data issue.
""")