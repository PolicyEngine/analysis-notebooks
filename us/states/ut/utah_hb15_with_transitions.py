"""Utah HB 15 analysis with parent Medicaid transitions tracked."""

import numpy as np
from policyengine_us import Microsimulation
from policyengine_core.periods import instant
from policyengine_core.reforms import Reform

YEAR = 2027
UT_DATASET = "hf://policyengine/policyengine-us-data/states/UT.h5"

def create_ut_medicaid_expansion_repeal():
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


def run_analysis():
    print("Loading simulations with Utah-specific dataset...")
    baseline = Microsimulation(dataset=UT_DATASET)
    reform = Microsimulation(dataset=UT_DATASET, reform=create_ut_medicaid_expansion_repeal())

    # Weights
    person_weights = baseline.calculate("person_weight", YEAR).values
    
    # Medicaid categories
    baseline_category = baseline.calculate("medicaid_category", YEAR).values
    reform_category = reform.calculate("medicaid_category", YEAR).values
    
    # Medicaid enrollment (accounts for takeup rate)
    baseline_enrolled = baseline.calculate("medicaid_enrolled", YEAR).values
    reform_enrolled = reform.calculate("medicaid_enrolled", YEAR).values
    
    # Medicaid benefits
    baseline_medicaid = baseline.calculate("medicaid", YEAR).values
    reform_medicaid = reform.calculate("medicaid", YEAR).values
    
    # ACA eligibility
    baseline_ptc_eligible = baseline.calculate("is_aca_ptc_eligible", YEAR).values
    reform_ptc_eligible = reform.calculate("is_aca_ptc_eligible", YEAR).values
    
    # Adult expansion flag
    is_adult_for_medicaid = baseline.calculate("is_adult_for_medicaid", YEAR).values
    
    # Category constants
    ADULT = "ADULT"
    PARENT = "PARENT"
    NONE = "NONE"
    
    print("\n" + "="*70)
    print("UTAH HB 15 - MEDICAID TRANSITION ANALYSIS")
    print("="*70)
    
    # People ENROLLED in expansion Medicaid (not just eligible)
    # Using is_adult_for_medicaid to identify expansion adults who are enrolled
    on_expansion_enrolled = baseline_enrolled & is_adult_for_medicaid
    expansion_enrolled_count = (on_expansion_enrolled * person_weights).sum()
    print(f"\nPeople enrolled in expansion Medicaid (baseline): {expansion_enrolled_count:,.0f}")
    
    # Also check using category
    on_expansion_by_cat = (baseline_category == ADULT) & baseline_enrolled
    expansion_by_cat_count = (on_expansion_by_cat * person_weights).sum()
    print(f"  (Using category check: {expansion_by_cat_count:,.0f})")
    
    # What happens to enrolled expansion adults under reform?
    # Still enrolled (transitioned to another category)
    still_enrolled = on_expansion_enrolled & reform_enrolled
    still_enrolled_count = (still_enrolled * person_weights).sum()
    
    # Transitioned to parent Medicaid
    to_parent = on_expansion_enrolled & reform_enrolled & (reform_category == PARENT)
    to_parent_count = (to_parent * person_weights).sum()
    
    # Transitioned to other Medicaid
    to_other = on_expansion_enrolled & reform_enrolled & (reform_category != PARENT) & (reform_category != ADULT)
    to_other_count = (to_other * person_weights).sum()
    
    # Lost enrollment entirely
    lost_enrollment = on_expansion_enrolled & ~reform_enrolled
    lost_enrollment_count = (lost_enrollment * person_weights).sum()
    
    print(f"\nTransitions from expansion Medicaid:")
    print(f"  → Still enrolled (other category): {still_enrolled_count:,.0f} ({still_enrolled_count/expansion_enrolled_count*100:.1f}%)")
    print(f"    - Parent Medicaid: {to_parent_count:,.0f}")
    print(f"    - Other categories: {to_other_count:,.0f}")
    print(f"  → Lost enrollment: {lost_enrollment_count:,.0f} ({lost_enrollment_count/expansion_enrolled_count*100:.1f}%)")
    
    # Of those who lost enrollment, who gains ACA?
    gains_aca = lost_enrollment & ~baseline_ptc_eligible & reform_ptc_eligible
    gains_aca_count = (gains_aca * person_weights).sum()
    
    coverage_gap = lost_enrollment & ~reform_ptc_eligible
    coverage_gap_count = (coverage_gap * person_weights).sum()
    
    print(f"\nOf those losing enrollment ({lost_enrollment_count:,.0f}):")
    print(f"  → Gain ACA eligibility: {gains_aca_count:,.0f} ({gains_aca_count/lost_enrollment_count*100:.1f}%)")
    print(f"  → Coverage gap: {coverage_gap_count:,.0f} ({coverage_gap_count/lost_enrollment_count*100:.1f}%)")
    
    # Fiscal impact
    baseline_total = (baseline_medicaid * person_weights).sum()
    reform_total = (reform_medicaid * person_weights).sum()
    medicaid_savings = baseline_total - reform_total
    
    print(f"\n" + "="*70)
    print("FISCAL IMPACT")
    print("="*70)
    print(f"\nMedicaid spending savings: ${medicaid_savings/1e6:,.0f} million")
    print(f"  Federal share (90%): ${medicaid_savings*0.9/1e6:,.0f} million")
    print(f"  State share (10%): ${medicaid_savings*0.1/1e6:,.0f} million")
    
    # Summary for blog post
    print(f"\n" + "="*70)
    print("REVISED SUMMARY FOR BLOG POST")
    print("="*70)
    print(f"""
Key results for 2027:

- ~{expansion_enrolled_count/1000:.0f},000 people enrolled in expansion Medicaid
- ~{still_enrolled_count/1000:.0f},000 ({still_enrolled_count/expansion_enrolled_count*100:.0f}%) would retain Medicaid (other categories)
  - ~{to_parent_count/1000:.0f},000 via parent Medicaid
  - ~{to_other_count/1000:.0f},000 via other categories
- ~{lost_enrollment_count/1000:.0f},000 ({lost_enrollment_count/expansion_enrolled_count*100:.0f}%) would lose Medicaid enrollment
  - ~{gains_aca_count/1000:.0f},000 ({gains_aca_count/lost_enrollment_count*100:.0f}%) could transition to ACA
  - ~{coverage_gap_count/1000:.0f},000 ({coverage_gap_count/lost_enrollment_count*100:.0f}%) would fall into coverage gap
- State savings: ~${medicaid_savings*0.1/1e6:.0f} million/year
""")


if __name__ == "__main__":
    run_analysis()
