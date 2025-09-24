#!/usr/bin/env python3
"""
NJ Winners/Losers based on income_tax changes
Building on the script that worked (nj_tax_by_dist.py)
"""

import pandas as pd
import numpy as np
import gc
from policyengine_us import Microsimulation
from policyengine_core.reforms import Reform

def cleanup_memory():
    """Force garbage collection to free up memory"""
    gc.collect()

def create_reform():
    """Create the tax reform (same as the working script)"""
    return Reform.from_dict({
        "gov.irs.deductions.itemized.salt_and_real_estate.cap.JOINT": {
            "2025-01-01.2025-12-31": 10000,
            "2026-01-01.2100-12-31": 1000000000000
        },
        "gov.irs.deductions.itemized.salt_and_real_estate.cap.SINGLE": {
            "2025-01-01.2025-12-31": 10000,
            "2026-01-01.2100-12-31": 1000000000000
        },
    }, country_id="us")

def setup_simulation(dataset_path="hf://policyengine/test/sparse_cd_stacked_2023.h5", reform=None):
    """Initialize and setup the simulation with state corrections (same as working script)"""
    print(f"Loading simulation...")

    if reform:
        sim = Microsimulation(reform=reform, dataset=dataset_path)
    else:
        sim = Microsimulation(dataset=dataset_path)

    YEAR = 2023

    # Correct state FIPS codes (this worked before)
    cd_geoids = sim.calculate("congressional_district_geoid").values
    correct_state_fips = cd_geoids // 100
    sim.set_input("state_fips", YEAR, correct_state_fips)

    # Clear cached calculations
    if "state_name" in sim.tax_benefit_system.variables:
        sim.delete_arrays("state_name", YEAR)
    if "state_code" in sim.tax_benefit_system.variables:
        sim.delete_arrays("state_code", YEAR)

    cleanup_memory()
    return sim

def calculate_nj_winners_losers(sim_baseline, sim_reform, period=2026):
    """Calculate winners/losers based on income_tax (which worked before)"""
    print(f"Calculating taxes for period: {period}")

    # Calculate variables that worked before
    state_code = sim_baseline.calculate("state_code", map_to="household", period=period)
    income_tax_baseline = sim_baseline.calculate("income_tax", map_to="household", period=period)
    income_tax_reform = sim_reform.calculate("income_tax", map_to="household", period=period)
    congressional_district_geoid = sim_baseline.calculate("congressional_district_geoid", map_to="household", period=period)
    household_weight = sim_baseline.calculate("household_weight", map_to="household", period=period)

    # Filter for NJ
    in_nj = state_code == "NJ"

    # Get NJ data - convert to numpy arrays
    tax_baseline_nj = income_tax_baseline[in_nj].values if hasattr(income_tax_baseline[in_nj], 'values') else income_tax_baseline[in_nj]
    tax_reform_nj = income_tax_reform[in_nj].values if hasattr(income_tax_reform[in_nj], 'values') else income_tax_reform[in_nj]
    districts_nj = congressional_district_geoid[in_nj].values if hasattr(congressional_district_geoid[in_nj], 'values') else congressional_district_geoid[in_nj]
    weights_nj = household_weight[in_nj].values if hasattr(household_weight[in_nj], 'values') else household_weight[in_nj]

    # Calculate tax changes (negative = tax cut = winner)
    tax_change = tax_reform_nj - tax_baseline_nj

    # Winners pay less tax (tax_change < 0)
    winners = tax_change < 0
    losers = tax_change > 0
    no_change = tax_change == 0

    # Overall statistics
    total_households = np.sum(weights_nj)
    num_winners = np.sum(weights_nj[winners])
    num_losers = np.sum(weights_nj[losers])
    num_no_change = np.sum(weights_nj[no_change])

    pct_winners = 100 * num_winners / total_households
    pct_losers = 100 * num_losers / total_households

    print(f"\nOverall NJ Results:")
    print(f"  Winners (tax cut): {num_winners:,.0f} ({pct_winners:.1f}%)")
    print(f"  Losers (tax increase): {num_losers:,.0f} ({pct_losers:.1f}%)")
    print(f"  No change: {num_no_change:,.0f} ({100*num_no_change/total_households:.1f}%)")

    # Calculate by district
    unique_districts = np.unique(districts_nj)
    district_results = {}

    print(f"\nBy Congressional District:")
    for district in unique_districts:
        in_district = districts_nj == district
        dist_weights = weights_nj[in_district]
        dist_changes = tax_change[in_district]

        dist_total = np.sum(dist_weights)
        dist_winners = np.sum(dist_weights[winners[in_district]])
        dist_losers = np.sum(dist_weights[losers[in_district]])

        pct_dist_winners = 100 * dist_winners / dist_total if dist_total > 0 else 0
        avg_tax_change = np.average(dist_changes, weights=dist_weights)

        print(f"  District {int(district)}: {pct_dist_winners:.1f}% winners, avg tax change: ${avg_tax_change:,.0f}")

        district_results[int(district)] = {
            'pct_winners': pct_dist_winners,
            'avg_tax_change': avg_tax_change,
            'total_households': dist_total
        }

    cleanup_memory()
    return district_results, pct_winners

def main():
    """Main execution function"""
    print("=" * 60)
    print("NJ Winners/Losers Analysis (Based on Income Tax)")
    print("=" * 60)

    # Baseline calculation
    print("\n1. Running baseline analysis...")
    sim_baseline = setup_simulation()

    # Reform calculation
    print("\n2. Creating tax reform...")
    reform = create_reform()
    print("Reform created successfully")

    print("\n3. Running reform analysis...")
    sim_reform = setup_simulation(reform=reform)

    # Calculate winners/losers
    print("\n4. Analyzing winners and losers...")
    district_results, overall_pct_winners = calculate_nj_winners_losers(sim_baseline, sim_reform)

    # Save results
    results_df = pd.DataFrame.from_dict(district_results, orient='index')
    results_df.index.name = 'district'
    results_df = results_df.reset_index()
    results_df = results_df.sort_values('district')
    results_df.to_csv('nj_tax_winners_losers.csv', index=False)

    print("\n" + "=" * 60)
    print(f"Analysis complete!")
    print(f"Overall: {overall_pct_winners:.1f}% of NJ households get a tax cut")
    print(f"Results saved to nj_tax_winners_losers.csv")
    print("=" * 60)

    # Clean up
    del sim_baseline
    del sim_reform
    cleanup_memory()

if __name__ == "__main__":
    main()