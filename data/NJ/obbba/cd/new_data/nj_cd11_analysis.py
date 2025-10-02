"""
NJ 11th Congressional District Winners and Losers Analysis
Using hf://policyengine/test/NJ.h5 dataset
"""

import pandas as pd
import numpy as np
from policyengine_us import Microsimulation
from policyengine_core.reforms import Reform
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# Configuration
YEAR = 2026
TARGET_CD_GEOID = 3411
DATASET = "hf://policyengine/test/NJ.h5"

print("=" * 60)
print("USING DATASET: NJ.h5")
print("=" * 60)
print(f"\nLoading data for CD {TARGET_CD_GEOID}...")

# Initialize baseline simulation
print("Loading baseline simulation (this may take a few minutes)...")
baseline = Microsimulation(dataset=DATASET)
print("Baseline simulation loaded.")

# Get congressional district IDs for filtering
print("Extracting congressional district data...")
cd_geoids = baseline.calculate("congressional_district_geoid", YEAR).values
household_weights = baseline.calculate("household_weight", YEAR).values
household_ids = baseline.calculate("household_id", YEAR).values

# DIAGNOSTIC: Check what districts exist in the dataset
print("\n" + "="*60)
print("DIAGNOSTIC: Checking all congressional districts in dataset")
print("="*60)
unique_districts = np.unique(cd_geoids)
print(f"Unique congressional district GEOIDs: {unique_districts}")
print(f"Total unique districts: {len(unique_districts)}")

# Check NJ districts specifically
nj_mask_all = (cd_geoids >= 3400) & (cd_geoids < 3500)
nj_districts = np.unique(cd_geoids[nj_mask_all])
print(f"\nNJ districts found (3400-3499): {nj_districts}")

# Show population for each NJ district
print("\nNJ District breakdown:")
for district in sorted(nj_districts):
    mask = cd_geoids == district
    count = mask.sum()
    weighted_pop = household_weights[mask].sum()
    print(f"  GEOID {district}: {count} households, weighted pop: {weighted_pop:,.0f}")

# First, let's check what we have for all of NJ
print(f"\nTotal NJ households in dataset: {nj_mask_all.sum()}")
print(f"Total NJ weighted population: {household_weights[nj_mask_all].sum():,.0f}")

# Filter to NJ 11th congressional district
cd_mask = cd_geoids == TARGET_CD_GEOID
cd11_household_ids = household_ids[cd_mask]
cd11_weights = household_weights[cd_mask]

print(f"\nFound {len(cd11_household_ids)} households in NJ's 11th congressional district")
print(f"Weighted population in CD11: {cd11_weights.sum():,.0f}")
print(f"Weight statistics - Min: {cd11_weights.min():.2f}, Max: {cd11_weights.max():.2f}, Mean: {cd11_weights.mean():.2f}")

# Calculate baseline household incomes for CD11
print("\nCalculating baseline values for CD11 households...")
baseline_net_income = baseline.calculate("household_net_income", YEAR).values[cd_mask]
baseline_household_income = baseline.calculate("household_net_income", YEAR).values[cd_mask]

# Calculate weighted income deciles for CD11 households
print("Calculating income deciles...")

def calculate_weighted_deciles(values, weights):
    """Calculate weighted decile boundaries"""
    # Sort by value
    sorted_indices = np.argsort(values)
    sorted_values = values[sorted_indices]
    sorted_weights = weights[sorted_indices]

    # Calculate cumulative weights
    cum_weights = np.cumsum(sorted_weights)
    total_weight = cum_weights[-1]

    # Find decile boundaries
    decile_boundaries = []
    for i in range(1, 10):
        target_weight = total_weight * i / 10
        idx = np.searchsorted(cum_weights, target_weight)
        if idx < len(sorted_values):
            decile_boundaries.append(sorted_values[idx])
        else:
            decile_boundaries.append(sorted_values[-1])

    # Assign deciles
    deciles = np.zeros(len(values), dtype=int)
    for i, val in enumerate(values):
        for d, boundary in enumerate(decile_boundaries):
            if val <= boundary:
                deciles[i] = d + 1
                break
        if deciles[i] == 0:  # Above all boundaries
            deciles[i] = 10

    return deciles, decile_boundaries

# Calculate deciles based on baseline household income
household_deciles, decile_boundaries = calculate_weighted_deciles(
    baseline_household_income, cd11_weights
)

print("\nIncome decile boundaries (household_net_income):")
for i, boundary in enumerate(decile_boundaries):
    print(f"  Decile {i+1} upper bound: ${boundary:,.0f}")

# Define OBBBA reform
print("\nApplying OBBBA reform...")

reform = Reform.from_dict({
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
  "gov.irs.income.bracket.rates.2": {
    "2025-01-01.2100-12-31": 0.15
  },
  "gov.irs.income.bracket.rates.3": {
    "2025-01-01.2100-12-31": 0.25
  },
  "gov.irs.income.bracket.rates.4": {
    "2025-01-01.2100-12-31": 0.28
  },
  "gov.irs.income.bracket.rates.5": {
    "2025-01-01.2100-12-31": 0.33
  },
  "gov.irs.income.bracket.rates.7": {
    "2025-01-01.2100-12-31": 0.396
  },
  "gov.irs.deductions.qbi.max.rate": {
    "2026-01-01.2100-12-31": 0
  },
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
  "gov.irs.deductions.tip_income.cap": {
    "2025-01-01.2100-12-31": 0
  },
  "gov.irs.credits.cdcc.phase_out.max": {
    "2026-01-01.2100-12-31": 0.35
  },
  "gov.irs.credits.cdcc.phase_out.min": {
    "2026-01-01.2100-12-31": 0.2
  },
  "gov.irs.deductions.qbi.max.w2_wages.rate": {
    "2026-01-01.2100-12-31": 0
  },
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
  "gov.irs.credits.ctc.amount.base[0].amount": {
    "2025-01-01.2025-12-31": 2000,
    "2026-01-01.2100-12-31": 1000
  },
  "gov.irs.deductions.auto_loan_interest.cap": {
    "2025-01-01.2100-12-31": 0
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
  "gov.irs.income.bracket.thresholds.1.JOINT": {
    "2026-01-01.2026-12-31": 24300,
    "2027-01-01.2027-12-31": 24800,
    "2028-01-01.2028-12-31": 25300,
    "2029-01-01.2029-12-31": 25800,
    "2030-01-01.2030-12-31": 26300,
    "2031-01-01.2031-12-31": 26850,
    "2032-01-01.2032-12-31": 27350,
    "2033-01-01.2033-12-31": 27900,
    "2034-01-01.2034-12-31": 28450,
    "2035-01-01.2100-12-31": 29000
  },
  "gov.irs.income.bracket.thresholds.2.JOINT": {
    "2026-01-01.2026-12-31": 98600,
    "2027-01-01.2027-12-31": 100700,
    "2028-01-01.2028-12-31": 102800,
    "2029-01-01.2029-12-31": 104800,
    "2030-01-01.2030-12-31": 106900,
    "2031-01-01.2031-12-31": 109000,
    "2032-01-01.2032-12-31": 111100,
    "2033-01-01.2033-12-31": 113300,
    "2034-01-01.2034-12-31": 115600,
    "2035-01-01.2100-12-31": 117900
  },
  "gov.irs.income.bracket.thresholds.3.JOINT": {
    "2026-01-01.2026-12-31": 199000,
    "2027-01-01.2027-12-31": 203250,
    "2028-01-01.2028-12-31": 207350,
    "2029-01-01.2029-12-31": 211450,
    "2030-01-01.2030-12-31": 215600,
    "2031-01-01.2031-12-31": 219900,
    "2032-01-01.2032-12-31": 224250,
    "2033-01-01.2033-12-31": 228700,
    "2034-01-01.2034-12-31": 233200,
    "2035-01-01.2100-12-31": 237850
  },
  "gov.irs.income.bracket.thresholds.4.JOINT": {
    "2026-01-01.2026-12-31": 303250,
    "2027-01-01.2027-12-31": 309700,
    "2028-01-01.2028-12-31": 315950,
    "2029-01-01.2029-12-31": 322200,
    "2030-01-01.2030-12-31": 328550,
    "2031-01-01.2031-12-31": 335050,
    "2032-01-01.2032-12-31": 341700,
    "2033-01-01.2033-12-31": 348450,
    "2034-01-01.2034-12-31": 355400,
    "2035-01-01.2100-12-31": 362450
  },
  "gov.irs.income.bracket.thresholds.5.JOINT": {
    "2026-01-01.2026-12-31": 541550,
    "2027-01-01.2027-12-31": 553050,
    "2028-01-01.2028-12-31": 564200,
    "2029-01-01.2029-12-31": 575400,
    "2030-01-01.2030-12-31": 586750,
    "2031-01-01.2031-12-31": 598350,
    "2032-01-01.2032-12-31": 610200,
    "2033-01-01.2033-12-31": 622300,
    "2034-01-01.2034-12-31": 634650,
    "2035-01-01.2100-12-31": 647250
  },
  "gov.irs.income.bracket.thresholds.6.JOINT": {
    "2026-01-01.2026-12-31": 611750,
    "2027-01-01.2027-12-31": 624700,
    "2028-01-01.2028-12-31": 637350,
    "2029-01-01.2029-12-31": 649950,
    "2030-01-01.2030-12-31": 662800,
    "2031-01-01.2031-12-31": 675900,
    "2032-01-01.2032-12-31": 689250,
    "2033-01-01.2033-12-31": 702950,
    "2034-01-01.2034-12-31": 716900,
    "2035-01-01.2100-12-31": 731150
  },
  "gov.irs.credits.ctc.amount.adult_dependent": {
    "2026-01-01.2100-12-31": 0
  },
  "gov.irs.deductions.senior_deduction.amount": {
    "2025-01-01.2100-12-31": 0
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
  "gov.irs.income.bracket.thresholds.1.SINGLE": {
    "2026-01-01.2026-12-31": 12150,
    "2027-01-01.2027-12-31": 12400,
    "2028-01-01.2028-12-31": 12650,
    "2029-01-01.2029-12-31": 12900,
    "2030-01-01.2030-12-31": 13150,
    "2031-01-01.2031-12-31": 13425,
    "2032-01-01.2032-12-31": 13675,
    "2033-01-01.2033-12-31": 13950,
    "2034-01-01.2034-12-31": 14225,
    "2035-01-01.2100-12-31": 14500
  },
  "gov.irs.income.bracket.thresholds.2.SINGLE": {
    "2026-01-01.2026-12-31": 49300,
    "2027-01-01.2027-12-31": 50350,
    "2028-01-01.2028-12-31": 51400,
    "2029-01-01.2029-12-31": 52400,
    "2030-01-01.2030-12-31": 53450,
    "2031-01-01.2031-12-31": 54500,
    "2032-01-01.2032-12-31": 55550,
    "2033-01-01.2033-12-31": 56650,
    "2034-01-01.2034-12-31": 57800,
    "2035-01-01.2100-12-31": 58950
  },
  "gov.irs.income.bracket.thresholds.3.SINGLE": {
    "2026-01-01.2026-12-31": 119400,
    "2027-01-01.2027-12-31": 121950,
    "2028-01-01.2028-12-31": 124400,
    "2029-01-01.2029-12-31": 126900,
    "2030-01-01.2030-12-31": 129400,
    "2031-01-01.2031-12-31": 131950,
    "2032-01-01.2032-12-31": 134550,
    "2033-01-01.2033-12-31": 137200,
    "2034-01-01.2034-12-31": 139950,
    "2035-01-01.2100-12-31": 142750
  },
  "gov.irs.income.bracket.thresholds.4.SINGLE": {
    "2026-01-01.2026-12-31": 249100,
    "2027-01-01.2027-12-31": 254400,
    "2028-01-01.2028-12-31": 259550,
    "2029-01-01.2029-12-31": 264650,
    "2030-01-01.2030-12-31": 269900,
    "2031-01-01.2031-12-31": 275250,
    "2032-01-01.2032-12-31": 280700,
    "2033-01-01.2033-12-31": 286250,
    "2034-01-01.2034-12-31": 291900,
    "2035-01-01.2100-12-31": 297750
  },
  "gov.irs.income.bracket.thresholds.5.SINGLE": {
    "2026-01-01.2026-12-31": 541550,
    "2027-01-01.2027-12-31": 553050,
    "2028-01-01.2028-12-31": 564200,
    "2029-01-01.2029-12-31": 575400,
    "2030-01-01.2030-12-31": 586750,
    "2031-01-01.2031-12-31": 598350,
    "2032-01-01.2032-12-31": 610200,
    "2033-01-01.2033-12-31": 622300,
    "2034-01-01.2034-12-31": 634650,
    "2035-01-01.2100-12-31": 647250
  },
  "gov.irs.income.bracket.thresholds.6.SINGLE": {
    "2026-01-01.2026-12-31": 543800,
    "2027-01-01.2027-12-31": 555300,
    "2028-01-01.2028-12-31": 566500,
    "2029-01-01.2029-12-31": 577700,
    "2030-01-01.2030-12-31": 589150,
    "2031-01-01.2031-12-31": 600800,
    "2032-01-01.2032-12-31": 612700,
    "2033-01-01.2033-12-31": 624850,
    "2034-01-01.2034-12-31": 637250,
    "2035-01-01.2100-12-31": 649900
  },
  "gov.irs.deductions.itemized.casualty.active": {
    "2026-01-01.2100-12-31": True
  },
  "gov.irs.deductions.standard.amount.SEPARATE": {
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
  "gov.irs.income.amt.exemption.phase_out.rate": {
    "2026-01-01.2100-12-31": 0.25
  },
  "gov.irs.deductions.overtime_income.cap.JOINT": {
    "2025-01-01.2100-12-31": 0
  },
  "gov.irs.deductions.qbi.max.w2_wages.alt_rate": {
    "2026-01-01.2100-12-31": 0
  },
  "gov.irs.income.amt.exemption.amount.SEPARATE": {
    "2026-01-01.2026-12-31": 54900,
    "2027-01-01.2027-12-31": 56050,
    "2028-01-01.2028-12-31": 57200,
    "2029-01-01.2029-12-31": 58350,
    "2030-01-01.2030-12-31": 59500,
    "2031-01-01.2031-12-31": 60650,
    "2032-01-01.2032-12-31": 61850,
    "2033-01-01.2033-12-31": 63100,
    "2034-01-01.2034-12-31": 64350,
    "2035-01-01.2100-12-31": 65600
  },
  "gov.irs.income.bracket.thresholds.1.SEPARATE": {
    "2026-01-01.2026-12-31": 12150,
    "2027-01-01.2027-12-31": 12400,
    "2028-01-01.2028-12-31": 12650,
    "2029-01-01.2029-12-31": 12900,
    "2030-01-01.2030-12-31": 13150,
    "2031-01-01.2031-12-31": 13425,
    "2032-01-01.2032-12-31": 13675,
    "2033-01-01.2033-12-31": 13950,
    "2034-01-01.2034-12-31": 14225,
    "2035-01-01.2100-12-31": 14500
  },
  "gov.irs.income.bracket.thresholds.2.SEPARATE": {
    "2026-01-01.2026-12-31": 49300,
    "2027-01-01.2027-12-31": 50350,
    "2028-01-01.2028-12-31": 51400,
    "2029-01-01.2029-12-31": 52400,
    "2030-01-01.2030-12-31": 53450,
    "2031-01-01.2031-12-31": 54500,
    "2032-01-01.2032-12-31": 55550,
    "2033-01-01.2033-12-31": 56650,
    "2034-01-01.2034-12-31": 57800,
    "2035-01-01.2100-12-31": 58950
  },
  "gov.irs.income.bracket.thresholds.3.SEPARATE": {
    "2026-01-01.2026-12-31": 99500,
    "2027-01-01.2027-12-31": 101625,
    "2028-01-01.2028-12-31": 103675,
    "2029-01-01.2029-12-31": 105725,
    "2030-01-01.2030-12-31": 107800,
    "2031-01-01.2031-12-31": 109950,
    "2032-01-01.2032-12-31": 112125,
    "2033-01-01.2033-12-31": 114350,
    "2034-01-01.2034-12-31": 116600,
    "2035-01-01.2100-12-31": 118925
  },
  "gov.irs.income.bracket.thresholds.4.SEPARATE": {
    "2026-01-01.2026-12-31": 151625,
    "2027-01-01.2027-12-31": 154850,
    "2028-01-01.2028-12-31": 157975,
    "2029-01-01.2029-12-31": 161100,
    "2030-01-01.2030-12-31": 164275,
    "2031-01-01.2031-12-31": 167525,
    "2032-01-01.2032-12-31": 170850,
    "2033-01-01.2033-12-31": 174225,
    "2034-01-01.2034-12-31": 177700,
    "2035-01-01.2100-12-31": 181225
  },
  "gov.irs.income.bracket.thresholds.5.SEPARATE": {
    "2026-01-01.2026-12-31": 270775,
    "2027-01-01.2027-12-31": 276525,
    "2028-01-01.2028-12-31": 282100,
    "2029-01-01.2029-12-31": 287700,
    "2030-01-01.2030-12-31": 293375,
    "2031-01-01.2031-12-31": 299175,
    "2032-01-01.2032-12-31": 305100,
    "2033-01-01.2033-12-31": 311150,
    "2034-01-01.2034-12-31": 317325,
    "2035-01-01.2100-12-31": 323625
  },
  "gov.irs.income.bracket.thresholds.6.SEPARATE": {
    "2026-01-01.2026-12-31": 305875,
    "2027-01-01.2027-12-31": 312350,
    "2028-01-01.2028-12-31": 318675,
    "2029-01-01.2029-12-31": 324975,
    "2030-01-01.2030-12-31": 331400,
    "2031-01-01.2031-12-31": 337950,
    "2032-01-01.2032-12-31": 344625,
    "2033-01-01.2033-12-31": 351475,
    "2034-01-01.2034-12-31": 358450,
    "2035-01-01.2100-12-31": 365575
  },
  "gov.irs.credits.ctc.phase_out.threshold.JOINT": {
    "2026-01-01.2100-12-31": 110000
  },
  "gov.irs.credits.ctc.refundable.individual_max": {
    "2025-01-01.2025-12-31": 1800,
    "2026-01-01.2100-12-31": 1000
  },
  "gov.irs.deductions.overtime_income.cap.SINGLE": {
    "2025-01-01.2100-12-31": 0
  },
  "gov.irs.credits.ctc.phase_out.threshold.SINGLE": {
    "2026-01-01.2100-12-31": 75000
  },
  "gov.irs.deductions.itemized.charity.ceiling.all": {
    "2026-01-01.2100-12-31": 0.5
  },
  "gov.irs.deductions.overtime_income.cap.SEPARATE": {
    "2025-01-01.2100-12-31": 0
  },
  "gov.irs.credits.ctc.phase_out.threshold.SEPARATE": {
    "2026-01-01.2100-12-31": 55000
  },
  "gov.irs.credits.ctc.adult_ssn_requirement_applies": {
    "2025-01-01.2100-12-31": False
  },
  "gov.irs.credits.ctc.refundable.phase_in.threshold": {
    "2026-01-01.2100-12-31": 3000
  },
  "gov.irs.deductions.itemized.charity.floor.applies": {
    "2026-01-01.2100-12-31": False
  },
  "gov.irs.deductions.qbi.max.business_property.rate": {
    "2026-01-01.2100-12-31": 0
  },
  "gov.irs.income.amt.exemption.phase_out.start.JOINT": {
    "2026-01-01.2026-12-31": 209200,
    "2027-01-01.2027-12-31": 213600,
    "2028-01-01.2028-12-31": 217900,
    "2029-01-01.2029-12-31": 222200,
    "2030-01-01.2030-12-31": 226600,
    "2031-01-01.2031-12-31": 231100,
    "2032-01-01.2032-12-31": 235700,
    "2033-01-01.2033-12-31": 240300,
    "2034-01-01.2034-12-31": 245100,
    "2035-01-01.2100-12-31": 250000
  },
  "gov.irs.deductions.standard.amount.SURVIVING_SPOUSE": {
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
  "gov.irs.income.amt.exemption.phase_out.start.SINGLE": {
    "2026-01-01.2026-12-31": 156900,
    "2027-01-01.2027-12-31": 160200,
    "2028-01-01.2028-12-31": 163400,
    "2029-01-01.2029-12-31": 166700,
    "2030-01-01.2030-12-31": 170000,
    "2031-01-01.2031-12-31": 173300,
    "2032-01-01.2032-12-31": 176800,
    "2033-01-01.2033-12-31": 180300,
    "2034-01-01.2034-12-31": 183800,
    "2035-01-01.2100-12-31": 187500
  },
  "gov.irs.deductions.standard.amount.HEAD_OF_HOUSEHOLD": {
    "2025-01-01.2025-12-31": 22500,
    "2026-01-01.2026-12-31": 12150,
    "2027-01-01.2027-12-31": 12400,
    "2028-01-01.2028-12-31": 12650,
    "2029-01-01.2029-12-31": 12900,
    "2030-01-01.2030-12-31": 13200,
    "2031-01-01.2031-12-31": 13450,
    "2032-01-01.2032-12-31": 13700,
    "2033-01-01.2033-12-31": 14000,
    "2034-01-01.2034-12-31": 14250,
    "2035-01-01.2100-12-31": 14550
  },
  "gov.irs.income.amt.exemption.amount.SURVIVING_SPOUSE": {
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
  "gov.irs.income.bracket.thresholds.1.SURVIVING_SPOUSE": {
    "2026-01-01.2026-12-31": 24300,
    "2027-01-01.2027-12-31": 24800,
    "2028-01-01.2028-12-31": 25300,
    "2029-01-01.2029-12-31": 25800,
    "2030-01-01.2030-12-31": 26300,
    "2031-01-01.2031-12-31": 26850,
    "2032-01-01.2032-12-31": 27350,
    "2033-01-01.2033-12-31": 27900,
    "2034-01-01.2034-12-31": 28450,
    "2035-01-01.2100-12-31": 29000
  },
  "gov.irs.income.bracket.thresholds.2.SURVIVING_SPOUSE": {
    "2026-01-01.2026-12-31": 98600,
    "2027-01-01.2027-12-31": 100700,
    "2028-01-01.2028-12-31": 102800,
    "2029-01-01.2029-12-31": 104800,
    "2030-01-01.2030-12-31": 106900,
    "2031-01-01.2031-12-31": 109000,
    "2032-01-01.2032-12-31": 111100,
    "2033-01-01.2033-12-31": 113300,
    "2034-01-01.2034-12-31": 115600,
    "2035-01-01.2100-12-31": 117900
  },
  "gov.irs.income.bracket.thresholds.3.SURVIVING_SPOUSE": {
    "2026-01-01.2026-12-31": 199000,
    "2027-01-01.2027-12-31": 203250,
    "2028-01-01.2028-12-31": 207350,
    "2029-01-01.2029-12-31": 211450,
    "2030-01-01.2030-12-31": 215600,
    "2031-01-01.2031-12-31": 219900,
    "2032-01-01.2032-12-31": 224250,
    "2033-01-01.2033-12-31": 228700,
    "2034-01-01.2034-12-31": 233200,
    "2035-01-01.2100-12-31": 237850
  },
  "gov.irs.income.bracket.thresholds.4.SURVIVING_SPOUSE": {
    "2026-01-01.2026-12-31": 303250,
    "2027-01-01.2027-12-31": 309700,
    "2028-01-01.2028-12-31": 315950,
    "2029-01-01.2029-12-31": 322200,
    "2030-01-01.2030-12-31": 328550,
    "2031-01-01.2031-12-31": 335050,
    "2032-01-01.2032-12-31": 341700,
    "2033-01-01.2033-12-31": 348450,
    "2034-01-01.2034-12-31": 355400,
    "2035-01-01.2100-12-31": 362450
  },
  "gov.irs.income.bracket.thresholds.5.SURVIVING_SPOUSE": {
    "2026-01-01.2026-12-31": 541550,
    "2027-01-01.2027-12-31": 553050,
    "2028-01-01.2028-12-31": 564200,
    "2029-01-01.2029-12-31": 575400,
    "2030-01-01.2030-12-31": 586750,
    "2031-01-01.2031-12-31": 598350,
    "2032-01-01.2032-12-31": 610200,
    "2033-01-01.2033-12-31": 622300,
    "2034-01-01.2034-12-31": 634650,
    "2035-01-01.2100-12-31": 647250
  },
  "gov.irs.income.bracket.thresholds.6.SURVIVING_SPOUSE": {
    "2026-01-01.2026-12-31": 611750,
    "2027-01-01.2027-12-31": 624700,
    "2028-01-01.2028-12-31": 637350,
    "2029-01-01.2029-12-31": 649950,
    "2030-01-01.2030-12-31": 662800,
    "2031-01-01.2031-12-31": 675900,
    "2032-01-01.2032-12-31": 689250,
    "2033-01-01.2033-12-31": 702950,
    "2034-01-01.2034-12-31": 716900,
    "2035-01-01.2100-12-31": 731150
  },
  "gov.irs.income.amt.exemption.amount.HEAD_OF_HOUSEHOLD": {
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
  "gov.irs.income.amt.exemption.phase_out.start.SEPARATE": {
    "2026-01-01.2026-12-31": 104600,
    "2027-01-01.2027-12-31": 106800,
    "2028-01-01.2028-12-31": 108950,
    "2029-01-01.2029-12-31": 111100,
    "2030-01-01.2030-12-31": 113300,
    "2031-01-01.2031-12-31": 115550,
    "2032-01-01.2032-12-31": 117850,
    "2033-01-01.2033-12-31": 120150,
    "2034-01-01.2034-12-31": 122550,
    "2035-01-01.2100-12-31": 125000
  },
  "gov.irs.income.bracket.thresholds.1.HEAD_OF_HOUSEHOLD": {
    "2026-01-01.2026-12-31": 17350,
    "2027-01-01.2027-12-31": 17700,
    "2028-01-01.2028-12-31": 18050,
    "2029-01-01.2029-12-31": 18400,
    "2030-01-01.2030-12-31": 18800,
    "2031-01-01.2031-12-31": 19150,
    "2032-01-01.2032-12-31": 19550,
    "2033-01-01.2033-12-31": 19900,
    "2034-01-01.2034-12-31": 20300,
    "2035-01-01.2100-12-31": 20700
  },
  "gov.irs.income.bracket.thresholds.2.HEAD_OF_HOUSEHOLD": {
    "2026-01-01.2026-12-31": 66050,
    "2027-01-01.2027-12-31": 67450,
    "2028-01-01.2028-12-31": 68850,
    "2029-01-01.2029-12-31": 70200,
    "2030-01-01.2030-12-31": 71550,
    "2031-01-01.2031-12-31": 73000,
    "2032-01-01.2032-12-31": 74450,
    "2033-01-01.2033-12-31": 75900,
    "2034-01-01.2034-12-31": 77400,
    "2035-01-01.2100-12-31": 78950
  },
  "gov.irs.income.bracket.thresholds.3.HEAD_OF_HOUSEHOLD": {
    "2026-01-01.2026-12-31": 170550,
    "2027-01-01.2027-12-31": 174150,
    "2028-01-01.2028-12-31": 177700,
    "2029-01-01.2029-12-31": 181200,
    "2030-01-01.2030-12-31": 184800,
    "2031-01-01.2031-12-31": 188450,
    "2032-01-01.2032-12-31": 192150,
    "2033-01-01.2033-12-31": 195950,
    "2034-01-01.2034-12-31": 199850,
    "2035-01-01.2100-12-31": 203850
  },
  "gov.irs.income.bracket.thresholds.4.HEAD_OF_HOUSEHOLD": {
    "2026-01-01.2026-12-31": 276200,
    "2027-01-01.2027-12-31": 282050,
    "2028-01-01.2028-12-31": 287750,
    "2029-01-01.2029-12-31": 293450,
    "2030-01-01.2030-12-31": 299250,
    "2031-01-01.2031-12-31": 305150,
    "2032-01-01.2032-12-31": 311200,
    "2033-01-01.2033-12-31": 317350,
    "2034-01-01.2034-12-31": 323650,
    "2035-01-01.2100-12-31": 330100
  },
  "gov.irs.income.bracket.thresholds.5.HEAD_OF_HOUSEHOLD": {
    "2026-01-01.2026-12-31": 541550,
    "2027-01-01.2027-12-31": 553050,
    "2028-01-01.2028-12-31": 564200,
    "2029-01-01.2029-12-31": 575400,
    "2030-01-01.2030-12-31": 586750,
    "2031-01-01.2031-12-31": 598350,
    "2032-01-01.2032-12-31": 610200,
    "2033-01-01.2033-12-31": 622300,
    "2034-01-01.2034-12-31": 634650,
    "2035-01-01.2100-12-31": 647250
  },
  "gov.irs.income.bracket.thresholds.6.HEAD_OF_HOUSEHOLD": {
    "2026-01-01.2026-12-31": 577750,
    "2027-01-01.2027-12-31": 590000,
    "2028-01-01.2028-12-31": 601950,
    "2029-01-01.2029-12-31": 613850,
    "2030-01-01.2030-12-31": 625950,
    "2031-01-01.2031-12-31": 638350,
    "2032-01-01.2032-12-31": 651000,
    "2033-01-01.2033-12-31": 663900,
    "2034-01-01.2034-12-31": 677050,
    "2035-01-01.2100-12-31": 690500
  },
  "gov.irs.deductions.itemized.interest.mortgage.cap.JOINT": {
    "2026-01-01.2100-12-31": 1000000
  },
  "gov.irs.deductions.overtime_income.cap.SURVIVING_SPOUSE": {
    "2025-01-01.2100-12-31": 0
  },
  "gov.irs.deductions.qbi.deduction_floor.amount[1].amount": {
    "2025-01-01.2100-12-31": 0
  },
  "gov.irs.credits.cdcc.phase_out.amended_structure.applies": {
    "2026-01-01.2100-12-31": False
  },
  "gov.irs.credits.ctc.phase_out.threshold.SURVIVING_SPOUSE": {
    "2026-01-01.2100-12-31": 75000
  },
  "gov.irs.deductions.itemized.interest.mortgage.cap.SINGLE": {
    "2026-01-01.2100-12-31": 1000000
  },
  "gov.irs.deductions.overtime_income.cap.HEAD_OF_HOUSEHOLD": {
    "2025-01-01.2100-12-31": 0
  },
  "gov.irs.credits.ctc.phase_out.threshold.HEAD_OF_HOUSEHOLD": {
    "2026-01-01.2100-12-31": 75000
  },
  "gov.irs.deductions.itemized.interest.mortgage.cap.SEPARATE": {
    "2026-01-01.2100-12-31": 500000
  },
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
  "gov.irs.income.amt.exemption.phase_out.start.SURVIVING_SPOUSE": {
    "2026-01-01.2026-12-31": 209200,
    "2027-01-01.2027-12-31": 213600,
    "2028-01-01.2028-12-31": 217900,
    "2029-01-01.2029-12-31": 222200,
    "2030-01-01.2030-12-31": 226600,
    "2031-01-01.2031-12-31": 231100,
    "2032-01-01.2032-12-31": 235700,
    "2033-01-01.2033-12-31": 240300,
    "2034-01-01.2034-12-31": 245100,
    "2035-01-01.2100-12-31": 250000
  },
  "gov.irs.deductions.itemized.charity.non_itemizers_amount.JOINT": {
    "2026-01-01.2100-12-31": 0
  },
  "gov.irs.income.amt.exemption.phase_out.start.HEAD_OF_HOUSEHOLD": {
    "2026-01-01.2026-12-31": 156900,
    "2027-01-01.2027-12-31": 160200,
    "2028-01-01.2028-12-31": 163400,
    "2029-01-01.2029-12-31": 166700,
    "2030-01-01.2030-12-31": 170000,
    "2031-01-01.2031-12-31": 173300,
    "2032-01-01.2032-12-31": 176800,
    "2033-01-01.2033-12-31": 180300,
    "2034-01-01.2034-12-31": 183800,
    "2035-01-01.2100-12-31": 187500
  },
  "gov.irs.deductions.itemized.charity.non_itemizers_amount.SINGLE": {
    "2026-01-01.2100-12-31": 0
  },
  "gov.irs.deductions.itemized.reduction.amended_structure.applies": {
    "2026-01-01.2100-12-31": False
  },
  "gov.irs.deductions.itemized.charity.non_itemizers_amount.SEPARATE": {
    "2026-01-01.2100-12-31": 0
  },
  "gov.irs.deductions.itemized.interest.mortgage.cap.SURVIVING_SPOUSE": {
    "2026-01-01.2100-12-31": 1000000
  },
  "gov.irs.deductions.itemized.interest.mortgage.cap.HEAD_OF_HOUSEHOLD": {
    "2026-01-01.2100-12-31": 1000000
  },
  "gov.irs.deductions.itemized.salt_and_real_estate.phase_out.in_effect": {
    "2025-01-01.2029-12-31": False
  },
  "gov.irs.deductions.itemized.salt_and_real_estate.cap.SURVIVING_SPOUSE": {
    "2025-01-01.2025-12-31": 10000,
    "2026-01-01.2100-12-31": 1000000000000
  },
  "gov.irs.deductions.itemized.salt_and_real_estate.cap.HEAD_OF_HOUSEHOLD": {
    "2025-01-01.2025-12-31": 10000,
    "2026-01-01.2100-12-31": 1000000000000
  },
  "gov.irs.deductions.itemized.salt_and_real_estate.phase_out.floor.applies": {
    "2025-01-01.2029-12-31": False
  },
  "gov.irs.deductions.itemized.charity.non_itemizers_amount.SURVIVING_SPOUSE": {
    "2026-01-01.2100-12-31": 0
  },
  "gov.irs.deductions.itemized.charity.non_itemizers_amount.HEAD_OF_HOUSEHOLD": {
    "2026-01-01.2100-12-31": 0
  }
}, country_id="us")

# Apply reform
print("Loading reform simulation (this may take a few minutes)...")
reformed = Microsimulation(reform=reform, dataset=DATASET)
print("Reform simulation loaded.")

# Calculate reformed values for CD11 households
print("Calculating reformed values for CD11 households...")
reformed_net_income = reformed.calculate("household_net_income", YEAR).values[cd_mask]

# Calculate net income changes
print("\nCalculating income changes...")
income_changes = reformed_net_income - baseline_net_income
percent_changes = (income_changes / baseline_net_income) * 100

# Handle infinity and NaN values
percent_changes = np.where(baseline_net_income == 0, 0, percent_changes)
percent_changes = np.where(np.isinf(percent_changes), 0, percent_changes)
percent_changes = np.nan_to_num(percent_changes, 0)

# Categorize winners and losers
winners = income_changes > 0
losers = income_changes < 0
no_change = income_changes == 0

# Create results dataframe
results = pd.DataFrame({
    'household_id': cd11_household_ids,
    'decile': household_deciles,
    'household_income': baseline_household_income,
    'baseline_net_income': baseline_net_income,
    'reformed_net_income': reformed_net_income,
    'income_change': income_changes,
    'percent_change': percent_changes,
    'category': pd.cut(percent_changes,
                       bins=[-np.inf, -5, -1e-10, 1e-10, 5, np.inf],
                       labels=['Lose >5%', 'Lose <5%', 'No change', 'Gain <5%', 'Gain >5%']),
    'weight': cd11_weights
})

# Aggregate by decile
print("\nAggregating results by decile...")
decile_summary = []

for decile in range(1, 11):
    decile_mask = results['decile'] == decile
    decile_data = results[decile_mask]

    if len(decile_data) == 0:
        continue

    total_weight = decile_data['weight'].sum()
    if total_weight == 0:
        continue

    winners_weight = decile_data[decile_data['income_change'] > 0]['weight'].sum()
    losers_weight = decile_data[decile_data['income_change'] < 0]['weight'].sum()
    no_change_weight = decile_data[decile_data['income_change'] == 0]['weight'].sum()

    # Calculate percentages for each category
    gain_5plus = decile_data[decile_data['category'] == 'Gain >5%']['weight'].sum() / total_weight * 100
    gain_less5 = decile_data[decile_data['category'] == 'Gain <5%']['weight'].sum() / total_weight * 100
    no_change_pct = no_change_weight / total_weight * 100
    lose_less5 = decile_data[decile_data['category'] == 'Lose <5%']['weight'].sum() / total_weight * 100
    lose_5plus = decile_data[decile_data['category'] == 'Lose >5%']['weight'].sum() / total_weight * 100

    # Calculate weighted average income change
    avg_income_change = (decile_data['income_change'] * decile_data['weight']).sum() / total_weight
    avg_pct_change = (decile_data['percent_change'] * decile_data['weight']).sum() / total_weight

    decile_summary.append({
        'decile': decile,
        'pct_winners': winners_weight / total_weight * 100,
        'pct_losers': losers_weight / total_weight * 100,
        'pct_no_change': no_change_pct,
        'pct_gain_5plus': gain_5plus,
        'pct_gain_less5': gain_less5,
        'pct_lose_less5': lose_less5,
        'pct_lose_5plus': lose_5plus,
        'avg_income_change': avg_income_change,
        'avg_pct_change': avg_pct_change,
        'total_households': len(decile_data),
        'total_weight': total_weight
    })

summary_df = pd.DataFrame(decile_summary)

# Display results
print("\n=== Winners and Losers by Income Decile (NJ CD11 - NJ.h5) ===")
print(summary_df.to_string())

# Save to CSV with clear filename
output_file = '/Users/daphnehansell/Documents/GitHub/analysis-notebooks/data/NJ/obbba/cd/new_data/nj_cd11_winners_losers_by_decile.csv'
summary_df.to_csv(output_file, index=False)
print(f"\nResults saved to: {output_file}")

# Save detailed household results for verification
detailed_file = '/Users/daphnehansell/Documents/GitHub/analysis-notebooks/data/NJ/obbba/cd/new_data/nj_cd11_winners_losers_detailed.csv'
results.to_csv(detailed_file, index=False)
print(f"Detailed results saved to: {detailed_file}")

# Print summary statistics
print("\n=== Overall Summary (NJ.h5 DATASET) ===")
total_weight = results['weight'].sum()
print(f"Dataset: NJ.h5")
print(f"Total NJ CD11 households analyzed: {len(results)}")
print(f"Total weighted population: {total_weight:,.0f}")
overall_winners_pct = results[results['income_change'] > 0]['weight'].sum() / total_weight * 100
overall_losers_pct = results[results['income_change'] < 0]['weight'].sum() / total_weight * 100
overall_no_change_pct = results[results['income_change'] == 0]['weight'].sum() / total_weight * 100
print(f"Overall % winners: {overall_winners_pct:.1f}%")
print(f"Overall % losers: {overall_losers_pct:.1f}%")
print(f"Overall % no change: {overall_no_change_pct:.1f}%")

# Create visualization
print("\n=== Creating Visualization ===")

# PolicyEngine color scheme for the diverging chart
colors = {
    'gain_5plus': '#0066CC',   # Dark blue
    'gain_less5': '#6699FF',   # Light blue
    'no_change': '#E0E0E0',    # Light gray
    'lose_less5': '#999999',   # Medium gray
    'lose_5plus': '#4D4D4D'    # Dark gray
}

# Create figure
fig, ax = plt.subplots(1, 1, figsize=(12, 8))

# Prepare data - calculate percentages for each category
categories_data = {
    'gain_5plus': summary_df['pct_gain_5plus'].values,
    'gain_less5': summary_df['pct_gain_less5'].values,
    'no_change': summary_df['pct_no_change'].values,
    'lose_less5': summary_df['pct_lose_less5'].values,
    'lose_5plus': summary_df['pct_lose_5plus'].values
}

# Calculate overall percentages for "All" bar
overall_gain_5plus = results[results['percent_change'] > 5]['weight'].sum() / total_weight * 100
overall_gain_less5 = results[(results['percent_change'] > 0) & (results['percent_change'] <= 5)]['weight'].sum() / total_weight * 100
overall_no_change = results[results['percent_change'] == 0]['weight'].sum() / total_weight * 100
overall_lose_less5 = results[(results['percent_change'] < 0) & (results['percent_change'] >= -5)]['weight'].sum() / total_weight * 100
overall_lose_5plus = results[results['percent_change'] < -5]['weight'].sum() / total_weight * 100

# Add "All" row
all_data = [overall_gain_5plus, overall_gain_less5, overall_no_change, overall_lose_less5, overall_lose_5plus]

# Create y-positions for bars (reversed so 1 is at top)
# Only include deciles that exist in summary_df
existing_deciles = summary_df['decile'].values
y_labels = ['All'] + [str(d) for d in range(10, 0, -1) if d in existing_deciles]
y_pos = np.arange(len(y_labels))

# Plot horizontal bars - stacked
# Add "All" bar data
left_pos = 0
for i, (value, color_key) in enumerate(zip(all_data, ['gain_5plus', 'gain_less5', 'no_change', 'lose_less5', 'lose_5plus'])):
    ax.barh(y_pos[0], value, left=left_pos, height=0.8,
            color=colors[color_key], edgecolor='white', linewidth=0.5)
    if value > 5:
        ax.text(left_pos + value/2, y_pos[0], f'{value:.0f}%',
               ha='center', va='center', fontsize=10,
               color='white' if color_key.endswith('5plus') else 'black')
    left_pos += value

# Add decile bars - only for existing deciles
for label_idx, label in enumerate(y_labels[1:], 1):  # Skip "All"
    decile = int(label)
    if decile in existing_deciles:
        decile_idx = list(existing_deciles).index(decile)

        # Reset accumulator for each bar
        left_pos = 0

        # Plot each category
        for cat_name, cat_color in [('gain_5plus', colors['gain_5plus']),
                                     ('gain_less5', colors['gain_less5']),
                                     ('no_change', colors['no_change']),
                                     ('lose_less5', colors['lose_less5']),
                                     ('lose_5plus', colors['lose_5plus'])]:
            value = categories_data[cat_name][decile_idx]
            if value > 0:
                ax.barh(y_pos[label_idx], value, left=left_pos, height=0.8,
                       color=cat_color, edgecolor='white', linewidth=0.5)

                # Add percentage label if significant
                if value > 5:
                    ax.text(left_pos + value/2, y_pos[label_idx], f'{value:.0f}%',
                           ha='center', va='center', fontsize=10,
                           color='white' if cat_name.endswith('5plus') else 'black')
                left_pos += value

# Styling
ax.set_yticks(y_pos)
ax.set_yticklabels(y_labels)
ax.set_xlabel('Population share', fontsize=12)
ax.set_ylabel('Income decile', fontsize=12)
ax.set_xlim(0, 100)
ax.set_xticks([0, 20, 40, 60, 80, 100])
ax.set_xticklabels(['0%', '20%', '40%', '60%', '80%', '100%'])

# Add vertical line to separate "All" from deciles
ax.axhline(y=0.5, color='gray', linestyle='-', linewidth=0.5)

# Add gridlines
ax.grid(True, axis='x', alpha=0.2, linestyle='-', linewidth=0.5)
ax.set_axisbelow(True)

# Title
overall_winners = overall_gain_5plus + overall_gain_less5
overall_losers = overall_lose_less5 + overall_lose_5plus
ax.set_title(f'OBBBA reform would increase the net income for {overall_winners:.0f}% of the population\nin NJ\'s 11th Congressional District and decrease it for {overall_losers:.0f}% in 2026\n(NJ.h5 DATASET)',
            fontsize=14, fontweight='bold', pad=20)

# Legend
legend_elements = [
    Patch(facecolor=colors['gain_5plus'], label='Gain more than 5%'),
    Patch(facecolor=colors['gain_less5'], label='Gain less than 5%'),
    Patch(facecolor=colors['no_change'], label='No change'),
    Patch(facecolor=colors['lose_less5'], label='Loss less than 5%'),
    Patch(facecolor=colors['lose_5plus'], label='Loss more than 5%')
]
ax.legend(handles=legend_elements, loc='upper right', title='Change in income',
         bbox_to_anchor=(1.15, 1), frameon=False)

# Clean up spines
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#CCCCCC')
ax.spines['bottom'].set_color('#CCCCCC')

fig.patch.set_facecolor('white')
plt.tight_layout()

output_chart = '/Users/daphnehansell/Documents/GitHub/analysis-notebooks/data/NJ/obbba/cd/new_data/nj_cd11_winners_losers_chart.png'
plt.savefig(output_chart, dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
print(f"Chart saved to: {output_chart}")

print("\n=== Analysis Complete ===")
print("NJ.h5 dataset analysis complete.")
