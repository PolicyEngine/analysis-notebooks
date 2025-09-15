"""
Simple household test for AEI rebate base calculation
"""

from policyengine_us import CountryTaxBenefitSystem
from policyengine_core import Simulation
from aei_rebate import create_aei_reform

def test_household_rebate():
    """Test household rebate base calculations at different income levels"""

    # Create reform
    reform = create_aei_reform()
    tax_benefit_system = CountryTaxBenefitSystem(reform=reform)

    # Test cases with different income levels
    test_cases = [
        ("Below 150% FPG", 20000, "full rebate base"),
        ("At 150% FPG", 24046, "full rebate base"),
        ("At 162.5% FPG", 26050, "50% rebate base"),
        ("At 175% FPG", 28054, "zero rebate base"),
        ("Above 175% FPG", 32000, "zero rebate base"),
    ]

    for description, income, expected in test_cases:
        test_situation = {
            "households": {
                "household": {
                    "members": ["person"],
                    "state_code_str": {"2024": "CA"}
                }
            },
            "tax_units": {
                "tax_unit": {
                    "members": ["person"],
                    "adjusted_gross_income": {"2024": income},
                }
            },
            "people": {
                "person": {}
            }
        }

        sim = Simulation(tax_benefit_system=tax_benefit_system, situation=test_situation)
        rebate = sim.calculate("ca_aei_rebate_base", 2024)
        fpg = sim.calculate("household_fpg", period=2024)

        ratio = income / fpg[0] if fpg[0] > 0 else 0

        print(f"\n{description}:")
        print(f"  Income: ${income:,}")
        print(f"  FPG: ${fpg[0]:,.0f}")
        print(f"  Income/FPG ratio: {ratio:.1%}")
        print(f"  Rebate base: ${rebate[0]:,.0f}")
        print(f"  Expected: {expected}")

if __name__ == "__main__":
    test_household_rebate()