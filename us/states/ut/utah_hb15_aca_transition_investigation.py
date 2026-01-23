"""
Utah HB 15 - ACA Transition Investigation
=========================================

This script investigates why so few people (~489) gain ACA Premium Tax
Credit eligibility when ~48,000 lose Medicaid under Utah HB 15.

Key Finding:
------------
Of ~48,000 losing Medicaid:
- 77% are below 100% FPL -> fall into "coverage gap" (no ACA available)
- 19% are at 100-138% FPL -> could potentially get ACA
  - But 76% of these already have ESI coverage
  - Only 24% (~489) actually gain ACA eligibility

The high ESI rate at 100-138% FPL (~$16k/year) is surprising and may
warrant further investigation into the microdata/imputation methods.

Author: PolicyEngine
Date: January 2025
"""

import numpy as np
from policyengine_us import Microsimulation
from policyengine_core.periods import instant
from policyengine_core.reforms import Reform

# =============================================================================
# Configuration
# =============================================================================

YEAR = 2027


# =============================================================================
# Define Reform
# =============================================================================

def create_ut_medicaid_expansion_repeal():
    """Repeal Utah Medicaid expansion by setting income limit to -inf."""
    def modify_parameters(parameters):
        parameters.gov.hhs.medicaid.eligibility.categories.adult.income_limit.UT.update(
            start=instant(f"{YEAR}-01-01"),
            stop=instant("2100-12-31"),
            value=float("-inf"),
        )
        return parameters

    class reform(Reform):
        def apply(self):
            self.modify_parameters(modify_parameters)

    return reform


# =============================================================================
# Analysis Functions
# =============================================================================

def analyze_income_distribution(baseline, weights):
    """
    Analyze income distribution of expansion Medicaid adults.

    This explains why most people fall into the coverage gap:
    ACA subsidies start at 100% FPL, but most expansion adults
    are below that threshold.
    """
    print("=" * 70)
    print("PART 1: Income Distribution of Expansion Medicaid Adults")
    print("=" * 70)
    print()

    # Get expansion Medicaid adults
    is_adult_medicaid = baseline.calculate("is_adult_for_medicaid", YEAR).values

    # Get income as % of FPL
    medicaid_income = baseline.calculate("medicaid_income_level", YEAR).values

    # Filter to expansion adults
    expansion_income = medicaid_income[is_adult_medicaid]
    expansion_weights = weights[is_adult_medicaid]

    print("Medicaid Income Level        People         % of Total")
    print("-" * 70)

    brackets = [
        (float("-inf"), 0.5, "Below 50% FPL"),
        (0.5, 1.0, "50-100% FPL"),
        (1.0, 1.38, "100-138% FPL"),
    ]

    total = expansion_weights.sum()
    cumulative = 0

    for low, high, label in brackets:
        mask = (expansion_income >= low) & (expansion_income < high)
        count = expansion_weights[mask].sum()
        cumulative += count
        pct = count / total * 100
        print(f"{label:<25} {count:>12,.0f}      {pct:>5.1f}%")

    print("-" * 70)
    print(f"{'Total':<25} {total:>12,.0f}")
    print()

    below_100 = expansion_weights[expansion_income < 1.0].sum()
    print(f"KEY: {below_100/total*100:.0f}% are below 100% FPL (coverage gap)")
    print(f"     Only {(total-below_100)/total*100:.0f}% could potentially get ACA (100-138% FPL)")
    print()

    return {
        "total_expansion_adults": total,
        "below_100_fpl": below_100,
        "pct_below_100_fpl": below_100 / total * 100,
    }


def analyze_aca_transitions(baseline, reform_sim, weights):
    """
    Analyze why people at 100-138% FPL don't all get ACA.

    Finding: Most already have employer-sponsored insurance (ESI).
    """
    print("=" * 70)
    print("PART 2: Why Don't All 100-138% FPL People Get ACA?")
    print("=" * 70)
    print()

    # Get people who lose Medicaid
    baseline_medicaid = baseline.calculate("is_medicaid_eligible", YEAR).values
    reform_medicaid = reform_sim.calculate("is_medicaid_eligible", YEAR).values
    loses_medicaid = baseline_medicaid & ~reform_medicaid

    # Get income level
    medicaid_income = baseline.calculate("medicaid_income_level", YEAR).values

    # Filter to 100-138% FPL (the ACA-eligible income range)
    in_aca_range = (medicaid_income >= 1.0) & (medicaid_income < 1.38)
    loses_medicaid_in_range = loses_medicaid & in_aca_range

    # Check ACA eligibility in reform
    baseline_ptc = baseline.calculate("is_aca_ptc_eligible", YEAR).values
    reform_ptc = reform_sim.calculate("is_aca_ptc_eligible", YEAR).values

    # Categorize outcomes
    gains_aca = loses_medicaid_in_range & ~baseline_ptc & reform_ptc
    not_aca = loses_medicaid_in_range & ~reform_ptc

    total_in_range = (loses_medicaid_in_range.astype(float) * weights).sum()
    gains_aca_count = (gains_aca.astype(float) * weights).sum()
    not_aca_count = (not_aca.astype(float) * weights).sum()

    print(f"People losing Medicaid at 100-138% FPL: {total_in_range:>10,.0f}")
    print(f"  Gain ACA PTC eligibility:             {gains_aca_count:>10,.0f} ({gains_aca_count/total_in_range*100:.0f}%)")
    print(f"  Do NOT gain ACA eligibility:          {not_aca_count:>10,.0f} ({not_aca_count/total_in_range*100:.0f}%)")
    print()

    # Investigate why they don't get ACA
    print("Why don't the remaining people qualify for ACA PTC?")
    print("-" * 70)

    # Check ESI coverage
    has_esi = baseline.calculate("has_esi", YEAR).values
    esi_count = ((not_aca & has_esi).astype(float) * weights).sum()
    print(f"Have employer coverage (ESI):           {esi_count:>10,.0f} ({esi_count/not_aca_count*100:.0f}%)")

    # Check disqualifying ESI offer
    disq_esi = baseline.calculate("offered_aca_disqualifying_esi", YEAR).values
    disq_esi_count = ((not_aca & disq_esi).astype(float) * weights).sum()
    print(f"Offered disqualifying ESI:              {disq_esi_count:>10,.0f}")

    # Check Medicare
    is_medicare = baseline.calculate("is_medicare_eligible", YEAR).values
    medicare_count = ((not_aca & is_medicare).astype(float) * weights).sum()
    print(f"Medicare eligible:                      {medicare_count:>10,.0f}")

    # Check dependents
    is_dependent = baseline.calculate("is_tax_unit_dependent", YEAR).values
    dependent_count = ((not_aca & is_dependent).astype(float) * weights).sum()
    print(f"Tax unit dependents:                    {dependent_count:>10,.0f}")

    # Check incarceration
    is_incarcerated = baseline.calculate("is_incarcerated", YEAR).values
    incarcerated_count = ((not_aca & is_incarcerated).astype(float) * weights).sum()
    print(f"Incarcerated:                           {incarcerated_count:>10,.0f}")

    print()

    return {
        "total_100_138_fpl": total_in_range,
        "gains_aca": gains_aca_count,
        "not_aca_eligible": not_aca_count,
        "have_esi": esi_count,
        "pct_with_esi": esi_count / not_aca_count * 100 if not_aca_count > 0 else 0,
    }


def analyze_esi_at_low_income(baseline, weights):
    """
    Investigate the surprisingly high ESI rate at 100-138% FPL.

    This seems high - 76% ESI coverage for people making ~$16k/year.
    May warrant investigation into microdata/imputation methods.
    """
    print("=" * 70)
    print("PART 3: ESI Coverage Investigation at Low Income")
    print("=" * 70)
    print()

    # Get expansion Medicaid adults
    is_adult_medicaid = baseline.calculate("is_adult_for_medicaid", YEAR).values
    medicaid_income = baseline.calculate("medicaid_income_level", YEAR).values
    has_esi = baseline.calculate("has_esi", YEAR).values

    # Check ESI rates by income bracket
    print("ESI Coverage Rate by Income Level (Expansion Medicaid Adults)")
    print("-" * 70)

    brackets = [
        (float("-inf"), 0.5, "Below 50% FPL"),
        (0.5, 1.0, "50-100% FPL"),
        (1.0, 1.38, "100-138% FPL"),
    ]

    for low, high, label in brackets:
        in_bracket = is_adult_medicaid & (medicaid_income >= low) & (medicaid_income < high)
        bracket_weights = weights[in_bracket]
        esi_weights = weights[in_bracket & has_esi]

        total = bracket_weights.sum()
        with_esi = esi_weights.sum()
        pct = with_esi / total * 100 if total > 0 else 0

        print(f"{label:<25} {with_esi:>10,.0f} / {total:>10,.0f} = {pct:>5.1f}% with ESI")

    print()
    print("NOTE: The high ESI rate at 100-138% FPL (~$16k/year) seems")
    print("      surprisingly high and may warrant investigation into")
    print("      microdata/imputation methods.")
    print()


def run_investigation():
    """Run the full ACA transition investigation."""

    print("Loading simulations...")
    print("(This may take a moment)\n")

    baseline = Microsimulation()
    reform_sim = Microsimulation(reform=create_ut_medicaid_expansion_repeal())

    weights = baseline.calculate("person_weight", YEAR).values

    # Run analyses
    income_results = analyze_income_distribution(baseline, weights)
    aca_results = analyze_aca_transitions(baseline, reform_sim, weights)
    analyze_esi_at_low_income(baseline, weights)

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("""
Why do only ~489 people gain ACA eligibility when ~48,000 lose Medicaid?

1. COVERAGE GAP (77% of those losing Medicaid):
   - Below 100% FPL
   - ACA subsidies don't exist below 100% FPL
   - These people have NO coverage option

2. ALREADY HAVE ESI (76% of those at 100-138% FPL):
   - Already have employer-sponsored insurance
   - Disqualified from ACA Premium Tax Credits
   - They keep their ESI when losing Medicaid

3. GAIN ACA (only ~489 people):
   - At 100-138% FPL
   - Don't have ESI or other disqualifying coverage
   - These are the only ones who transition to ACA

The low ACA transition number is real - it's a combination of the
coverage gap and existing ESI coverage.
""")

    return {
        "income": income_results,
        "aca": aca_results,
    }


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    results = run_investigation()
