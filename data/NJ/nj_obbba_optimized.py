#!/usr/bin/env python3
"""
NJ Winners/Losers Analysis with FULL OBBBA Reform
Optimized for better hardware (but not supercomputer)
Uses the complete reform from obbba.ipynb
"""

import pandas as pd
import numpy as np
import gc
import time
from policyengine_us import Microsimulation
from policyengine_core.reforms import Reform

def create_obbba_reform():
    """OBBBA reform exactly as in obbba.ipynb"""
    return Reform.from_dict({
        # Estate tax changes
        "gov.irs.credits.estate.base": {
            "2026-01-01.2026-12-31": 6790000,
            "2027-01-01.2027-12-31": 6960000,
            "2028-01-01.2028-12-31": 7100000,
            "2029-01-01.2029-12-31": 7240000,
            "2030-01-01.2030-12-31": 7390000,
            "2031-01-01.2031-12-31": 7530000,
            "2032-01-01.2032-12-31": 7680000,
            "2033-01-01.2033-12-31": 7830000,
            "2034-01-01.2034-12-31": 7990000,
            "2035-01-01.2100-12-31": 8150000
        },

        # Tax bracket rate changes
        "gov.irs.income.bracket.rates.2": {"2025-01-01.2100-12-31": 0.15},
        "gov.irs.income.bracket.rates.3": {"2025-01-01.2100-12-31": 0.25},
        "gov.irs.income.bracket.rates.4": {"2025-01-01.2100-12-31": 0.28},
        "gov.irs.income.bracket.rates.5": {"2025-01-01.2100-12-31": 0.33},
        "gov.irs.income.bracket.rates.7": {"2025-01-01.2100-12-31": 0.396},

        # QBI and other deductions
        "gov.irs.deductions.qbi.max.rate": {"2026-01-01.2100-12-31": 0},
        "gov.irs.deductions.qbi.max.w2_wages.rate": {"2026-01-01.2100-12-31": 0},
        "gov.irs.deductions.qbi.max.w2_wages.alt_rate": {"2026-01-01.2100-12-31": 0},
        "gov.irs.deductions.qbi.max.business_property.rate": {"2026-01-01.2100-12-31": 0},

        # Income exemption
        "gov.irs.income.exemption.amount": {
            "2026-01-01.2026-12-31": 5300,
            "2027-01-01.2027-12-31": 5400,
            "2028-01-01.2028-12-31": 5500,
            "2029-01-01.2029-12-31": 5650,
            "2030-01-01.2030-12-31": 5750,
            "2031-01-01.2031-12-31": 5850,
            "2032-01-01.2032-12-31": 5950,
            "2033-01-01.2033-12-31": 6100,
            "2034-01-01.2034-12-31": 6200,
            "2035-01-01.2100-12-31": 6350
        },

        # Standard deduction changes - MAJOR CHANGE
        "gov.irs.deductions.standard.amount.JOINT": {
            "2025-01-01.2025-12-31": 30000,
            "2026-01-01.2026-12-31": 16600,
            "2027-01-01.2027-12-31": 16900,
            "2028-01-01.2028-12-31": 17300,
            "2029-01-01.2029-12-31": 17600,
            "2030-01-01.2030-12-31": 18000,
            "2031-01-01.2031-12-31": 18300,
            "2032-01-01.2032-12-31": 18700,
            "2033-01-01.2033-12-31": 19000,
            "2034-01-01.2034-12-31": 19400,
            "2035-01-01.2100-12-31": 19800
        },
        "gov.irs.deductions.standard.amount.SINGLE": {
            "2025-01-01.2025-12-31": 15000,
            "2026-01-01.2026-12-31": 8300,
            "2027-01-01.2027-12-31": 8450,
            "2028-01-01.2028-12-31": 8650,
            "2029-01-01.2029-12-31": 8800,
            "2030-01-01.2030-12-31": 9000,
            "2031-01-01.2031-12-31": 9150,
            "2032-01-01.2032-12-31": 9350,
            "2033-01-01.2033-12-31": 9500,
            "2034-01-01.2034-12-31": 9700,
            "2035-01-01.2100-12-31": 9900
        },

        # SALT cap removal - CRITICAL FOR NJ
        "gov.irs.deductions.itemized.salt_and_real_estate.cap.JOINT": {
            "2025-01-01.2025-12-31": 10000,
            "2026-01-01.2100-12-31": 1000000000000
        },
        "gov.irs.deductions.itemized.salt_and_real_estate.cap.SINGLE": {
            "2025-01-01.2025-12-31": 10000,
            "2026-01-01.2100-12-31": 1000000000000
        },
        "gov.irs.deductions.itemized.salt_and_real_estate.cap.SEPARATE": {
            "2025-01-01.2025-12-31": 5000,
            "2026-01-01.2100-12-31": 1000000000000
        },
        "gov.irs.deductions.itemized.salt_and_real_estate.cap.SURVIVING_SPOUSE": {
            "2025-01-01.2025-12-31": 10000,
            "2026-01-01.2100-12-31": 1000000000000
        },
        "gov.irs.deductions.itemized.salt_and_real_estate.cap.HEAD_OF_HOUSEHOLD": {
            "2025-01-01.2025-12-31": 10000,
            "2026-01-01.2100-12-31": 1000000000000
        },

        # Child tax credit changes
        "gov.irs.credits.ctc.amount.base[0].amount": {
            "2025-01-01.2025-12-31": 2000,
            "2026-01-01.2100-12-31": 1000
        },
        "gov.irs.credits.ctc.refundable.individual_max": {
            "2025-01-01.2025-12-31": 1800,
            "2026-01-01.2100-12-31": 1000
        },

        # AMT exemption amounts
        "gov.irs.income.amt.exemption.amount.JOINT": {
            "2026-01-01.2026-12-31": 109800,
            "2027-01-01.2027-12-31": 112100,
            "2028-01-01.2028-12-31": 114400,
            "2029-01-01.2029-12-31": 116700,
            "2030-01-01.2030-12-31": 119000,
            "2031-01-01.2031-12-31": 121300,
            "2032-01-01.2032-12-31": 123700,
            "2033-01-01.2033-12-31": 126200,
            "2034-01-01.2034-12-31": 128700,
            "2035-01-01.2100-12-31": 131200
        },
        "gov.irs.income.amt.exemption.amount.SINGLE": {
            "2026-01-01.2026-12-31": 70600,
            "2027-01-01.2027-12-31": 72100,
            "2028-01-01.2028-12-31": 73500,
            "2029-01-01.2029-12-31": 75000,
            "2030-01-01.2030-12-31": 76400,
            "2031-01-01.2031-12-31": 78000,
            "2032-01-01.2032-12-31": 79500,
            "2033-01-01.2033-12-31": 81100,
            "2034-01-01.2034-12-31": 82700,
            "2035-01-01.2100-12-31": 84300
        },

        # Itemized deduction changes
        "gov.irs.deductions.itemized.casualty.active": {"2026-01-01.2100-12-31": True},
        "gov.irs.deductions.itemized.charity.ceiling.all": {"2026-01-01.2100-12-31": 0.5},
        "gov.irs.deductions.itemized.interest.mortgage.cap.JOINT": {"2026-01-01.2100-12-31": 1000000},
        "gov.irs.deductions.itemized.interest.mortgage.cap.SINGLE": {"2026-01-01.2100-12-31": 1000000},

    }, country_id="us")

def setup_simulation(dataset_path, reform=None):
    """Setup simulation with state corrections"""
    print("  Loading simulation...", end="", flush=True)
    start = time.time()

    if reform:
        sim = Microsimulation(reform=reform, dataset=dataset_path)
    else:
        sim = Microsimulation(dataset=dataset_path)

    # Fix state FIPS codes
    cd_geoids = sim.calculate("congressional_district_geoid").values
    correct_state_fips = cd_geoids // 100
    sim.set_input("state_fips", 2023, correct_state_fips)

    # Clear cached calculations
    if "state_name" in sim.tax_benefit_system.variables:
        sim.delete_arrays("state_name", 2023)
    if "state_code" in sim.tax_benefit_system.variables:
        sim.delete_arrays("state_code", 2023)

    print(f" done ({time.time()-start:.1f}s)")
    return sim

def calculate_nj_only(sim, period=2026):
    """Calculate household_net_income for NJ households only"""
    print("  Filtering for NJ...", end="", flush=True)
    start = time.time()

    # Get NJ filter
    state_code = sim.calculate("state_code", map_to="household", period=period)
    in_nj = state_code == "NJ"
    nj_count = np.sum(in_nj.values if hasattr(in_nj, 'values') else in_nj)
    print(f" found {nj_count} households ({time.time()-start:.1f}s)")

    # Calculate household_net_income
    print("  Calculating household_net_income...", end="", flush=True)
    start = time.time()
    household_net_income = sim.calculate("household_net_income", map_to="household", period=period)
    print(f" done ({time.time()-start:.1f}s)")

    # Get weights and districts
    print("  Getting weights and districts...", end="", flush=True)
    start = time.time()
    weights = sim.calculate("household_weight", map_to="household", period=period)
    districts = sim.calculate("congressional_district_geoid", map_to="household", period=period)
    print(f" done ({time.time()-start:.1f}s)")

    # Convert to numpy arrays and filter for NJ
    net_income_nj = household_net_income[in_nj].values if hasattr(household_net_income[in_nj], 'values') else household_net_income[in_nj]
    weights_nj = weights[in_nj].values if hasattr(weights[in_nj], 'values') else weights[in_nj]
    districts_nj = districts[in_nj].values if hasattr(districts[in_nj], 'values') else districts[in_nj]

    return net_income_nj, weights_nj, districts_nj

def main():
    print("=" * 70)
    print("NJ WINNERS/LOSERS WITH OBBBA REFORM")
    print("Optimized for better hardware")
    print("=" * 70)

    dataset_path = "hf://policyengine/test/sparse_cd_stacked_2023.h5"
    period = 2026

    print("\nThis script will:")
    print("1. Calculate baseline household_net_income for NJ")
    print("2. Apply OBBBA reform")
    print("3. Calculate reformed household_net_income for NJ")
    print("4. Analyze winners and losers by district")

    try:
        # BASELINE
        print("\n" + "=" * 70)
        print("BASELINE CALCULATION:")
        print("-" * 70)
        start_baseline = time.time()

        sim_baseline = setup_simulation(dataset_path)
        baseline_income, weights, districts = calculate_nj_only(sim_baseline, period)

        print(f"Baseline complete in {time.time()-start_baseline:.1f}s")

        # Clean up baseline
        del sim_baseline
        gc.collect()

        # REFORM
        print("\n" + "=" * 70)
        print("REFORM CALCULATION:")
        print("-" * 70)
        start_reform = time.time()

        reform = create_obbba_reform()
        sim_reform = setup_simulation(dataset_path, reform=reform)
        reform_income, _, _ = calculate_nj_only(sim_reform, period)

        print(f"Reform complete in {time.time()-start_reform:.1f}s")

        # Clean up reform
        del sim_reform
        gc.collect()

        # ANALYSIS
        print("\n" + "=" * 70)
        print("ANALYSIS:")
        print("-" * 70)

        # Calculate changes
        income_change = reform_income - baseline_income

        # Identify winners and losers
        winners = income_change > 10  # Gain more than $10
        losers = income_change < -10  # Lose more than $10
        no_change = np.abs(income_change) <= 10

        # Overall statistics
        total_households = np.sum(weights)
        num_winners = np.sum(weights[winners])
        num_losers = np.sum(weights[losers])
        num_no_change = np.sum(weights[no_change])

        pct_winners = 100 * num_winners / total_households
        pct_losers = 100 * num_losers / total_households
        pct_no_change = 100 * num_no_change / total_households

        print(f"\nSTATEWIDE RESULTS:")
        print(f"  Total NJ Households: {total_households:,.0f}")
        print(f"  Winners: {num_winners:,.0f} ({pct_winners:.1f}%)")
        print(f"  Losers: {num_losers:,.0f} ({pct_losers:.1f}%)")
        print(f"  No change: {num_no_change:,.0f} ({pct_no_change:.1f}%)")

        if np.any(winners):
            avg_gain = np.average(income_change[winners], weights=weights[winners])
            print(f"  Average gain for winners: ${avg_gain:,.2f}")

        if np.any(losers):
            avg_loss = np.average(income_change[losers], weights=weights[losers])
            print(f"  Average loss for losers: ${-avg_loss:,.2f}")

        overall_avg = np.average(income_change, weights=weights)
        print(f"  Overall average change: ${overall_avg:,.2f}")

        # By district
        print("\n" + "-" * 70)
        print("BY CONGRESSIONAL DISTRICT:")
        print("-" * 70)
        print(f"{'District':<10} {'Winners':<12} {'Losers':<12} {'No Change':<12} {'Avg Change':<15}")
        print("-" * 70)

        results = []
        for district in sorted(np.unique(districts)):
            mask = districts == district
            dist_weights = weights[mask]
            dist_changes = income_change[mask]

            dist_total = np.sum(dist_weights)
            dist_winners = np.sum(dist_weights[winners[mask]])
            dist_losers = np.sum(dist_weights[losers[mask]])
            dist_no_change = np.sum(dist_weights[no_change[mask]])

            pct_winners = 100 * dist_winners / dist_total
            pct_losers = 100 * dist_losers / dist_total
            pct_no_change = 100 * dist_no_change / dist_total
            avg_change = np.average(dist_changes, weights=dist_weights)

            print(f"{int(district):<10} {pct_winners:<11.1f}% {pct_losers:<11.1f}% "
                  f"{pct_no_change:<11.1f}% ${avg_change:<14,.2f}")

            results.append({
                'district': int(district),
                'pct_winners': pct_winners,
                'pct_losers': pct_losers,
                'pct_no_change': pct_no_change,
                'avg_change': avg_change,
                'total_households': dist_total
            })

        # Save results
        results_df = pd.DataFrame(results)
        results_df.to_csv('nj_obbba_results.csv', index=False)

        print("\n" + "=" * 70)
        print("Results saved to nj_obbba_results.csv")
        print(f"Total runtime: {time.time()-start_baseline:.1f}s")
        print("=" * 70)

    except Exception as e:
        print(f"\nERROR: {e}")
        print("\nThis script requires:")
        print("- At least 16GB RAM")
        print("- Fast SSD")
        print("- Modern multi-core processor")
        print("\nConsider:")
        print("1. Closing other applications")
        print("2. Running on a cloud instance")
        print("3. Using the income_tax proxy version instead")

if __name__ == "__main__":
    main()