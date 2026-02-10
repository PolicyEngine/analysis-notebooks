"""
Repeal State Dependent Exemptions - State Impact Analysis

Uses the same methodology as the PolicyEngine API (budget.py / compare.py).
sim.calc() returns MicroSeries with embedded weights, so .sum() gives
the weighted population total without manual weight multiplication.
"""

import os

import pandas as pd
from microdf import MicroSeries
from policyengine_core.reforms import Reform
from policyengine_us import Microsimulation

PERIOD = 2026

REFORM_PARAM = (
    "gov.contrib.repeal_state_dependent_exemptions.in_effect"
)


def calc_change(baseline, reformed, variable, period, **kwargs):
    """Return (baseline, reformed, change) MicroSeries for a variable."""
    b = baseline.calc(variable, period=period, **kwargs)
    r = reformed.calc(variable, period=period, **kwargs)
    return b, r, r - b


def run_analysis():
    reform = Reform.from_dict(
        {REFORM_PARAM: {"2024-01-01.2100-12-31": True}},
        country_id="us",
    )
    baseline = Microsimulation()
    reformed = Microsimulation(reform=reform)

    # --- Household-level changes (reused for national + state) ---
    _, _, hh_income_change = calc_change(
        baseline, reformed, "household_net_income", PERIOD
    )
    _, _, hh_tax_change = calc_change(
        baseline, reformed, "household_tax", PERIOD
    )
    _, _, hh_state_tax_change = calc_change(
        baseline, reformed,
        "household_state_income_tax", PERIOD,
        map_to="household",
    )
    _, _, hh_benefits_change = calc_change(
        baseline, reformed, "household_benefits", PERIOD
    )

    # --- National totals ---
    total_households = hh_income_change.count()
    net_income_impact = hh_income_change.sum()
    tax_revenue_impact = hh_tax_change.sum()
    state_tax_revenue_impact = hh_state_tax_change.sum()
    benefit_spending_impact = hh_benefits_change.sum()
    budgetary_impact = tax_revenue_impact - benefit_spending_impact

    print(f"\n=== Repeal State Dependent Exemptions ===")
    print(f"Dataset: enhanced_cps_2024 | Period: {PERIOD}")
    print(f"Reform: {REFORM_PARAM}")
    print(f"Total households: {total_households:,.0f}\n")
    print("National Budgetary Impact (API pattern):")
    for label, value in [
        ("Tax revenue impact", tax_revenue_impact),
        ("State tax revenue impact", state_tax_revenue_impact),
        ("Benefit spending impact", benefit_spending_impact),
        ("Budgetary impact", budgetary_impact),
        ("Net income impact", net_income_impact),
    ]:
        print(f"  {label + ':':<28s}${value:>15,.0f}")

    # --- State-level groupby ---
    state_code = baseline.calc("state_code", period=PERIOD)
    household_weight = baseline.calc(
        "household_weight", period=PERIOD
    )

    by_state = {
        "income_change": hh_income_change.groupby(state_code),
        "state_tax_change": hh_state_tax_change.groupby(
            state_code
        ),
    }

    affected = MicroSeries(
        (hh_income_change.abs() > 0.01).astype(float).values,
        weights=household_weight.values,
    )

    income_sum = by_state["income_change"].sum()
    income_mean = by_state["income_change"].mean()
    income_count = by_state["income_change"].count()
    tax_sum = by_state["state_tax_change"].sum()
    affected_sum = affected.groupby(state_code).sum()

    # --- Build results table ---
    state_results = []
    for state in income_sum.index:
        total_hh = income_count[state]
        affected_hh = affected_sum[state]
        state_results.append({
            "state_code": state,
            "total_households": round(total_hh),
            "avg_net_income_change": round(income_mean[state], 2),
            "total_net_income_impact": round(income_sum[state]),
            "total_state_tax_revenue_change": round(tax_sum[state]),
            "households_affected": round(affected_hh),
            "pct_households_affected": (
                round(affected_hh / total_hh * 100, 2)
                if total_hh > 0
                else 0
            ),
        })

    state_impacts = pd.DataFrame(state_results).sort_values(
        "total_net_income_impact"
    )

    total_affected = state_impacts["households_affected"].sum()
    national = pd.DataFrame([{
        "state_code": "TOTAL",
        "total_households": round(total_households),
        "avg_net_income_change": round(
            net_income_impact / total_households, 2
        ),
        "total_net_income_impact": round(net_income_impact),
        "total_state_tax_revenue_change": round(
            state_tax_revenue_impact
        ),
        "households_affected": total_affected,
        "pct_households_affected": round(
            total_affected / total_households * 100, 2
        ),
    }])

    final = pd.concat(
        [state_impacts, national], ignore_index=True
    )

    # --- Print state results ---
    print("\nState-by-State Impact Analysis:")
    print(final.to_string(index=False))

    affected_states = state_impacts[
        state_impacts["total_net_income_impact"] != 0
    ]

    print(f"\n\nAffected states: {len(affected_states)}")
    print(f"Total budgetary impact: ${budgetary_impact:,.0f}")
    print(
        f"Total state tax revenue change: "
        f"${state_tax_revenue_impact:,.0f}"
    )

    # --- Save CSV ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(
        script_dir, "state_impacts_detailed.csv"
    )
    final.to_csv(output_path, index=False)
    print(f"\nResults saved to {output_path}")

    return final


if __name__ == "__main__":
    results = run_analysis()
