"""
Simplified test for AEI rebate base calculation
"""

from policyengine_us import CountryTaxBenefitSystem
from policyengine_core import Simulation
from aei_rebate import create_aei_reform

def test_simple():
    """Test rebate base calculation with hardcoded FPG values"""

    # Create reform
    reform = create_aei_reform()
    tax_benefit_system = CountryTaxBenefitSystem(reform=reform)

    # Single person FPG for 2024 is approximately $16,030
    FPG_SINGLE = 16030

    test_cases = [
        ("Below 150% FPG", 20000),
        ("At 150% FPG", int(FPG_SINGLE * 1.5)),  # ~24,045
        ("At 162.5% FPG", int(FPG_SINGLE * 1.625)),  # ~26,049
        ("At 175% FPG", int(FPG_SINGLE * 1.75)),  # ~28,053
        ("Above 175% FPG", 32000),
    ]

    for description, income in test_cases:
        ratio = income / FPG_SINGLE

        # Calculate expected rebate base
        if ratio <= 1.5:
            expected_rebate = FPG_SINGLE  # Full rebate base
        elif ratio >= 1.75:
            expected_rebate = 0  # No rebate base
        else:
            # Linear phase-out between 150% and 175%
            phase_out_pct = (ratio - 1.5) / 0.25
            expected_rebate = FPG_SINGLE * (1 - phase_out_pct)

        print(f"\n{description}:")
        print(f"  Income: ${income:,}")
        print(f"  FPG (approx): ${FPG_SINGLE:,}")
        print(f"  Income/FPG ratio: {ratio:.1%}")
        print(f"  Expected rebate base: ${expected_rebate:,.0f}")

if __name__ == "__main__":
    test_simple()