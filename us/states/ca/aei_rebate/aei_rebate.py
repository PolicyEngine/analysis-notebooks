"""
AEI Rebate Program Analysis
California tax-free consumption rebate with income-based phase-out
"""

from policyengine_us import Microsimulation
from policyengine_core.reforms import Reform
from policyengine_us.model_api import *
import numpy as np


def create_aei_reform():
    """
    Creates a PolicyEngine reform that adds the California AEI rebate variable.
    
    Returns:
        Reform: PolicyEngine reform with ca_aei_rebate variable
    """
    
    class household_fpg(Variable):
        value_type = float
        entity = Household
        label = "Household's federal poverty guideline"
        definition_period = YEAR
        unit = USD

        def formula(household, period, parameters):
            n = household("household_size", period)
            state_group = household("state_group_str", period)
            p_fpg = parameters(period).gov.hhs.fpg
            p1 = p_fpg.first_person[state_group]
            pn = p_fpg.additional_person[state_group]
            return p1 + pn * (n - 1)
    

    class ca_aei_rebate_base_tax_unit(Variable):
        value_type = float
        entity = TaxUnit
        label = "California AEI rebate base (tax unit version)"
        unit = USD
        definition_period = YEAR
        defined_for = StateCode.CA

        def formula(tax_unit, period, parameters):
            # Use tax unit's own AGI
            income = tax_unit("adjusted_gross_income", period)
            fpg = tax_unit("tax_unit_fpg", period)
            income_to_fpg_ratio = where(fpg > 0, income / fpg, np.inf)

            # Phase-out parameters
            PHASEOUT_START = 1.5   # 150% FPG
            PHASEOUT_END = 1.75    # 175% FPG
            PHASEOUT_WIDTH = PHASEOUT_END - PHASEOUT_START

            # Phase-out calculation (similar to ME deduction structure)
            excess = max_(income_to_fpg_ratio - PHASEOUT_START, 0)
            phaseout_percentage = min_(1, excess / PHASEOUT_WIDTH)

            return where(
                income_to_fpg_ratio <= PHASEOUT_END,
                fpg * (1 - phaseout_percentage),
                0
            )

    class ca_aei_rebate_base(Variable):
        value_type = float
        entity = Household
        label = "California AEI rebate base"
        unit = USD
        definition_period = YEAR

        def formula(household, period, parameters):
            # Sum AGI from all tax units in the household
            income = household.sum(household.members.tax_unit("adjusted_gross_income", period))
            fpg = household("household_fpg", period)
            income_to_fpg_ratio = where(fpg > 0, income / fpg, np.inf)

            # Phase-out parameters
            PHASEOUT_START = 1.5   # 150% FPG
            PHASEOUT_END = 1.75    # 175% FPG
            PHASEOUT_WIDTH = PHASEOUT_END - PHASEOUT_START

            # Phase-out calculation (similar to ME deduction structure)
            excess = max_(income_to_fpg_ratio - PHASEOUT_START, 0)
            phaseout_percentage = min_(1, excess / PHASEOUT_WIDTH)

            return where(
                income_to_fpg_ratio <= PHASEOUT_END,
                fpg * (1 - phaseout_percentage),
                0
            )

    class AEIReform(Reform):
        def apply(self):
            self.update_variable(household_fpg)
            self.update_variable(ca_aei_rebate_base_tax_unit)
            self.update_variable(ca_aei_rebate_base)
    
    return AEIReform


def calculate_aei_rebate_statistics():
    """
    Calculate AEI rebate base program statistics for California households.

    Returns:
        dict: Dictionary with rebate base statistics including X value for VAT formula
    """

    # Create simulation with reform
    reform = create_aei_reform()
    sim = Microsimulation(
        dataset="hf://policyengine/policyengine-us-data/pooled_3_year_cps_2023.h5",
        reform=reform
    )

    # Calculate rebates for all households
    rebates = sim.calculate("ca_aei_rebate_base")

    # Filter for California households only
    household_state = sim.calculate("state_code", map_to="household")
    ca_mask = household_state == "CA"

    # Apply CA filter
    ca_rebates = rebates[ca_mask]

    # Calculate statistics (MicroSeries already contain weights)
    households_with_rebates = (ca_rebates > 0).sum()
    total_ca_households = ca_mask.sum()  # Count all CA households
    total_rebate_base = ca_rebates.sum()
    average_rebate_base = ca_rebates[ca_rebates > 0].mean() if households_with_rebates > 0 else 0

    return {
        "total_ca_households": total_ca_households,
        "households_with_rebates": households_with_rebates,
        "rebate_percentage": households_with_rebates / total_ca_households,
        "average_rebate_base": average_rebate_base,
        "total_rebate_base": total_rebate_base,
        "X_value": total_rebate_base,  # X for VAT formula
    }


def calculate_aei_rebate_tax_unit_statistics():
    """
    Calculate AEI rebate base program statistics for California tax units.

    Returns:
        dict: Dictionary with tax unit rebate base statistics including X value for VAT formula
    """

    # Create simulation with reform
    reform = create_aei_reform()
    sim = Microsimulation(
        dataset="hf://policyengine/policyengine-us-data/pooled_3_year_cps_2023.h5",
        reform=reform
    )

    # Calculate rebates for all tax units (defined_for gives 0 for non-CA)
    rebates = sim.calculate("ca_aei_rebate_base_tax_unit")

    # Use calculate_dataframe to get household-level data
    household_df = sim.calculate_dataframe(
        ["household_id", "state_code"],
        map_to="household"
    )

    # Get tax unit data
    tax_unit_df = sim.calculate_dataframe(
        ["tax_unit_id", "tax_unit_household_id"]
    )

    # Merge to get state for each tax unit
    tax_unit_with_state = tax_unit_df.merge(
        household_df[["household_id", "state_code"]],
        left_on="tax_unit_household_id",
        right_on="household_id",
        how="left"
    )

    # Create a boolean MicroSeries for CA tax units
    ca_tax_unit_mask = tax_unit_with_state["state_code"] == "CA"

    # Count CA tax units - the mask is a MicroSeries with weights embedded
    total_ca_tax_units = ca_tax_unit_mask.sum()

    # Calculate statistics (MicroSeries already contain weights)
    # Only CA tax units can have positive rebates due to defined_for
    tax_units_with_rebates = (rebates > 0).sum()

    # Total and average only include CA due to defined_for
    total_rebate_base = rebates.sum()
    average_rebate_base = rebates[rebates > 0].mean() if tax_units_with_rebates > 0 else 0

    return {
        "total_ca_tax_units": total_ca_tax_units,
        "tax_units_with_rebates": tax_units_with_rebates,
        "rebate_percentage": tax_units_with_rebates / total_ca_tax_units,
        "average_rebate_base": average_rebate_base,
        "total_rebate_base": total_rebate_base,
        "X_value": total_rebate_base,  # X for VAT formula
    }


def print_aei_results():
    """Print formatted AEI rebate base results."""

    household_results = calculate_aei_rebate_statistics()
    tax_unit_results = calculate_aei_rebate_tax_unit_statistics()

    print("=== AEI REBATE BASE PROGRAM RESULTS (HOUSEHOLD VERSION) ===")
    print(f"Total CA households: {household_results['total_ca_households']/1e6:.1f}M")
    print(f"Households with rebate base: {household_results['households_with_rebates']/1e6:.1f}M ({household_results['rebate_percentage']:.0%})")
    print(f"Average rebate base: ${household_results['average_rebate_base']:,.0f}")
    print(f"X (tax-free consumption base): ${household_results['X_value']/1e9:.1f}B")
    print(f"X (exact value): ${household_results['X_value']:,.0f}")

    print(f"\n=== AEI REBATE BASE PROGRAM RESULTS (TAX UNIT VERSION) ===")
    print(f"Total CA tax units: {tax_unit_results['total_ca_tax_units']/1e6:.1f}M")
    print(f"Tax units with rebate base: {tax_unit_results['tax_units_with_rebates']/1e6:.1f}M ({tax_unit_results['rebate_percentage']:.0%})")
    print(f"Average rebate base: ${tax_unit_results['average_rebate_base']:,.0f}")
    print(f"X (tax-free consumption base): ${tax_unit_results['X_value']/1e9:.1f}B")
    print(f"X (exact value): ${tax_unit_results['X_value']:,.0f}")

    print(f"\n=== VAT FORMULA ===")
    print(f"Household X = ${household_results['X_value']:,.0f}")
    print(f"Tax Unit X = ${tax_unit_results['X_value']:,.0f}")
    print(f"Used in VAT rate formula: t = Rs/(Cp - X - T + Ro)")


if __name__ == "__main__":
    print_aei_results()