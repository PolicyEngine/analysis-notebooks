"""
NJ Congressional District Population Diagnostic
Shows the population distribution across all 12 NJ congressional districts
in the NJ.h5 test dataset
"""

import numpy as np
from policyengine_us import Microsimulation

YEAR = 2026
DATASET = "hf://policyengine/test/NJ.h5"

print("="*70)
print("NJ Congressional District Population Check")
print("Dataset: hf://policyengine/test/NJ.h5")
print("="*70)

print("\nLoading dataset...")
baseline = Microsimulation(dataset=DATASET)
print("Dataset loaded.\n")

# Get congressional district data
cd_geoids = baseline.calculate("congressional_district_geoid", YEAR).values
household_weights = baseline.calculate("household_weight", YEAR).values

# Also check person_count (like the notebook)
person_counts = baseline.calculate("person_count", YEAR, map_to="household").values

print(f"\nDEBUG: Checking calculation methods:")
print(f"  Sum of household_weight: {household_weights.sum():,.0f}")
print(f"  Sum of person_count: {person_counts.sum():,.0f}")

# Get all unique districts
unique_districts = np.unique(cd_geoids)
print(f"Total unique congressional districts in dataset: {len(unique_districts)}\n")

# Calculate total NJ population
nj_mask = (cd_geoids >= 3400) & (cd_geoids < 3500)
total_nj_pop = household_weights[nj_mask].sum()

print("="*90)
print("NJ Congressional District Breakdown:")
print("="*90)
print(f"{'District':<15} {'Households':<12} {'Person Count':<15} {'HH Weight':<15} {'% of NJ':<10}")
print("-"*90)

for district in sorted(unique_districts):
    if 3400 <= district < 3500:  # NJ districts only
        mask = cd_geoids == district
        count = mask.sum()
        person_ct = person_counts[mask].sum()
        weighted_pop = household_weights[mask].sum()
        pct = (weighted_pop / total_nj_pop) * 100
        print(f"CD {district-3400:02d} ({district}):   {count:>6} HH    {person_ct:>12,.0f}    {weighted_pop:>12,.0f}      {pct:>6.2f}%")

total_person_count = person_counts[nj_mask].sum()
print("-"*90)
print(f"{'TOTAL NJ:':<15} {nj_mask.sum():>6} HH    {total_person_count:>12,.0f}    {total_nj_pop:>12,.0f}     {100.00:>6.2f}%")
print("="*90)

print("\n⚠️  IMPORTANT NOTES:")
print("\n1. METRICS EXPLAINED:")
print("   - Person Count: Raw number of people in the dataset sample")
print("   - HH Weight: Survey weights used to extrapolate to full population")
print("   - For analysis, we use HH Weight (household_weight)")
print("\n2. TEST DATASET ISSUE:")
print("   This is a TEST dataset. In reality, each NJ congressional district")
print("   should have approximately 700,000-800,000 people.")
print("\n   District 1 (CD01) is massively oversampled in this test dataset,")
print("   while all other districts are severely undersampled.")
print("   This dataset is NOT suitable for production congressional district analysis.")
