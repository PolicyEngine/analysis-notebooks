"""
SC H.4216 Budget Impact Analysis
Simple script to calculate the budgetary impact of H.4216 with default 5.21% top rate.
"""

from policyengine_us import Microsimulation
from policyengine_us.reforms.states.sc.h4216.sc_h4216 import create_sc_h4216
from policyengine_core.reforms import Reform
import numpy as np

SC_DATASET = "hf://policyengine/policyengine-us-data/staging/states/SC.h5"
TAX_YEAR = 2026

def create_h4216_reform():
    """
    SC H.4216 Reform with default rates:
    - 1.99% up to $30k
    - 5.21% over $30k (default)
    """
    param_reform = Reform.from_dict(
        {
            "gov.contrib.states.sc.h4216.in_effect": {
                "2026-01-01.2100-12-31": True
            }
        },
        country_id="us",
    )
    base_reform = create_sc_h4216()
    return (base_reform, param_reform)

print("Loading baseline...")
baseline = Microsimulation(dataset=SC_DATASET)

print("Loading reform (H.4216 with 5.21% top rate)...")
reform = create_h4216_reform()
reform_sim = Microsimulation(dataset=SC_DATASET, reform=reform)

# Calculate tax impact - use .values to get raw numpy arrays (avoid MicroSeries auto-weighting)
baseline_tax = baseline.calculate("sc_income_tax", period=TAX_YEAR, map_to="tax_unit").values
reform_tax = reform_sim.calculate("sc_income_tax", period=TAX_YEAR, map_to="tax_unit").values
weight = baseline.calculate("tax_unit_weight", period=TAX_YEAR).values

tax_change = reform_tax - baseline_tax
budget_impact = (tax_change * weight).sum()

# Summary stats (all using raw numpy arrays, no MicroSeries)
baseline_revenue = (baseline_tax * weight).sum()
reform_revenue = (reform_tax * weight).sum()
total_weight = weight.sum()

pct_decrease = weight[tax_change < -1].sum() / total_weight * 100
pct_increase = weight[tax_change > 1].sum() / total_weight * 100
pct_unchanged = weight[np.abs(tax_change) <= 1].sum() / total_weight * 100

print("\n" + "="*60)
print("SC H.4216 BUDGET IMPACT (5.21% Top Rate)")
print("="*60)
print(f"\nBaseline SC Income Tax Revenue: ${baseline_revenue:,.0f}")
print(f"Reform SC Income Tax Revenue:   ${reform_revenue:,.0f}")
print(f"\n>>> BUDGET IMPACT: ${budget_impact:,.0f} <<<")
print(f"\nRFA Estimate: -$119,100,000")
print(f"Difference from RFA: ${budget_impact - (-119100000):,.0f}")
print(f"Accuracy: {(1 - abs(budget_impact - (-119100000)) / 119100000) * 100:.1f}%")
print("\n" + "-"*60)
print(f"Tax units with DECREASE: {pct_decrease:.1f}%")
print(f"Tax units with INCREASE: {pct_increase:.1f}%")
print(f"Tax units UNCHANGED:     {pct_unchanged:.1f}%")
print("="*60)
