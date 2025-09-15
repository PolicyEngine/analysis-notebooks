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
    
    class tax_unit_fpg(Variable):
        value_type = float
        entity = TaxUnit
        label = "Tax unit's federal poverty guideline"
        definition_period = YEAR
        unit = USD

        def formula(tax_unit, period, parameters):
            n = tax_unit("tax_unit_size", period)
            state_group = tax_unit.household("state_group_str", period)
            p_fpg = parameters(period).gov.hhs.fpg
            p1 = p_fpg.first_person[state_group]
            pn = p_fpg.additional_person[state_group]
            return p1 + pn * (n - 1)

    class ca_aei_rebate_tax_unit(Variable):
        value_type = float
        entity = TaxUnit
        label = "California AEI rebate (tax unit version)"
        unit = USD
        definition_period = YEAR
        defined_for = StateCode.CA

        def formula(tax_unit, period, parameters):
            # Use tax unit's own AGI
            income = tax_unit("adjusted_gross_income", period)
            fpg = tax_unit("tax_unit_fpg", period)
            income_to_fpg_ratio = where(fpg > 0, income / fpg, np.inf)

            # Phase-out parameters
            phaseout_start = 1.5   # 150% FPG
            phaseout_end = 1.75    # 175% FPG
            phaseout_width = phaseout_end - phaseout_start

            # Phase-out calculation (similar to ME deduction structure)
            excess = max_(income_to_fpg_ratio - phaseout_start, 0)
            phaseout_percentage = min_(1, excess / phaseout_width)

            return where(
                income_to_fpg_ratio <= phaseout_end,
                fpg * (1 - phaseout_percentage),
                0
            )

    class ca_aei_rebate(Variable):
        value_type = float
        entity = Household
        label = "California AEI rebate"
        unit = USD
        definition_period = YEAR

        def formula(household, period, parameters):
            # Sum AGI from all tax units in the household
            income = household.sum(household.members.tax_unit("adjusted_gross_income", period))
            fpg = household("household_fpg", period)
            income_to_fpg_ratio = where(fpg > 0, income / fpg, np.inf)

            # Phase-out parameters
            phaseout_start = 1.5   # 150% FPG
            phaseout_end = 1.75    # 175% FPG
            phaseout_width = phaseout_end - phaseout_start

            # Phase-out calculation (similar to ME deduction structure)
            excess = max_(income_to_fpg_ratio - phaseout_start, 0)
            phaseout_percentage = min_(1, excess / phaseout_width)

            return where(
                income_to_fpg_ratio <= phaseout_end,
                fpg * (1 - phaseout_percentage),
                0
            )

    class AEIReform(Reform):
        def apply(self):
            self.update_variable(household_fpg)
            self.update_variable(tax_unit_fpg)
            self.update_variable(ca_aei_rebate_tax_unit)
            self.update_variable(ca_aei_rebate)
    
    return AEIReform


def calculate_aei_rebate_statistics():
    """
    Calculate AEI rebate program statistics for California households.

    Returns:
        dict: Dictionary with rebate statistics including X value for VAT formula
    """

    # Create simulation with reform
    reform = create_aei_reform()
    sim = Microsimulation(
        dataset="hf://policyengine/policyengine-us-data/pooled_3_year_cps_2023.h5",
        reform=reform
    )

    # Filter for California households
    ca_mask = sim.calculate("state_code_str", map_to="household") == "CA"
    rebates = sim.calculate("ca_aei_rebate")[ca_mask]

    # Calculate statistics
    total_households = ca_mask.sum()
    households_with_rebates = (rebates > 0).sum()
    total_rebate_cost = rebates.sum()
    average_rebate = rebates[rebates > 0].mean() if households_with_rebates > 0 else 0

    return {
        "total_ca_households": total_households,
        "households_with_rebates": households_with_rebates,
        "rebate_percentage": 100 * households_with_rebates / total_households,
        "average_rebate": average_rebate,
        "total_rebate_cost": total_rebate_cost,
        "X_value": total_rebate_cost,  # X for VAT formula
    }


def calculate_aei_rebate_tax_unit_statistics():
    """
    Calculate AEI rebate program statistics for California tax units.

    Returns:
        dict: Dictionary with tax unit rebate statistics including X value for VAT formula
    """

    # Create simulation with reform
    reform = create_aei_reform()
    sim = Microsimulation(
        dataset="hf://policyengine/policyengine-us-data/pooled_3_year_cps_2023.h5",
        reform=reform
    )

    # Filter for California tax units
    ca_mask = sim.calculate("state_code_str") == "CA"
    rebates = sim.calculate("ca_aei_rebate_tax_unit")[ca_mask]

    # Calculate statistics
    total_tax_units = ca_mask.sum()
    tax_units_with_rebates = (rebates > 0).sum()
    total_rebate_cost = rebates.sum()
    average_rebate = rebates[rebates > 0].mean() if tax_units_with_rebates > 0 else 0

    return {
        "total_ca_tax_units": total_tax_units,
        "tax_units_with_rebates": tax_units_with_rebates,
        "rebate_percentage": 100 * tax_units_with_rebates / total_tax_units,
        "average_rebate": average_rebate,
        "total_rebate_cost": total_rebate_cost,
        "X_value": total_rebate_cost,  # X for VAT formula
    }


def print_aei_results():
    """Print formatted AEI rebate results."""

    household_results = calculate_aei_rebate_statistics()
    tax_unit_results = calculate_aei_rebate_tax_unit_statistics()

    print("=== AEI REBATE PROGRAM RESULTS (HOUSEHOLD VERSION) ===")
    print(f"Total CA households: {household_results['total_ca_households']/1e6:.1f}M")
    print(f"Households with rebates: {household_results['households_with_rebates']/1e6:.1f}M ({household_results['rebate_percentage']:.0f}%)")
    print(f"Average rebate: ${household_results['average_rebate']:,.0f}")
    print(f"X (tax-free consumption): ${household_results['X_value']/1e9:.1f}B")
    print(f"X (exact value): ${household_results['X_value']:,.0f}")

    print(f"\n=== AEI REBATE PROGRAM RESULTS (TAX UNIT VERSION) ===")
    print(f"Total CA tax units: {tax_unit_results['total_ca_tax_units']/1e6:.1f}M")
    print(f"Tax units with rebates: {tax_unit_results['tax_units_with_rebates']/1e6:.1f}M ({tax_unit_results['rebate_percentage']:.0f}%)")
    print(f"Average rebate: ${tax_unit_results['average_rebate']:,.0f}")
    print(f"X (tax-free consumption): ${tax_unit_results['X_value']/1e9:.1f}B")
    print(f"X (exact value): ${tax_unit_results['X_value']:,.0f}")

    print(f"\n=== VAT FORMULA ===")
    print(f"Household X = ${household_results['X_value']:,.0f}")
    print(f"Tax Unit X = ${tax_unit_results['X_value']:,.0f}")
    print(f"Used in VAT rate formula: t = Rs/(Cp - X - T + Ro)")


if __name__ == "__main__":
    print_aei_results()