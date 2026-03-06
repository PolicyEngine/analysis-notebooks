"""
SC H.4216 Budget Impact Comparison Across Datasets
Compares budgetary impacts using production, staging, and test datasets.
"""

from policyengine_us import Microsimulation
from policyengine_us.reforms.states.sc.h4216.sc_h4216 import create_sc_h4216
from policyengine_core.reforms import Reform
import numpy as np

TAX_YEAR = 2026

DATASETS = {
    "Production": "hf://policyengine/policyengine-us-data/states/SC.h5",
    "Test (Mar)": "hf://policyengine/test/mar/SC.h5"
}

def create_h4216_reform(top_rate=0.0521):
    param_reform = Reform.from_dict(
        {
            "gov.contrib.states.sc.h4216.in_effect": {
                "2026-01-01.2100-12-31": True
            },
            "gov.contrib.states.sc.h4216.rates[1].rate": {
                "2026-01-01.2100-12-31": top_rate
            }
        },
        country_id="us",
    )
    base_reform = create_sc_h4216()
    return (base_reform, param_reform)

def calculate_impact(dataset_path, top_rate):
    """Calculate budget impact for a given dataset and top rate."""
    baseline = Microsimulation(dataset=dataset_path)
    reform = create_h4216_reform(top_rate=top_rate)
    reform_sim = Microsimulation(dataset=dataset_path, reform=reform)

    baseline_tax = baseline.calculate("sc_income_tax", period=TAX_YEAR, map_to="tax_unit").values
    reform_tax = reform_sim.calculate("sc_income_tax", period=TAX_YEAR, map_to="tax_unit").values
    weight = baseline.calculate("tax_unit_weight", period=TAX_YEAR).values

    tax_change = reform_tax - baseline_tax
    budget_impact = (tax_change * weight).sum()
    total_units = weight.sum()
    baseline_revenue = (baseline_tax * weight).sum()

    return {
        "budget_impact": budget_impact,
        "total_units": total_units,
        "baseline_revenue": baseline_revenue
    }

# Run analysis
results = {}
for name, path in DATASETS.items():
    print(f"\nProcessing {name}...")
    results[name] = {
        "5.21%": calculate_impact(path, 0.0521),
        "5.39%": calculate_impact(path, 0.0539)
    }
    print(f"  Done!")

# Print results
print("\n" + "="*90)
print("SC H.4216 BUDGET IMPACT COMPARISON ACROSS DATASETS")
print("="*90)

print(f"\n{'Dataset':<15} {'Tax Units':>15} {'Baseline Rev':>18} {'5.21% Impact':>18} {'5.39% Impact':>18}")
print("-"*90)

for name in DATASETS.keys():
    r = results[name]
    print(f"{name:<15} {r['5.21%']['total_units']:>15,.0f} ${r['5.21%']['baseline_revenue']:>16,.0f} ${r['5.21%']['budget_impact']:>16,.0f} ${r['5.39%']['budget_impact']:>16,.0f}")

print("-"*90)
print(f"{'RFA Estimate':<15} {'2,757,573':>15} {'N/A':>18} ${-309000000:>16,.0f} ${-119100000:>16,.0f}")
print("="*90)

# Accuracy comparison
print("\n" + "="*90)
print("ACCURACY vs RFA")
print("="*90)
print(f"{'Dataset':<15} {'5.21% PE':>15} {'vs RFA -$309M':>18} {'5.39% PE':>15} {'vs RFA -$119M':>18}")
print("-"*90)
for name in DATASETS.keys():
    impact_521 = results[name]["5.21%"]["budget_impact"]
    impact_539 = results[name]["5.39%"]["budget_impact"]
    acc_521 = (1 - abs(impact_521 - (-309000000)) / 309000000) * 100
    acc_539 = (1 - abs(impact_539 - (-119100000)) / 119100000) * 100
    print(f"{name:<15} ${impact_521:>14,.0f} {acc_521:>16.1f}% ${impact_539:>14,.0f} {acc_539:>16.1f}%")
print("="*90)
