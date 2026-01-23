"""
Utah HB 15 (2026) - Medicaid Expansion Repeal Analysis
======================================================

This script analyzes the impact of Utah HB 15, which would repeal
Medicaid expansion if federal matching falls below 85%.

Bill Reference: https://le.utah.gov/~2026/bills/static/HB0015.html

Key Findings:
- ~48,000 people would lose Medicaid eligibility
- ~47,000 would fall into the "coverage gap" (no ACA subsidies available)
- Utah would save ~$32 million/year (10% state share)
- Federal government would save ~$285 million/year (net of ACA costs)

Author: PolicyEngine
Date: January 2025
"""

import numpy as np
from policyengine_us import Microsimulation
from policyengine_us.reforms.states.ut.medicaid import (
    repeal_ut_medicaid_expansion,
)

# =============================================================================
# Configuration
# =============================================================================

YEAR = 2027  # Analysis year (reform starts 2027)
FEDERAL_FMAP_EXPANSION = 0.90  # Federal share of expansion Medicaid
STATE_FMAP_EXPANSION = 0.10  # State share of expansion Medicaid


# =============================================================================
# Initialize Simulations
# =============================================================================

def run_analysis():
    """Run the full Utah HB 15 Medicaid expansion repeal analysis."""

    print("Loading simulations...")
    print("(This may take a moment to download microdata)\n")

    # Baseline: Current law with Medicaid expansion
    baseline = Microsimulation()

    # Reform: Medicaid expansion repealed
    reform = Microsimulation(reform=repeal_ut_medicaid_expansion)

    # ==========================================================================
    # Extract Data
    # ==========================================================================

    # Person-level weights
    person_weights = baseline.calculate("person_weight", YEAR).values

    # Tax unit-level weights (for ACA PTC)
    tu_weights = baseline.calculate("tax_unit_weight", YEAR).values

    # Medicaid eligibility (person level)
    baseline_medicaid_eligible = baseline.calculate(
        "is_medicaid_eligible", YEAR
    ).values
    reform_medicaid_eligible = reform.calculate(
        "is_medicaid_eligible", YEAR
    ).values

    # Adult expansion category (directly affected by reform)
    baseline_adult_eligible = baseline.calculate(
        "is_adult_for_medicaid", YEAR
    ).values
    reform_adult_eligible = reform.calculate(
        "is_adult_for_medicaid", YEAR
    ).values

    # Medicaid benefits (person level, dollar amount)
    baseline_medicaid_benefits = baseline.calculate("medicaid", YEAR).values
    reform_medicaid_benefits = reform.calculate("medicaid", YEAR).values

    # ACA Premium Tax Credit eligibility (person level)
    baseline_ptc_eligible = baseline.calculate(
        "is_aca_ptc_eligible", YEAR
    ).values
    reform_ptc_eligible = reform.calculate("is_aca_ptc_eligible", YEAR).values

    # ACA Premium Tax Credit amount (tax unit level)
    baseline_ptc = baseline.calculate("premium_tax_credit", YEAR).values
    reform_ptc = reform.calculate("premium_tax_credit", YEAR).values

    # ==========================================================================
    # Calculate Coverage Changes
    # ==========================================================================

    # People who lose Medicaid eligibility
    loses_medicaid = baseline_medicaid_eligible & ~reform_medicaid_eligible

    # People who lose Medicaid but gain ACA PTC eligibility
    loses_medicaid_gains_ptc = (
        loses_medicaid & ~baseline_ptc_eligible & reform_ptc_eligible
    )

    # People who fall into coverage gap (lose Medicaid, don't get ACA)
    loses_medicaid_no_coverage = loses_medicaid & ~reform_ptc_eligible

    # Weighted counts
    people_losing_medicaid = np.sum(loses_medicaid.astype(float) * person_weights)
    people_gaining_ptc = np.sum(
        loses_medicaid_gains_ptc.astype(float) * person_weights
    )
    people_in_coverage_gap = np.sum(
        loses_medicaid_no_coverage.astype(float) * person_weights
    )

    # Adult category changes
    adults_losing_eligibility = np.sum(
        (baseline_adult_eligible & ~reform_adult_eligible).astype(float)
        * person_weights
    )

    # ==========================================================================
    # Calculate Fiscal Impact
    # ==========================================================================

    # Total Medicaid spending
    baseline_medicaid_total = np.sum(baseline_medicaid_benefits * person_weights)
    reform_medicaid_total = np.sum(reform_medicaid_benefits * person_weights)
    medicaid_savings = baseline_medicaid_total - reform_medicaid_total

    # Split by federal/state share
    federal_medicaid_savings = medicaid_savings * FEDERAL_FMAP_EXPANSION
    state_medicaid_savings = medicaid_savings * STATE_FMAP_EXPANSION

    # ACA PTC changes (federal cost)
    baseline_ptc_total = np.sum(baseline_ptc * tu_weights)
    reform_ptc_total = np.sum(reform_ptc * tu_weights)
    ptc_increase = reform_ptc_total - baseline_ptc_total

    # Net fiscal impact
    net_federal_savings = federal_medicaid_savings - ptc_increase
    net_state_savings = state_medicaid_savings  # No offset
    net_total_savings = medicaid_savings - ptc_increase

    # Cost per person losing coverage
    cost_per_person = medicaid_savings / people_losing_medicaid

    # ==========================================================================
    # Print Results
    # ==========================================================================

    print("=" * 65)
    print("UTAH HB 15 - MEDICAID EXPANSION REPEAL ANALYSIS")
    print(f"Analysis Year: {YEAR}")
    print("=" * 65)
    print()

    # Coverage Impact
    print("COVERAGE IMPACT")
    print("-" * 65)
    print(f"People losing Medicaid eligibility:      {people_losing_medicaid:>15,.0f}")
    print(f"  Adults (expansion category):           {adults_losing_eligibility:>15,.0f}")
    print()
    print("Coverage transitions for those losing Medicaid:")
    print(f"  -> Gain ACA PTC eligibility:           {people_gaining_ptc:>15,.0f}")
    print(f"  -> Fall into coverage gap:             {people_in_coverage_gap:>15,.0f}")
    print()

    # Fiscal Impact
    print("FISCAL IMPACT")
    print("-" * 65)
    print(f"Total Medicaid savings:                  ${medicaid_savings:>14,.0f}")
    print(f"  Federal share (90%):                   ${federal_medicaid_savings:>14,.0f}")
    print(f"  State/Utah share (10%):                ${state_medicaid_savings:>14,.0f}")
    print()
    print(f"Offsetting federal ACA costs:            ${ptc_increase:>14,.0f}")
    print()
    print(f"NET SAVINGS:")
    print(f"  Federal government:                    ${net_federal_savings:>14,.0f}")
    print(f"  State of Utah:                         ${net_state_savings:>14,.0f}")
    print(f"  Total:                                 ${net_total_savings:>14,.0f}")
    print()

    # Summary Statistics
    print("SUMMARY STATISTICS")
    print("-" * 65)
    print(f"Average Medicaid benefit per person:     ${cost_per_person:>14,.0f}")
    print(f"Percent falling into coverage gap:       {people_in_coverage_gap/people_losing_medicaid*100:>14.1f}%")
    print()

    # Return results as dictionary for further analysis
    return {
        "year": YEAR,
        "coverage": {
            "people_losing_medicaid": people_losing_medicaid,
            "adults_losing_eligibility": adults_losing_eligibility,
            "people_gaining_ptc": people_gaining_ptc,
            "people_in_coverage_gap": people_in_coverage_gap,
        },
        "fiscal": {
            "medicaid_savings_total": medicaid_savings,
            "medicaid_savings_federal": federal_medicaid_savings,
            "medicaid_savings_state": state_medicaid_savings,
            "aca_ptc_increase": ptc_increase,
            "net_federal_savings": net_federal_savings,
            "net_state_savings": net_state_savings,
            "net_total_savings": net_total_savings,
        },
        "per_capita": {
            "avg_medicaid_benefit": cost_per_person,
        },
    }


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    results = run_analysis()

    print("=" * 65)
    print("POLICY CONTEXT")
    print("=" * 65)
    print("""
Utah HB 15 (2026) would repeal Medicaid expansion if the federal
matching rate (FMAP) falls below 85%. Currently, the federal government
pays 90% of expansion Medicaid costs.

Key policy implications:

1. COVERAGE GAP: Most people losing Medicaid (~99%) would fall into
   the "coverage gap" - they earn too much for traditional Medicaid
   but too little for ACA subsidies (which start at 100% FPL).

2. FISCAL TRADEOFF: Utah saves ~$32M/year, but ~47,000 residents
   lose health coverage with no alternative.

3. FEDERAL IMPACT: Federal government saves ~$285M/year net, as
   very few people transition to ACA subsidies.

Bill Reference: https://le.utah.gov/~2026/bills/static/HB0015.html
""")
