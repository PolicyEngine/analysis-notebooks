#!/usr/bin/env python3
"""
Debug script for abolish_salt analysis with memory monitoring and optimization.
"""

import gc
import psutil
import sys
from policyengine_us import Microsimulation
from policyengine_core.reforms import Reform
import pandas as pd
import numpy as np

def print_memory_usage(label=""):
    """Print current memory usage."""
    process = psutil.Process()
    mem_info = process.memory_info()
    print(f"\n{label}")
    print(f"Memory usage: {mem_info.rss / 1024 / 1024:.2f} MB")
    print(f"Available system memory: {psutil.virtual_memory().available / 1024 / 1024:.2f} MB")
    print(f"System memory percent: {psutil.virtual_memory().percent}%")

def force_garbage_collection():
    """Force garbage collection and print stats."""
    collected = gc.collect()
    print(f"Garbage collector: collected {collected} objects")
    return collected

def create_reform():
    """Create the SALT cap abolishment reform."""
    return Reform.from_dict({
        "gov.irs.deductions.itemized.salt_and_real_estate.cap.JOINT": {
            "2025-01-01.2100-12-31": 0
        },
        "gov.irs.deductions.itemized.salt_and_real_estate.cap.SINGLE": {
            "2025-01-01.2100-12-31": 0
        },
        "gov.irs.deductions.itemized.salt_and_real_estate.cap.SEPARATE": {
            "2025-01-01.2100-12-31": 0
        },
        "gov.irs.deductions.itemized.salt_and_real_estate.cap.SURVIVING_SPOUSE": {
            "2025-01-01.2100-12-31": 0
        },
        "gov.irs.deductions.itemized.salt_and_real_estate.cap.HEAD_OF_HOUSEHOLD": {
            "2025-01-01.2100-12-31": 0
        },
        "gov.irs.deductions.itemized.salt_and_real_estate.phase_out.floor.applies": {
            "2025-01-01.2029-12-31": False
        }
    }, country_id="us")

def main():
    print("=" * 60)
    print("ABOLISH SALT CAP ANALYSIS - DEBUG VERSION")
    print("=" * 60)

    print_memory_usage("Initial memory state")

    # Step 1: Create reform
    print("\n1. Creating reform...")
    reform = create_reform()
    print("Reform created successfully")

    # Step 2: Create baseline microsimulation
    print("\n2. Creating baseline microsimulation...")
    print_memory_usage("Before baseline creation")

    try:
        cd_baseline = Microsimulation(dataset="hf://policyengine/test/sparse_cd_stacked_2023.h5")
        print(f"Baseline microsimulation created")

        # Fix state_fips
        cd_geoids = cd_baseline.calculate("congressional_district_geoid").values
        correct_state_fips = cd_geoids // 100
        cd_baseline.set_input("state_fips", 2023, correct_state_fips)

        print_memory_usage("After baseline creation")
    except MemoryError as e:
        print(f"ERROR: Memory error creating baseline: {e}")
        print_memory_usage("At error")
        return

    # Step 3: Calculate baseline variables
    print("\n3. Calculating baseline variables...")
    try:
        household_ids = cd_baseline.calculate("household_id")
        print(f"  - household_ids calculated: {len(household_ids)} households")

        state_fips = cd_baseline.calculate("state_fips")
        print(f"  - state_fips calculated")

        cd_geoids = cd_baseline.calculate("congressional_district_geoid")
        print(f"  - congressional_district_geoid calculated")

        print_memory_usage("Before income/tax calculations")

        baseline_income = cd_baseline.calculate("household_net_income", period=2025)
        print(f"  - baseline_income calculated")

        baseline_tax = cd_baseline.calculate("income_tax", period=2025)
        print(f"  - baseline_tax calculated")

        weights = cd_baseline.calculate("household_weight", period=2025)
        print(f"  - weights calculated")

        print_memory_usage("After baseline calculations")

    except MemoryError as e:
        print(f"ERROR: Memory error calculating baseline: {e}")
        print_memory_usage("At error")
        return

    # Step 4: Free baseline simulation memory before creating reform
    print("\n4. Optimizing memory before reform simulation...")

    # Save baseline data to dataframe immediately
    baseline_df = pd.DataFrame({
        'household_id': household_ids,
        'state_fips': state_fips,
        'congressional_district_geoid': cd_geoids,
        'baseline_income': baseline_income,
        'baseline_tax': baseline_tax,
        'household_weight': weights
    })

    # Clear individual arrays
    del household_ids, state_fips, cd_geoids, baseline_income, baseline_tax, weights

    # Clear baseline simulation
    del cd_baseline

    force_garbage_collection()
    print_memory_usage("After clearing baseline simulation")

    # Step 5: Create reform microsimulation
    print("\n5. Creating reform microsimulation...")
    try:
        cd_reformed = Microsimulation(
            dataset="hf://policyengine/test/sparse_cd_stacked_2023.h5",
            reform=reform
        )

        # Fix state_fips again for reform
        cd_geoids = cd_reformed.calculate("congressional_district_geoid").values
        correct_state_fips = cd_geoids // 100
        cd_reformed.set_input("state_fips", 2023, correct_state_fips)

        print("Reform microsimulation created")
        print_memory_usage("After reform creation")

    except MemoryError as e:
        print(f"ERROR: Memory error creating reform simulation: {e}")
        print_memory_usage("At error")
        # Save baseline results even if reform fails
        baseline_df.to_csv("baseline_results.csv", index=False)
        print("Baseline results saved to baseline_results.csv")
        return

    # Step 6: Calculate reform variables
    print("\n6. Calculating reform variables...")
    try:
        print_memory_usage("Before reform income calculation")
        reform_income = cd_reformed.calculate("household_net_income", period=2025)
        print(f"  - reform_income calculated")

        print_memory_usage("Before reform tax calculation")
        reform_tax = cd_reformed.calculate("income_tax", period=2025)
        print(f"  - reform_tax calculated")

        print_memory_usage("After reform calculations")

    except MemoryError as e:
        print(f"ERROR: Memory error calculating reform: {e}")
        print_memory_usage("At error")
        # Save baseline results
        baseline_df.to_csv("baseline_results.csv", index=False)
        print("Baseline results saved to baseline_results.csv")
        return

    # Step 7: Add reform data to dataframe
    print("\n7. Combining results...")
    baseline_df['reform_income'] = reform_income
    baseline_df['reform_tax'] = reform_tax

    # Clear reform arrays
    del reform_income, reform_tax
    del cd_reformed
    force_garbage_collection()

    # Calculate impacts
    baseline_df['reform_impact'] = baseline_df['reform_income'] - baseline_df['baseline_income']
    baseline_df['tax_change'] = baseline_df['reform_tax'] - baseline_df['baseline_tax']
    baseline_df['district_number'] = baseline_df['congressional_district_geoid'] % 100

    print(f"Impact dataframe created with {len(baseline_df)} households")
    print_memory_usage("After creating impact dataframe")

    # Step 8: Aggregate by congressional district
    print("\n8. Aggregating by congressional district...")

    def weighted_avg(group):
        return pd.Series({
            'avg_income_impact': (group['reform_impact'] * group['household_weight']).sum() / group['household_weight'].sum(),
            'avg_tax_change': (group['tax_change'] * group['household_weight']).sum() / group['household_weight'].sum(),
            'total_households': group['household_weight'].sum()
        })

    cd_summary = baseline_df.groupby(['state_fips', 'congressional_district_geoid', 'district_number']).apply(
        weighted_avg
    ).reset_index()

    cd_summary = cd_summary.sort_values('avg_income_impact', ascending=False)

    print(f"Summary created for {len(cd_summary)} congressional districts")

    # Step 9: Display results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    print("\nTop 10 Congressional Districts by Average Household Income Impact:")
    print(cd_summary.head(10)[['state_fips', 'district_number', 'avg_income_impact', 'avg_tax_change', 'total_households']])

    print("\nBottom 10 Congressional Districts (least benefit or most harm):")
    print(cd_summary.tail(10)[['state_fips', 'district_number', 'avg_income_impact', 'avg_tax_change', 'total_households']])

    print(f"\nOverall Statistics:")
    print(f"Total Congressional Districts: {len(cd_summary)}")
    print(f"Districts with positive income impact: {len(cd_summary[cd_summary['avg_income_impact'] > 0])}")
    print(f"Districts with negative income impact: {len(cd_summary[cd_summary['avg_income_impact'] < 0])}")
    print(f"Average impact across all districts: ${cd_summary['avg_income_impact'].mean():.2f}")
    print(f"Median impact across all districts: ${cd_summary['avg_income_impact'].median():.2f}")

    # Save results
    cd_summary.to_csv("congressional_district_summary.csv", index=False)
    print("\nResults saved to congressional_district_summary.csv")

    print_memory_usage("Final memory state")

    return cd_summary

if __name__ == "__main__":
    # Check if we should increase memory limits
    print("Python memory configuration:")
    print(f"Max size: {sys.maxsize}")

    # Try to run with optimizations
    try:
        results = main()
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        print_memory_usage("At unexpected error")