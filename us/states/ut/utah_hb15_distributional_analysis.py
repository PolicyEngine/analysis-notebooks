"""
Utah HB 15 - Distributional Analysis
=====================================

This script analyzes the demographics of people affected by Utah HB 15's
Medicaid expansion repeal, including:
- Age distribution
- Income distribution
- Household composition
- Gender breakdown

Uses Microseries objects for weighted calculations per PolicyEngine best practices.
"""

import numpy as np
from policyengine_us import Microsimulation
from policyengine_core.periods import instant
from policyengine_core.reforms import Reform

YEAR = 2027
UT_DATASET = "hf://policyengine/policyengine-us-data/states/UT.h5"


def create_ut_medicaid_expansion_repeal():
    """Create reform that repeals Utah's Medicaid expansion."""
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


def run_distributional_analysis():
    """Run distributional analysis of who loses coverage."""

    print("Loading simulations...")
    baseline = Microsimulation(dataset=UT_DATASET)
    reform = Microsimulation(dataset=UT_DATASET, reform=create_ut_medicaid_expansion_repeal())

    # Get Microseries objects (keep weighted)
    baseline_medicaid = baseline.calculate("medicaid_enrolled", YEAR)
    reform_medicaid = reform.calculate("medicaid_enrolled", YEAR)

    # Create boolean masks for filtering
    loses_medicaid = baseline_medicaid.values & ~reform_medicaid.values

    # ACA eligibility
    reform_ptc_eligible = reform.calculate("is_aca_ptc_eligible", YEAR)
    coverage_gap = loses_medicaid & ~reform_ptc_eligible.values
    gains_aca = loses_medicaid & reform_ptc_eligible.values

    # Demographics - get Microseries
    age = baseline.calculate("age", YEAR)
    is_male = baseline.calculate("is_male", YEAR)
    spm_income = baseline.calculate("spm_unit_net_income", YEAR, map_to="person")
    employment_income = baseline.calculate("employment_income", YEAR)
    spm_unit_size = baseline.calculate("spm_unit_size", YEAR, map_to="person")
    is_child = baseline.calculate("is_child", YEAR)
    fpl_fraction = baseline.calculate("tax_unit_medicaid_income_level", YEAR, map_to="person")

    # Get weights for filtering
    weights = baseline.calculate("person_weight", YEAR).values

    # ==========================================================================
    # Helper function for weighted calculations on filtered populations
    # ==========================================================================
    def weighted_sum(mask):
        """Sum of weights for people matching mask."""
        return (weights * mask.astype(float)).sum()

    def weighted_mean(values, mask):
        """Weighted mean of values for people matching mask."""
        w = weights * mask.astype(float)
        if w.sum() == 0:
            return 0
        return np.average(values, weights=w)

    # ==========================================================================
    # Analysis
    # ==========================================================================

    total_affected = weighted_sum(loses_medicaid)
    total_coverage_gap = weighted_sum(coverage_gap)
    total_gains_aca = weighted_sum(gains_aca)

    print("\n" + "=" * 70)
    print("UTAH HB 15 - DISTRIBUTIONAL ANALYSIS")
    print(f"Analysis Year: {YEAR}")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # Overall Numbers
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("OVERALL COVERAGE IMPACT")
    print("-" * 70)
    print(f"Total people losing Medicaid:              {total_affected:>12,.0f}")
    print(f"  -> Fall into coverage gap:               {total_coverage_gap:>12,.0f} ({total_coverage_gap/total_affected*100:.1f}%)")
    print(f"  -> Transition to ACA:                    {total_gains_aca:>12,.0f} ({total_gains_aca/total_affected*100:.1f}%)")

    # -------------------------------------------------------------------------
    # Age Distribution
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("AGE DISTRIBUTION OF THOSE LOSING COVERAGE")
    print("-" * 70)

    age_values = age.values
    age_brackets = [
        (0, 17, "Children (0-17)"),
        (18, 25, "Young adults (18-25)"),
        (26, 34, "Adults (26-34)"),
        (35, 44, "Adults (35-44)"),
        (45, 54, "Adults (45-54)"),
        (55, 64, "Adults (55-64)"),
        (65, 200, "Seniors (65+)"),
    ]

    for min_age, max_age, label in age_brackets:
        in_bracket = (age_values >= min_age) & (age_values <= max_age) & loses_medicaid
        bracket_count = weighted_sum(in_bracket)
        if bracket_count > 0:
            pct = bracket_count / total_affected * 100
            print(f"  {label:30s}  {bracket_count:>10,.0f}  ({pct:>5.1f}%)")

    # Average ages
    avg_age_affected = weighted_mean(age_values, loses_medicaid)
    avg_age_coverage_gap = weighted_mean(age_values, coverage_gap)
    avg_age_aca = weighted_mean(age_values, gains_aca)
    print(f"\n  Average age (all affected):              {avg_age_affected:>10.1f} years")
    print(f"  Average age (coverage gap):              {avg_age_coverage_gap:>10.1f} years")
    print(f"  Average age (ACA transition):            {avg_age_aca:>10.1f} years")

    # -------------------------------------------------------------------------
    # Gender Distribution
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("GENDER DISTRIBUTION")
    print("-" * 70)

    is_male_values = is_male.values
    male_affected = weighted_sum(loses_medicaid & is_male_values)
    female_affected = weighted_sum(loses_medicaid & ~is_male_values)

    print(f"  Male:                                    {male_affected:>10,.0f}  ({male_affected/total_affected*100:>5.1f}%)")
    print(f"  Female:                                  {female_affected:>10,.0f}  ({female_affected/total_affected*100:>5.1f}%)")

    # -------------------------------------------------------------------------
    # Income Distribution
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("INCOME DISTRIBUTION (Household Income)")
    print("-" * 70)

    spm_income_values = spm_income.values
    avg_income_affected = weighted_mean(spm_income_values, loses_medicaid)
    avg_income_coverage_gap = weighted_mean(spm_income_values, coverage_gap)
    avg_income_aca = weighted_mean(spm_income_values, gains_aca)

    print(f"  Average household income (all affected): ${avg_income_affected:>10,.0f}")
    print(f"  Average household income (coverage gap): ${avg_income_coverage_gap:>10,.0f}")
    print(f"  Average household income (ACA transition):${avg_income_aca:>10,.0f}")

    # Income brackets
    print("\n  Income distribution of affected population:")
    income_brackets = [
        (0, 10000, "$0 - $10,000"),
        (10000, 20000, "$10,000 - $20,000"),
        (20000, 30000, "$20,000 - $30,000"),
        (30000, 40000, "$30,000 - $40,000"),
        (40000, 50000, "$40,000 - $50,000"),
        (50000, float('inf'), "$50,000+"),
    ]

    for min_inc, max_inc, label in income_brackets:
        in_bracket = (spm_income_values >= min_inc) & (spm_income_values < max_inc) & loses_medicaid
        bracket_count = weighted_sum(in_bracket)
        if bracket_count > 0:
            pct = bracket_count / total_affected * 100
            print(f"    {label:25s}  {bracket_count:>10,.0f}  ({pct:>5.1f}%)")

    # -------------------------------------------------------------------------
    # FPL Distribution
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("FEDERAL POVERTY LEVEL (FPL) DISTRIBUTION")
    print("-" * 70)

    fpl_percent = fpl_fraction.values * 100
    avg_fpl_affected = weighted_mean(fpl_percent, loses_medicaid)
    avg_fpl_coverage_gap = weighted_mean(fpl_percent, coverage_gap)
    avg_fpl_aca = weighted_mean(fpl_percent, gains_aca)

    print(f"  Average FPL % (all affected):            {avg_fpl_affected:>10.1f}%")
    print(f"  Average FPL % (coverage gap):            {avg_fpl_coverage_gap:>10.1f}%")
    print(f"  Average FPL % (ACA transition):          {avg_fpl_aca:>10.1f}%")

    fpl_brackets = [
        (0, 50, "0-50% FPL"),
        (50, 100, "50-100% FPL"),
        (100, 138, "100-138% FPL"),
        (138, 200, "138-200% FPL"),
    ]

    print("\n  FPL distribution of affected population:")
    for min_fpl, max_fpl, label in fpl_brackets:
        in_bracket = (fpl_percent >= min_fpl) & (fpl_percent < max_fpl) & loses_medicaid
        bracket_count = weighted_sum(in_bracket)
        if bracket_count > 0:
            pct = bracket_count / total_affected * 100
            print(f"    {label:25s}  {bracket_count:>10,.0f}  ({pct:>5.1f}%)")

    # -------------------------------------------------------------------------
    # Household Size
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("HOUSEHOLD SIZE DISTRIBUTION")
    print("-" * 70)

    spm_size_values = spm_unit_size.values
    avg_hh_size = weighted_mean(spm_size_values, loses_medicaid)
    print(f"  Average household size of affected:      {avg_hh_size:>10.1f}")

    for hh_size in range(1, 7):
        if hh_size < 6:
            in_size = (spm_size_values == hh_size) & loses_medicaid
            label = f"Household size {hh_size}"
        else:
            in_size = (spm_size_values >= hh_size) & loses_medicaid
            label = f"Household size 6+"
        size_count = weighted_sum(in_size)
        if size_count > 0:
            pct = size_count / total_affected * 100
            print(f"    {label:25s}  {size_count:>10,.0f}  ({pct:>5.1f}%)")

    # -------------------------------------------------------------------------
    # Employment Status
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("EMPLOYMENT STATUS")
    print("-" * 70)

    emp_income_values = employment_income.values
    has_employment = emp_income_values > 0
    employed_affected = weighted_sum(loses_medicaid & has_employment)
    unemployed_affected = weighted_sum(loses_medicaid & ~has_employment)

    avg_emp_income = weighted_mean(emp_income_values, loses_medicaid & has_employment)

    print(f"  With employment income:                  {employed_affected:>10,.0f}  ({employed_affected/total_affected*100:>5.1f}%)")
    print(f"  Without employment income:               {unemployed_affected:>10,.0f}  ({unemployed_affected/total_affected*100:>5.1f}%)")
    print(f"  Average employment income (if employed): ${avg_emp_income:>10,.0f}")

    # -------------------------------------------------------------------------
    # Adults vs Children
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("ADULTS VS CHILDREN")
    print("-" * 70)

    is_child_values = is_child.values
    adults_affected = weighted_sum(loses_medicaid & ~is_child_values)
    children_affected = weighted_sum(loses_medicaid & is_child_values)

    print(f"  Adults (18+):                            {adults_affected:>10,.0f}  ({adults_affected/total_affected*100:>5.1f}%)")
    print(f"  Children (under 18):                     {children_affected:>10,.0f}  ({children_affected/total_affected*100:>5.1f}%)")

    # -------------------------------------------------------------------------
    # Summary Table for Blog
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("SUMMARY FOR BLOG POST")
    print("=" * 70)
    print(f"""
Key demographic findings:

| Metric | All Affected | Coverage Gap | ACA Transition |
|--------|--------------|--------------|----------------|
| Number of people | {total_affected:,.0f} | {total_coverage_gap:,.0f} | {total_gains_aca:,.0f} |
| Average age | {avg_age_affected:.0f} years | {avg_age_coverage_gap:.0f} years | {avg_age_aca:.0f} years |
| Average household income | ${avg_income_affected:,.0f} | ${avg_income_coverage_gap:,.0f} | ${avg_income_aca:,.0f} |
| Average FPL | {avg_fpl_affected:.0f}% | {avg_fpl_coverage_gap:.0f}% | {avg_fpl_aca:.0f}% |
| With employment income | {employed_affected/total_affected*100:.0f}% | — | — |
""")

    return {
        "total_affected": total_affected,
        "coverage_gap": total_coverage_gap,
        "aca_transition": total_gains_aca,
        "avg_age": avg_age_affected,
        "avg_age_coverage_gap": avg_age_coverage_gap,
        "avg_age_aca": avg_age_aca,
        "avg_income": avg_income_affected,
        "avg_fpl": avg_fpl_affected,
        "pct_adults": adults_affected / total_affected * 100,
        "pct_employed": employed_affected / total_affected * 100,
    }


if __name__ == "__main__":
    results = run_distributional_analysis()
