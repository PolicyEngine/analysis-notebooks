"""Analyze Utah HB 15 Medicaid transitions with microsimulation."""

from policyengine_us import Microsimulation
from policyengine_core.periods import instant
from policyengine_core.reforms import Reform
import numpy as np

YEAR = 2027
DATASET = "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5"

def create_ut_medicaid_expansion_repeal():
    def modify_parameters(parameters):
        parameters.gov.hhs.medicaid.eligibility.categories.adult.income_limit.UT.update(
            start=instant(f'{YEAR}-01-01'),
            stop=instant('2100-12-31'),
            value=float('-inf'),
        )
        return parameters

    class reform(Reform):
        def apply(self):
            self.modify_parameters(modify_parameters)

    return reform


def main():
    print("Loading baseline microsimulation...")
    baseline = Microsimulation(dataset=DATASET)
    
    print("Loading reform microsimulation...")
    reform = Microsimulation(dataset=DATASET, reform=create_ut_medicaid_expansion_repeal())
    
    # Filter to Utah residents - map household state to person level
    # state_code is defined at household level, map to person
    state_code = baseline.calculate("state_code", YEAR, map_to="person").values
    in_utah = state_code == "UT"
    
    # Get person weights
    person_weight = baseline.calculate("person_weight", YEAR).values
    
    # Get Medicaid categories (baseline vs reform) - these return string values
    baseline_category = baseline.calculate("medicaid_category", YEAR).values
    reform_category = reform.calculate("medicaid_category", YEAR).values
    
    # Get Medicaid amounts (person level)
    baseline_medicaid = baseline.calculate("medicaid", YEAR).values
    reform_medicaid = reform.calculate("medicaid", YEAR).values
    
    print(f"\nDebug: Total people in sample: {len(baseline_category):,}")
    print(f"Debug: People in Utah: {in_utah.sum():,}")
    print(f"Debug: Unique baseline categories: {np.unique(baseline_category)}")
    
    # Categories are strings now
    ADULT = "ADULT"
    PARENT = "PARENT"
    NONE = "NONE"
    
    print("\n" + "="*70)
    print("UTAH HB 15 MEDICAID TRANSITION ANALYSIS")
    print("="*70)
    
    # People on expansion Medicaid in baseline (in Utah)
    on_expansion_baseline = (baseline_category == ADULT) & in_utah
    expansion_count = (on_expansion_baseline * person_weight).sum()
    print(f"\nPeople on expansion Medicaid (baseline): {expansion_count:,.0f}")
    
    # What happens to expansion adults under reform?
    # Transition to parent Medicaid
    to_parent = on_expansion_baseline & (reform_category == PARENT)
    to_parent_count = (to_parent * person_weight).sum()
    
    # Transition to other Medicaid categories (not NONE, not ADULT, not PARENT)
    to_other_medicaid = on_expansion_baseline & (reform_category != NONE) & (reform_category != ADULT) & (reform_category != PARENT)
    to_other_count = (to_other_medicaid * person_weight).sum()
    
    # Fall to no Medicaid
    to_none = on_expansion_baseline & (reform_category == NONE)
    to_none_count = (to_none * person_weight).sum()
    
    print(f"\nTransitions from expansion Medicaid:")
    print(f"  → Parent Medicaid: {to_parent_count:,.0f}")
    print(f"  → Other Medicaid: {to_other_count:,.0f}")
    print(f"  → No Medicaid: {to_none_count:,.0f}")
    
    # Of those who lose all Medicaid, how many gain ACA?
    loses_medicaid = on_expansion_baseline & (reform_medicaid == 0)
    loses_medicaid_count = (loses_medicaid * person_weight).sum()
    
    # People above 100% FPL can get ACA
    income_level = baseline.calculate("medicaid_income_level", YEAR).values
    above_100_fpl = income_level >= 1.0
    
    gains_aca = loses_medicaid & above_100_fpl
    gains_aca_count = (gains_aca * person_weight).sum()
    
    # Coverage gap = loses Medicaid and below 100% FPL (can't get ACA)
    coverage_gap = loses_medicaid & ~above_100_fpl
    coverage_gap_count = (coverage_gap * person_weight).sum()
    
    if loses_medicaid_count > 0:
        print(f"\nOf those losing Medicaid ({loses_medicaid_count:,.0f}):")
        print(f"  → Can get ACA (>=100% FPL): {gains_aca_count:,.0f} ({gains_aca_count/loses_medicaid_count*100:.1f}%)")
        print(f"  → Coverage gap (<100% FPL): {coverage_gap_count:,.0f} ({coverage_gap_count/loses_medicaid_count*100:.1f}%)")
    
    # Fiscal impact (person-level Medicaid only for now)
    utah_weight = person_weight * in_utah
    
    baseline_medicaid_total = (baseline_medicaid * utah_weight).sum()
    reform_medicaid_total = (reform_medicaid * utah_weight).sum()
    medicaid_savings = baseline_medicaid_total - reform_medicaid_total
    
    print(f"\n" + "="*70)
    print("FISCAL IMPACT")
    print("="*70)
    print(f"\nMedicaid spending change: -${medicaid_savings/1e6:,.0f} million")
    print(f"  Federal share (90%): -${medicaid_savings*0.9/1e6:,.0f} million")
    print(f"  State share (10%): -${medicaid_savings*0.1/1e6:,.0f} million")
    
    # Summary for blog post
    print(f"\n" + "="*70)
    print("SUMMARY FOR BLOG POST")
    print("="*70)
    print(f"\n- ~{expansion_count/1000:.0f},000 people currently on expansion Medicaid")
    if to_parent_count > 0:
        print(f"- ~{to_parent_count/1000:.0f},000 would transition to parent Medicaid")
    if to_other_count > 0:
        print(f"- ~{to_other_count/1000:.0f},000 would transition to other Medicaid categories")
    print(f"- ~{loses_medicaid_count/1000:.0f},000 would lose Medicaid coverage entirely")
    if loses_medicaid_count > 0:
        print(f"  - ~{gains_aca_count/1000:.0f},000 ({gains_aca_count/loses_medicaid_count*100:.0f}%) could transition to ACA")
        print(f"  - ~{coverage_gap_count/1000:.0f},000 ({coverage_gap_count/loses_medicaid_count*100:.0f}%) would fall into coverage gap")
    print(f"- State savings: ~${medicaid_savings*0.1/1e6:.0f} million/year")


if __name__ == "__main__":
    main()
