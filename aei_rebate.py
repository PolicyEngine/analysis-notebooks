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
    
    class ca_aei_rebate(Variable):
        value_type = float
        entity = Household
        label = "California AEI rebate"
        unit = USD
        definition_period = YEAR

        def formula(household, period, parameters):
            income = household.sum(household.members("adjusted_gross_income", period))
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


def print_aei_results():
    """Print formatted AEI rebate results."""
    
    results = calculate_aei_rebate_statistics()
    
    print("=== AEI REBATE PROGRAM RESULTS ===")
    print(f"Total CA households: {results['total_ca_households']/1e6:.1f}M")
    print(f"Households with rebates: {results['households_with_rebates']/1e6:.1f}M ({results['rebate_percentage']:.0f}%)")
    print(f"Average rebate: ${results['average_rebate']:,.0f}")
    print(f"X (tax-free consumption): ${results['X_value']/1e9:.1f}B")
    print(f"X (exact value): ${results['X_value']:,.0f}")
    
    print(f"\n=== VAT FORMULA ===")
    print(f"X = ${results['X_value']:,.0f}")
    print(f"Used in VAT rate formula: t = Rs/(Cp - X - T + Ro)")


if __name__ == "__main__":
    print_aei_results()