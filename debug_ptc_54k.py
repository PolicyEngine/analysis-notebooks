#!/usr/bin/env python3
"""
Debug the REAL discrepancy: At ~$54k income, the chart shows ~20k PTC
but the table shows 0 PTC!
"""

from policyengine_us import Simulation
from policyengine_core.reforms import Reform
import numpy as np
import copy

# Define the reform (same as notebook)
reform = Reform.from_dict({
    "gov.aca.ptc_phase_out_rate[0].amount": {"2026-01-01.2100-12-31": 0},
    "gov.aca.ptc_phase_out_rate[1].amount": {"2025-01-01.2100-12-31": 0},
    "gov.aca.ptc_phase_out_rate[2].amount": {"2026-01-01.2100-12-31": 0},
    "gov.aca.ptc_phase_out_rate[3].amount": {"2026-01-01.2100-12-31": 0.02},
    "gov.aca.ptc_phase_out_rate[4].amount": {"2026-01-01.2100-12-31": 0.04},
    "gov.aca.ptc_phase_out_rate[5].amount": {"2026-01-01.2100-12-31": 0.06},
    "gov.aca.ptc_phase_out_rate[6].amount": {"2026-01-01.2100-12-31": 0.085},
    "gov.aca.ptc_income_eligibility[2].amount": {"2026-01-01.2100-12-31": True}
}, country_id="us")

# Base situation for New York family
base_situation_ny = {
    "people": {
        "you": {"age": {"2026": 30}},
        "your partner": {"age": {"2026": 30}},
        "your first dependent": {"age": {"2026": 3}}
    },
    "families": {
        "your family": {"members": ["you", "your partner", "your first dependent"]}
    },
    "spm_units": {
        "your household": {"members": ["you", "your partner", "your first dependent"]}
    },
    "tax_units": {
        "your tax unit": {"members": ["you", "your partner", "your first dependent"]}
    },
    "households": {
        "your household": {
            "members": ["you", "your partner", "your first dependent"],
            "state_name": {"2026": "NY"},
            "county_fips": {"2026": "36061"}
        }
    },
    "marital_units": {
        "your marital unit": {"members": ["you", "your partner"]},
        "your first dependent's marital unit": {
            "members": ["your first dependent"],
            "marital_unit_id": {"2026": 1}
        }
    }
}

# Test income: 200% FPL = $53,300
test_income = 53_300

print("=" * 80)
print(f"DEBUGGING PTC DISCREPANCY AT $53,300 (200% FPL)")
print("Table shows: PTC = $0")
print("Chart apparently shows: PTC = ~$20,000")
print("=" * 80)

# METHOD 1: Table approach (50/50 income split)
print("\nMETHOD 1: Table Approach (50/50 income split)")
print("-" * 60)

situation_5050 = copy.deepcopy(base_situation_ny)
situation_5050["people"]["you"]["employment_income"] = {"2026": test_income / 2}
situation_5050["people"]["your partner"]["employment_income"] = {"2026": test_income / 2}

sim_5050 = Simulation(situation=situation_5050, reform=reform)
ptc_5050 = sim_5050.calculate("aca_ptc", map_to="household", period=2026)[0]
medicaid_5050 = sim_5050.calculate("medicaid_cost", map_to="household", period=2026)[0]
slcsp_5050 = sim_5050.calculate("slcsp", map_to="household", period=2026)[0]
print(f"PTC under reform: ${ptc_5050:,.2f}")
print(f"Medicaid cost: ${medicaid_5050:,.2f}")
print(f"SLCSP: ${slcsp_5050:,.2f}")

# METHOD 2: All income on first person (like axes does)
print("\nMETHOD 2: All income on first person (axes default)")
print("-" * 60)

situation_all_on_you = copy.deepcopy(base_situation_ny)
situation_all_on_you["people"]["you"]["employment_income"] = {"2026": test_income}
situation_all_on_you["people"]["your partner"]["employment_income"] = {"2026": 0}

sim_all_on_you = Simulation(situation=situation_all_on_you, reform=reform)
ptc_all = sim_all_on_you.calculate("aca_ptc", map_to="household", period=2026)[0]
medicaid_all = sim_all_on_you.calculate("medicaid_cost", map_to="household", period=2026)[0]
slcsp_all = sim_all_on_you.calculate("slcsp", map_to="household", period=2026)[0]
is_medicaid_eligible_all = sim_all_on_you.calculate("is_medicaid_eligible", period=2026)

print(f"PTC under reform: ${ptc_all:,.2f}")
print(f"Medicaid cost: ${medicaid_all:,.2f}")
print(f"SLCSP: ${slcsp_all:,.2f}")
print(f"Medicaid eligible - You: {is_medicaid_eligible_all['you']}")
print(f"Medicaid eligible - Partner: {is_medicaid_eligible_all['your partner']}")
print(f"Medicaid eligible - Child: {is_medicaid_eligible_all['your first dependent']}")

# Check chart simulation at this exact income point
print("\nMETHOD 3: Chart simulation (axes with 800 points)")
print("-" * 60)

situation_axes = copy.deepcopy(base_situation_ny)
situation_axes["axes"] = [[{
    "name": "employment_income",
    "count": 800,
    "min": 0,
    "max": 400000
}]]

sim_axes = Simulation(situation=situation_axes, reform=reform)
household_income = sim_axes.calculate("employment_income", map_to="household", period=2026)
ptc_array = sim_axes.calculate("aca_ptc", map_to="household", period=2026)
medicaid_array = sim_axes.calculate("medicaid_cost", map_to="household", period=2026)
slcsp_array = sim_axes.calculate("slcsp", map_to="household", period=2026)

# Find values around $53,300
indices = np.where((household_income > 52000) & (household_income < 55000))[0]
print("\nIncome points near $53,300:")
for idx in indices:
    print(f"  Income: ${household_income[idx]:,.2f} -> PTC: ${ptc_array[idx]:,.2f}, "
          f"Medicaid: ${medicaid_array[idx]:,.2f}, SLCSP: ${slcsp_array[idx]:,.2f}")

# Look at the exact Medicaid eligibility thresholds
print("\n" + "=" * 80)
print("KEY INSIGHT:")
print("-" * 60)
print("The difference is that when one person has all the income, their")
print("individual income might exceed Medicaid eligibility thresholds differently")
print("than when income is split 50/50!")
print()
print("In New York, adult Medicaid eligibility cuts off at 138% FPL.")
print("For a family of 3, that's about $36,570 total household income.")
print("BUT individual eligibility might be calculated differently!")

# Check individual incomes and FPL percentages
print("\n" + "=" * 80)
print("MEDICAID ELIGIBILITY ANALYSIS")
print("-" * 60)

for method_name, sim in [("50/50 split", sim_5050), ("All on one", sim_all_on_you)]:
    print(f"\n{method_name}:")

    # Get FPL percentages
    fpl_individual = sim.calculate("fpl", period=2026)
    tax_unit_fpl = sim.calculate("tax_unit_fpl", map_to="tax_unit", period=2026)[0]

    print(f"  Tax unit FPL %: {tax_unit_fpl:.1%}")
    print(f"  Individual FPL - You: {fpl_individual['you']:.1%}")
    print(f"  Individual FPL - Partner: {fpl_individual['your partner']:.1%}")
    print(f"  Individual FPL - Child: {fpl_individual['your first dependent']:.1%}")

    # Check if they're on employer health insurance
    has_employer_coverage = sim.calculate("has_employer_coverage", period=2026)
    print(f"  Has employer coverage - You: {has_employer_coverage['you']}")
    print(f"  Has employer coverage - Partner: {has_employer_coverage['your partner']}")
    print(f"  Has employer coverage - Child: {has_employer_coverage['your first dependent']}")

print("\n" + "=" * 80)
print("CONCLUSION:")
print("The discrepancy occurs because Medicaid eligibility in New York")
print("makes the family eligible for Medicaid at 200% FPL, which makes them")
print("INELIGIBLE for PTC (you can't get both). That's why the table shows")
print("PTC = $0 and Medicaid = $12,930.")
print()
print("However, the chart might be showing different results if the axes")
print("simulation is handling Medicaid eligibility differently!")
print("=" * 80)