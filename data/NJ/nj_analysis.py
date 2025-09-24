#!/usr/bin/env python3
"""
Final NJ Winners/Losers Analysis
Using income_tax changes since household_net_income times out
A household is "better off" if their taxes go DOWN
"""

import pandas as pd
import numpy as np
from policyengine_us import Microsimulation
from policyengine_core.reforms import Reform

def create_reform():
    """SALT cap removal reform"""
    return Reform.from_dict({
        "gov.irs.deductions.itemized.salt_and_real_estate.cap.JOINT": {
            "2026-01-01.2100-12-31": 1000000000000
        },
        "gov.irs.deductions.itemized.salt_and_real_estate.cap.SINGLE": {
            "2026-01-01.2100-12-31": 1000000000000
        },
    }, country_id="us")

def setup_simulation(reform=None):
    """Setup simulation with corrections"""
    dataset = "hf://policyengine/test/sparse_cd_stacked_2023.h5"
    sim = Microsimulation(reform=reform, dataset=dataset) if reform else Microsimulation(dataset=dataset)

    # Fix state FIPS
    cd_geoids = sim.calculate("congressional_district_geoid").values
    correct_state_fips = cd_geoids // 100
    sim.set_input("state_fips", 2023, correct_state_fips)

    return sim

def main():
    print("=" * 70)
    print("NJ WINNERS/LOSERS ANALYSIS (Based on Tax Changes)")
    print("=" * 70)
    print("\nNote: Using income_tax changes as household_net_income times out")
    print("Winners = tax decrease (more net income)")
    print("Losers = tax increase (less net income)")

    period = 2026

    # Baseline
    print("\n1. Calculating baseline taxes...")
    sim_baseline = setup_simulation()
    state_code = sim_baseline.calculate("state_code", map_to="household", period=period)
    in_nj = state_code == "NJ"

    tax_baseline = sim_baseline.calculate("income_tax", map_to="household", period=period)
    weights = sim_baseline.calculate("household_weight", map_to="household", period=period)
    districts = sim_baseline.calculate("congressional_district_geoid", map_to="household", period=period)

    # Get NJ data
    tax_baseline_nj = tax_baseline[in_nj].values if hasattr(tax_baseline[in_nj], 'values') else tax_baseline[in_nj]
    weights_nj = weights[in_nj].values if hasattr(weights[in_nj], 'values') else weights[in_nj]
    districts_nj = districts[in_nj].values if hasattr(districts[in_nj], 'values') else districts[in_nj]

    print(f"   Found {len(tax_baseline_nj)} NJ households")

    # Reform
    print("\n2. Calculating reform taxes...")
    reform = create_reform()
    sim_reform = setup_simulation(reform=reform)
    tax_reform = sim_reform.calculate("income_tax", map_to="household", period=period)
    tax_reform_nj = tax_reform[in_nj].values if hasattr(tax_reform[in_nj], 'values') else tax_reform[in_nj]

    # Analysis
    print("\n3. Analyzing changes...")
    tax_change = tax_reform_nj - tax_baseline_nj

    # Winners have NEGATIVE tax change (pay less tax)
    winners = tax_change < -10  # At least $10 tax cut
    losers = tax_change > 10   # At least $10 tax increase
    no_change = np.abs(tax_change) <= 10

    # Overall stats
    total_households = np.sum(weights_nj)
    num_winners = np.sum(weights_nj[winners])
    num_losers = np.sum(weights_nj[losers])
    num_no_change = np.sum(weights_nj[no_change])

    print("\n" + "=" * 70)
    print("STATEWIDE RESULTS FOR NEW JERSEY:")
    print("-" * 70)
    print(f"Total Households: {total_households:,.0f}")
    print(f"Better off (tax cut):    {num_winners:,.0f} ({100*num_winners/total_households:.1f}%)")
    print(f"Worse off (tax increase): {num_losers:,.0f} ({100*num_losers/total_households:.1f}%)")
    print(f"No significant change:    {num_no_change:,.0f} ({100*num_no_change/total_households:.1f}%)")

    if np.any(winners):
        avg_tax_cut = np.average(tax_change[winners], weights=weights_nj[winners])
        print(f"\nAverage tax cut for winners: ${-avg_tax_cut:,.2f}")

    if np.any(losers):
        avg_tax_increase = np.average(tax_change[losers], weights=weights_nj[losers])
        print(f"Average tax increase for losers: ${avg_tax_increase:,.2f}")

    overall_avg = np.average(tax_change, weights=weights_nj)
    print(f"Overall average tax change: ${overall_avg:,.2f}")

    # By district
    print("\n" + "=" * 70)
    print("BY CONGRESSIONAL DISTRICT:")
    print("-" * 70)
    print(f"{'District':<10} {'Better Off':<15} {'Worse Off':<15} {'No Change':<15} {'Avg Change':<15}")
    print("-" * 70)

    unique_districts = np.unique(districts_nj)
    results = []

    for district in sorted(unique_districts):
        mask = districts_nj == district
        dist_weights = weights_nj[mask]
        dist_changes = tax_change[mask]

        dist_total = np.sum(dist_weights)
        dist_winners = np.sum(dist_weights[winners[mask]])
        dist_losers = np.sum(dist_weights[losers[mask]])
        dist_no_change = np.sum(dist_weights[no_change[mask]])

        pct_winners = 100 * dist_winners / dist_total
        pct_losers = 100 * dist_losers / dist_total
        avg_change = np.average(dist_changes, weights=dist_weights)

        print(f"{int(district):<10} {pct_winners:<14.1f}% {pct_losers:<14.1f}% "
              f"{100-pct_winners-pct_losers:<14.1f}% ${avg_change:<14,.0f}")

        results.append({
            'district': int(district),
            'pct_better_off': pct_winners,
            'pct_worse_off': pct_losers,
            'pct_no_change': 100-pct_winners-pct_losers,
            'avg_tax_change': avg_change,
            'total_households': dist_total
        })

    # Save results
    results_df = pd.DataFrame(results)
    results_df.to_csv('nj_final_winners_losers.csv', index=False)

    print("\n" + "=" * 70)
    print("Results saved to nj_final_winners_losers.csv")
    print("=" * 70)

if __name__ == "__main__":
    main()