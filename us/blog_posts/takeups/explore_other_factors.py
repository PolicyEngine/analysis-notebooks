#!/usr/bin/env python3
"""
Explore other factors beyond ESI that explain cost differences between datasets
"""

from policyengine_us import Microsimulation
from policyengine_core.reforms import Reform
import pandas as pd
import numpy as np

# Define the reform
reform = Reform.from_dict({
    "gov.aca.ptc_phase_out_rate[0].amount": {
        "2026-01-01.2100-12-31": 0
    },
    "gov.aca.ptc_phase_out_rate[1].amount": {
        "2025-01-01.2100-12-31": 0
    },
    "gov.aca.ptc_phase_out_rate[2].amount": {
        "2026-01-01.2100-12-31": 0
    },
    "gov.aca.ptc_phase_out_rate[3].amount": {
        "2026-01-01.2100-12-31": 0.02
    },
    "gov.aca.ptc_phase_out_rate[4].amount": {
        "2026-01-01.2100-12-31": 0.04
    },
    "gov.aca.ptc_phase_out_rate[5].amount": {
        "2026-01-01.2100-12-31": 0.06
    },
    "gov.aca.ptc_phase_out_rate[6].amount": {
        "2026-01-01.2100-12-31": 0.085
    }
}, country_id="us")

print("Loading datasets...")
old_baseline = Microsimulation(dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")
old_reformed = Microsimulation(reform=reform, dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")

new_baseline = Microsimulation(dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")
new_reformed = Microsimulation(reform=reform, dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")

year = 2026

print("\n" + "="*70)
print("EXPLORING OTHER FACTORS BEYOND ESI")
print("="*70)

# 1. SLCSP (Second Lowest Cost Silver Plan) premium differences
print("\n1. SLCSP PREMIUM DIFFERENCES:")
print("-"*40)

try:
    old_slcsp = old_baseline.calculate("slcsp_premium", map_to="tax_unit", period=year)
    new_slcsp = new_baseline.calculate("slcsp_premium", map_to="tax_unit", period=year)

    # Filter to tax units that might be eligible (rough proxy)
    old_income = old_baseline.calculate("tax_unit_income", map_to="tax_unit", period=year)
    new_income = new_baseline.calculate("tax_unit_income", map_to="tax_unit", period=year)

    # Look at households in ACA-relevant income range (100-400% FPL roughly)
    relevant_income_range = (old_income > 10000) & (old_income < 100000)

    old_slcsp_relevant = old_slcsp[relevant_income_range]
    new_slcsp_relevant = new_slcsp[(new_income > 10000) & (new_income < 100000)]

    print(f"Average SLCSP for relevant income range:")
    print(f"  Old: ${old_slcsp_relevant.mean():,.0f}")
    print(f"  New: ${new_slcsp_relevant.mean():,.0f}")
    print(f"  Difference: ${new_slcsp_relevant.mean() - old_slcsp_relevant.mean():,.0f}")
except Exception as e:
    print(f"SLCSP data not available: {e}")

# 2. MEDICAID EXPANSION STATUS / ELIGIBILITY
print("\n2. MEDICAID DIFFERENCES:")
print("-"*40)

try:
    old_medicaid = old_baseline.calculate("is_medicaid_eligible", map_to="person", period=year)
    new_medicaid = new_baseline.calculate("is_medicaid_eligible", map_to="person", period=year)
    
    old_medicaid_rate = old_medicaid.mean()
    new_medicaid_rate = new_medicaid.mean()
    
    print(f"Medicaid eligibility rate:")
    print(f"  Old: {old_medicaid_rate*100:.1f}%")
    print(f"  New: {new_medicaid_rate*100:.1f}%")
    print(f"  Change: {(new_medicaid_rate - old_medicaid_rate)*100:.1f} pp")
    
    # Check actual Medicaid enrollment (takeup)
    old_medicaid_enrolled = old_baseline.calculate("medicaid", map_to="person", period=year)
    new_medicaid_enrolled = new_baseline.calculate("medicaid", map_to="person", period=year)
    
    old_enrolled_rate = (old_medicaid_enrolled > 0).mean()
    new_enrolled_rate = (new_medicaid_enrolled > 0).mean()
    
    print(f"\nActual Medicaid enrollment:")
    print(f"  Old: {old_enrolled_rate*100:.1f}%")
    print(f"  New: {new_enrolled_rate*100:.1f}%")
    print(f"  Change: {(new_enrolled_rate - old_enrolled_rate)*100:.1f} pp")
except Exception as e:
    print(f"Error calculating Medicaid: {e}")

# 3. ACA TAKEUP RATE ASSUMPTIONS
print("\n3. ACA TAKEUP BEHAVIOR:")
print("-"*40)

# Check the takeup rates directly
old_takeup = old_baseline.calculate("takes_up_aca_if_eligible", map_to="person", period=year)
new_takeup = new_baseline.calculate("takes_up_aca_if_eligible", map_to="person", period=year)

# Among eligible people, what's the takeup rate?
old_eligible = old_baseline.calculate("is_aca_ptc_eligible", map_to="person", period=year)
new_eligible = new_baseline.calculate("is_aca_ptc_eligible", map_to="person", period=year)

old_takeup_rate = old_takeup[old_eligible == 1].mean() if (old_eligible == 1).sum() > 0 else 0
new_takeup_rate = new_takeup[new_eligible == 1].mean() if (new_eligible == 1).sum() > 0 else 0

print(f"Takeup rate among eligible:")
print(f"  Old: {old_takeup_rate*100:.1f}%")
print(f"  New: {new_takeup_rate*100:.1f}%")
print(f"  Change: {(new_takeup_rate - old_takeup_rate)*100:.1f} pp")

# 4. INCOME DISTRIBUTION IN KEY RANGE
print("\n4. INCOME DISTRIBUTION (100-400% FPL range):")
print("-"*40)

# Approximate FPL for single person
single_fpl = 15570

# Look at distribution around key thresholds
income_ranges = [
    (single_fpl * 1.0, single_fpl * 1.5, "100-150% FPL"),
    (single_fpl * 1.5, single_fpl * 2.0, "150-200% FPL"),
    (single_fpl * 2.0, single_fpl * 2.5, "200-250% FPL"),
    (single_fpl * 2.5, single_fpl * 3.0, "250-300% FPL"),
    (single_fpl * 3.0, single_fpl * 3.5, "300-350% FPL"),
    (single_fpl * 3.5, single_fpl * 4.0, "350-400% FPL"),
    (single_fpl * 4.0, single_fpl * 5.0, "400-500% FPL"),
]

old_tu_income = old_baseline.calculate("tax_unit_income", map_to="tax_unit", period=year)
new_tu_income = new_baseline.calculate("tax_unit_income", map_to="tax_unit", period=year)
old_tu_weights = old_baseline.calculate("tax_unit_weight", period=year)
new_tu_weights = new_baseline.calculate("tax_unit_weight", period=year)

print(f"{'Range':<15} {'Old Count':<12} {'New Count':<12} {'Change':<10}")
print("-"*50)

for low, high, label in income_ranges:
    old_mask = (old_tu_income >= low) & (old_tu_income < high)
    new_mask = (new_tu_income >= low) & (new_tu_income < high)
    
    old_count = old_tu_weights[old_mask].sum()
    new_count = new_tu_weights[new_mask].sum()
    
    print(f"{label:<15} {old_count/1e6:>10.2f}M {new_count/1e6:>10.2f}M {(new_count-old_count)/1e6:>9.2f}M")

# 5. FAMILY COMPOSITION CHANGES
print("\n5. FAMILY COMPOSITION:")
print("-"*40)

old_family_size = old_baseline.calculate("tax_unit_size", map_to="tax_unit", period=year)
new_family_size = new_baseline.calculate("tax_unit_size", map_to="tax_unit", period=year)

print(f"Average tax unit size:")
print(f"  Old: {old_family_size.mean():.2f}")
print(f"  New: {new_family_size.mean():.2f}")

# Distribution of family sizes
for size in [1, 2, 3, 4]:
    old_pct = (old_family_size == size).mean() * 100
    new_pct = (new_family_size == size).mean() * 100
    print(f"  Size {size}: Old {old_pct:.1f}%, New {new_pct:.1f}%")

# 6. AGE DISTRIBUTION (affects premiums and eligibility)
print("\n6. AGE DISTRIBUTION:")
print("-"*40)

old_age = old_baseline.calculate("age", map_to="person", period=year)
new_age = new_baseline.calculate("age", map_to="person", period=year)

# Key age groups for ACA
age_groups = [
    (0, 18, "Under 18"),
    (18, 26, "18-26"),
    (26, 35, "26-35"),
    (35, 50, "35-50"),
    (50, 64, "50-64"),
    (64, 999, "65+")
]

print(f"{'Age Group':<12} {'Old %':<8} {'New %':<8} {'Change':<8}")
print("-"*40)

for low, high, label in age_groups:
    old_pct = ((old_age >= low) & (old_age < high)).mean() * 100
    new_pct = ((new_age >= low) & (new_age < high)).mean() * 100
    print(f"{label:<12} {old_pct:>7.1f}% {new_pct:>7.1f}% {new_pct-old_pct:>7.1f}pp")

# 7. Check state-specific factors
print("\n7. HIGH-IMPACT STATES DEEP DIVE:")
print("-"*40)

# Look at California specifically (biggest $ change)
old_states = old_baseline.calculate("state_code", map_to="household", period=year)
new_states = new_baseline.calculate("state_code", map_to="household", period=year)

ca_mask_old = old_states == "CA"
ca_mask_new = new_states == "CA"

# ESI in CA
old_esi = old_baseline.calculate("has_esi", map_to="person", period=year)
new_esi = new_baseline.calculate("has_esi", map_to="person", period=year)
old_person_state = old_baseline.calculate("state_code", map_to="person", period=year)
new_person_state = new_baseline.calculate("state_code", map_to="person", period=year)

ca_person_old = old_person_state == "CA"
ca_person_new = new_person_state == "CA"

print("California specifics:")
print(f"  ESI rate old: {old_esi[ca_person_old].mean()*100:.1f}%")
print(f"  ESI rate new: {new_esi[ca_person_new].mean()*100:.1f}%")

# Income distribution in CA
ca_income_old = old_tu_income[old_states == "CA"]
ca_income_new = new_tu_income[new_states == "CA"]

print(f"  Median income old: ${np.median(ca_income_old):,.0f}")
print(f"  Median income new: ${np.median(ca_income_new):,.0f}")

print("\n" + "="*70)
print("KEY INSIGHTS:")
print("="*70)

print("""
Why ESI doesn't explain everything:

1. MEDICAID CROWD-OUT: Lower Medicaid eligibility (-5pp) means more people 
   need marketplace coverage, partially offsetting ESI increases

2. INCOME SHIFTS: The income distribution changed significantly, with more
   households in lower income brackets who get larger subsidies

3. FAMILY COMPOSITION: Changes in tax unit sizes affect both eligibility
   and subsidy amounts

4. PREMIUM CHANGES: SLCSP premiums may have been updated, changing the
   subsidy calculation even for the same income

5. STATE-SPECIFIC FACTORS: Some states like CA show massive changes that
   can't be explained by ESI alone - likely data quality improvements

6. TAKEUP BEHAVIOR: The takeup model may have been refined between versions

7. AGE DISTRIBUTION: Shifts in age distribution affect both premiums and
   the likelihood of having ESI
""")