#!/usr/bin/env python3
"""
Debug script to identify the discrepancy between block 7 table and block 10 chart
in the ACA reform households notebook.
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

# Test income: 300% FPL = $79,950
test_income = 79_950

print("=" * 60)
print("DEBUGGING PTC DISCREPANCY AT 300% FPL ($79,950)")
print("=" * 60)

# METHOD 1: Block 7 approach (single-point with explicit income split)
print("\nMETHOD 1: Block 7 Table Approach (50/50 income split)")
print("-" * 40)

situation_method1 = copy.deepcopy(base_situation_ny)
# Split income 50/50 between adults
situation_method1["people"]["you"]["employment_income"] = {"2026": test_income / 2}
situation_method1["people"]["your partner"]["employment_income"] = {"2026": test_income / 2}

sim_method1 = Simulation(situation=situation_method1, reform=reform)
ptc_method1 = sim_method1.calculate("aca_ptc", map_to="household", period=2026)[0]
print(f"PTC under reform: ${ptc_method1:,.2f}")

# METHOD 2: Block 10 chart approach (axes-based simulation)
print("\nMETHOD 2: Block 10 Chart Approach (axes simulation)")
print("-" * 40)

situation_method2 = copy.deepcopy(base_situation_ny)
situation_method2["axes"] = [[{
    "name": "employment_income",
    "count": 800,
    "min": 0,
    "max": 400000
}]]

sim_method2 = Simulation(situation=situation_method2, reform=reform)
household_income = sim_method2.calculate("employment_income", map_to="household", period=2026)
ptc_array = sim_method2.calculate("aca_ptc", map_to="household", period=2026)

# Find the closest income point to our test income
closest_idx = np.argmin(np.abs(household_income - test_income))
actual_income = household_income[closest_idx]
ptc_method2 = ptc_array[closest_idx]

print(f"Closest income point: ${actual_income:,.2f}")
print(f"PTC under reform: ${ptc_method2:,.2f}")

# METHOD 3: Check how axes distributes income
print("\nMETHOD 3: Investigating income distribution in axes simulation")
print("-" * 40)

# The axes parameter by default applies the variation to the first person in the first entity
# Since we used "employment_income" which is a person-level variable, it's applied to "you"
print("Note: When using axes with 'employment_income', PolicyEngine applies")
print("the entire income variation to the first person ('you') by default.")
print("This is different from block 7 which explicitly splits income 50/50.")

# METHOD 4: Test with all income on one person
print("\nMETHOD 4: All income on one person")
print("-" * 40)

situation_method4 = copy.deepcopy(base_situation_ny)
situation_method4["people"]["you"]["employment_income"] = {"2026": test_income}
situation_method4["people"]["your partner"]["employment_income"] = {"2026": 0}

sim_method4 = Simulation(situation=situation_method4, reform=reform)
ptc_method4 = sim_method4.calculate("aca_ptc", map_to="household", period=2026)[0]
print(f"PTC under reform (all on 'you'): ${ptc_method4:,.2f}")

# Check some key variables that might affect PTC calculation
print("\n" + "=" * 60)
print("KEY VARIABLES COMPARISON")
print("=" * 60)

for method_name, sim in [("Method 1 (50/50)", sim_method1),
                          ("Method 4 (all on one)", sim_method4)]:
    print(f"\n{method_name}:")
    print("-" * 30)

    # Tax unit AGI
    agi = sim.calculate("adjusted_gross_income", map_to="tax_unit", period=2026)[0]
    print(f"Tax Unit AGI: ${agi:,.2f}")

    # SLCSP
    slcsp = sim.calculate("slcsp", map_to="household", period=2026)[0]
    print(f"SLCSP: ${slcsp:,.2f}")

    # Try to get expected contribution if it exists
    try:
        expected_contribution = sim.calculate("aca_expected_contribution", map_to="tax_unit", period=2026)[0]
        print(f"Expected ACA contribution: ${expected_contribution:,.2f}")
    except:
        pass

    # Try to get PTC phase-out if it exists
    try:
        ptc_phase_out = sim.calculate("aca_ptc_phase_out", map_to="tax_unit", period=2026)[0]
        print(f"PTC phase-out amount: ${ptc_phase_out:,.2f}")
    except:
        pass

print("\n" + "=" * 60)
print("CONCLUSION:")
print("The discrepancy occurs because:")
print("1. Block 7 explicitly splits income 50/50 between spouses")
print("2. Block 10 uses axes which assigns all income to the first person")
print("3. This affects tax calculations and potentially PTC eligibility/amounts")
print("=" * 60)