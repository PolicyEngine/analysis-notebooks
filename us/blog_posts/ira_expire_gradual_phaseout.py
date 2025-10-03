"""
ACA PTC reform with gradual phase-out starting at 300% FPL.

This reform keeps everything the same until 300% FPL, then implements a linear increase:
- 300% FPL: 6%
- 350% FPL: 8%
- 400% FPL: 10%
- 450% FPL: 12%
- 500% FPL: 14%
- 550% FPL: 16%
- 600% FPL: 18%
- etc. (continues linearly at 4% per 100 percentage points)
"""

from policyengine_us import Microsimulation
from policyengine_core.reforms import Reform
from policyengine_us.model_api import *
import pandas as pd
import numpy as np


def create_gradual_phaseout_reform() -> Reform:
    """
    Creates a reform with gradual PTC phase-out above 300% FPL.
    """

    class aca_ptc_phase_out_rate(Variable):
        value_type = float
        entity = TaxUnit
        label = "ACA PTC phase-out rate with gradual increase"
        unit = "/1"
        definition_period = YEAR

        def formula(tax_unit, period, parameters):
            """
            Calculate phase-out rate based on FPL ratio.
            Uses original brackets up to 300% FPL, then linear increase.
            """
            fpl_ratio = tax_unit("aca_magi_fraction", period)
            p = parameters(period).gov.aca.ptc_phase_out_rate

            # Use the original bracket structure for FPL ratios below 3.0 (300% FPL)
            # with the modified amounts from the original reform
            rate = select(
                [
                    fpl_ratio < 1.33,
                    fpl_ratio < 1.50,
                    fpl_ratio < 2.00,
                    fpl_ratio < 2.50,
                    fpl_ratio < 3.00,
                    fpl_ratio >= 3.00,
                ],
                [
                    0.0,      # Bracket 0-2: 0% (0-133% FPL)
                    0.0,      # Still 0% (133-150% FPL)
                    0.02,     # Bracket 3: 2% (150-200% FPL)
                    0.04,     # Bracket 4: 4% (200-250% FPL)
                    0.06,     # Bracket 5: 6% (250-300% FPL)
                    # Above 300% FPL: linear increase
                    # Formula: 6% + 4% per 100 percentage points above 300%
                    # = 0.06 + 0.04 * (fpl_ratio - 3.0)
                    0.06 + 0.04 * (fpl_ratio - 3.0)
                ]
            )

            return rate

    class aca_ptc_income_eligibility(Variable):
        value_type = bool
        entity = TaxUnit
        label = "ACA PTC income eligibility (no cap)"
        definition_period = YEAR

        def formula(tax_unit, period, parameters):
            """
            Remove the income eligibility cap - everyone is eligible regardless of FPL ratio.
            """
            # Original checks for other eligibility criteria
            fpl_ratio = tax_unit("aca_magi_fraction", period)

            # Must be at least at the lower bound (typically around 100% FPL for most states)
            p = parameters(period).gov.aca.ptc_income_eligibility
            lower_bound = p.brackets[0].threshold

            return fpl_ratio >= lower_bound

    class reform(Reform):
        def apply(self):
            self.update_variable(aca_ptc_phase_out_rate)
            self.update_variable(aca_ptc_income_eligibility)

    return reform


# Create the reform
gradual_phaseout_reform = create_gradual_phaseout_reform()


def run_analysis():
    """
    Run the simulation and analysis.
    """
    print("Loading baseline simulation...")
    baseline = Microsimulation(
        dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5"
    )

    print("Loading reformed simulation...")
    reformed = Microsimulation(
        reform=gradual_phaseout_reform,
        dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5"
    )

    # Calculate basic statistics
    print("\n" + "="*70)
    print("BASELINE ACA STATISTICS")
    print("="*70)

    baseline_eligible = baseline.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026).sum()
    print(f"Eligible tax units: {baseline_eligible/1e6:.2f} million")

    baseline_enrollment = baseline.calculate("takes_up_aca_if_eligible", map_to="person", period=2026).sum()
    print(f"People enrolled: {baseline_enrollment/1e6:.2f} million")

    # Baseline people with PTC
    period = 2026
    takes_up_b = baseline.calculate("takes_up_aca_if_eligible", map_to="person", period=period)
    aca_ptc_b = baseline.calculate("aca_ptc", map_to="person", period=period)
    person_wt_b = baseline.calculate("age", map_to="person", period=period).weights

    mask_b = (takes_up_b == 1) & (aca_ptc_b > 0)
    people_with_ptc_wtd_b = (mask_b.astype(float) * person_wt_b).sum()

    print(f"People receiving PTC (baseline): {people_with_ptc_wtd_b/1e6:.2f} million")

    # Reformed statistics
    print("\n" + "="*70)
    print("REFORMED ACA STATISTICS")
    print("="*70)

    # People receiving PTC under reform
    takes_up_r = reformed.calculate("takes_up_aca_if_eligible", map_to="person", period=period)
    aca_ptc_r = reformed.calculate("aca_ptc", map_to="person", period=period)
    person_wt_r = reformed.calculate("age", map_to="person", period=period).weights

    mask_r = (takes_up_r == 1) & (aca_ptc_r > 0)
    people_with_ptc_wtd_r = (mask_r.astype(float) * person_wt_r).sum()

    print(f"People receiving PTC (reform): {people_with_ptc_wtd_r/1e6:.2f} million")
    print(f"Change in people receiving PTC: {(people_with_ptc_wtd_r - people_with_ptc_wtd_b)/1e6:.2f} million")

    # Budgetary impact
    print("\n" + "="*70)
    print("BUDGETARY IMPACT")
    print("="*70)

    ptc_base = baseline.calculate("aca_ptc", map_to="household", period=2026)
    ptc_reform = reformed.calculate("aca_ptc", map_to="household", period=2026)

    weighted_total_change = ptc_reform - ptc_base
    total_impact = weighted_total_change.sum() / 1e9

    print(f"Total budgetary impact: ${total_impact:.2f} billion")

    # Household-level analysis
    print("\n" + "="*70)
    print("HOUSEHOLD-LEVEL ANALYSIS")
    print("="*70)

    year = 2026
    household_data = {
        "household_id": baseline.calculate("household_id", map_to="household", period=year),
        "state": baseline.calculate("state_code", map_to="household", period=year),
        "married": baseline.calculate("is_married", map_to="household", period=year),
        "num_dependents": baseline.calculate("tax_unit_dependents", map_to="household", period=year),
        "employment_income": baseline.calculate("employment_income", map_to="household", period=year),
        "aca_baseline": ptc_base,
        "aca_reform": ptc_reform,
        "weight": ptc_base.weights
    }

    df = pd.DataFrame(household_data)
    df["net_change"] = df["aca_reform"] - df["aca_baseline"]

    # Average change among households with any change
    mask = df["net_change"] != 0
    if mask.any():
        avg_change = (df.loc[mask, "net_change"] * df.loc[mask, "weight"]).sum() / df.loc[mask, "weight"].sum()
        print(f"Average change (households with any change): ${avg_change:,.2f}")

    # Households gaining PTC
    gained_ptc = df[(df["aca_baseline"] == 0) & (df["aca_reform"] > 0)]
    if len(gained_ptc) > 0:
        print(f"\nHouseholds newly gaining PTC: {len(gained_ptc)}")
        print(f"Weighted count: {gained_ptc['weight'].sum():,.0f}")
        avg_gain = (gained_ptc["aca_reform"] * gained_ptc["weight"]).sum() / gained_ptc["weight"].sum()
        print(f"Average new PTC amount: ${avg_gain:,.2f}")

    # Households with PTC in both scenarios
    kept_ptc = df[(df["aca_baseline"] > 0) & (df["aca_reform"] > 0)]
    if len(kept_ptc) > 0:
        print(f"\nHouseholds with PTC in both scenarios: {len(kept_ptc)}")
        print(f"Weighted count: {kept_ptc['weight'].sum():,.0f}")
        avg_change_kept = (kept_ptc["net_change"] * kept_ptc["weight"]).sum() / kept_ptc["weight"].sum()
        print(f"Average PTC increase: ${avg_change_kept:,.2f}")

    return df


if __name__ == "__main__":
    df_results = run_analysis()
    print("\n" + "="*70)
    print("Analysis complete!")
    print("="*70)
