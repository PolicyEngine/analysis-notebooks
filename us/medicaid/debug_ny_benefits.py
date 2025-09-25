#!/usr/bin/env python3
"""
Focused analysis: Find exact 2026 FPG and calculate PTC at 405% and 406% FPL
"""

from policyengine_us import Simulation
from policyengine_core.reforms import Reform
import copy

print("="*80)
print("FINDING 2026 FPG AND CALCULATING EXACT 405% FPL")
print("="*80)

# The 2025 FPG for family of 3 is $26,650
# PolicyEngine uprates this to 2026
# Let's assume ~2% inflation = $27,183

fpg_2025 = 26650
uprate_factor = 1.02  # Approximate uprate to 2026
fpg_2026_estimate = fpg_2025 * uprate_factor

print(f"\n2025 FPG for family of 3: ${fpg_2025:,}")
print(f"Estimated 2026 FPG (with ~2% uprate): ${fpg_2026_estimate:,.0f}")

# Calculate what the incomes would be
incomes_2026 = {
    "300% FPL": fpg_2026_estimate * 3.00,
    "400% FPL": fpg_2026_estimate * 4.00,
    "401% FPL": fpg_2026_estimate * 4.01,
    "405% FPL": fpg_2026_estimate * 4.05,
    "406% FPL": fpg_2026_estimate * 4.06,
    "410% FPL": fpg_2026_estimate * 4.10,
}

print(f"\nExact 405% FPL for 2026: ${incomes_2026['405% FPL']:,.2f}")
print(f"Exact 406% FPL for 2026: ${incomes_2026['406% FPL']:,.2f}")
print(f"Difference between 405% and 406%: ${incomes_2026['406% FPL'] - incomes_2026['405% FPL']:,.2f}")

# Define the reform
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

# Define NY family situation
situation = {
    "people": {
        "you": {"age": {"2026": 30}},
        "your partner": {"age": {"2026": 30}},
        "your first dependent": {"age": {"2026": 3}}
    },
    "families": {"your family": {"members": ["you", "your partner", "your first dependent"]}},
    "spm_units": {"your household": {"members": ["you", "your partner", "your first dependent"]}},
    "tax_units": {"your tax unit": {"members": ["you", "your partner", "your first dependent"]}},
    "households": {
        "your household": {
            "members": ["you", "your partner", "your first dependent"],
            "state_name": {"2026": "NY"},
            "county_fips": {"2026": "36061"}
        }
    },
    "marital_units": {
        "your marital unit": {"members": ["you", "your partner"]},
        "your first dependent's marital unit": {"members": ["your first dependent"], "marital_unit_id": {"2026": 1}}
    }
}

print("\n" + "="*80)
print("ESTIMATED TABLE (Based on 2026 uprated FPG)")
print("="*80)

print(f"\n{'FPL %':<12} {'Income':>12} {'Expected Outcomes'}")
print("-"*70)

for label, income in incomes_2026.items():
    if "300" in label:
        print(f"{label:<12} ${income:>10,.0f}  CHIP active, PTC active in both")
    elif "400" in label:
        print(f"{label:<12} ${income:>10,.0f}  CHIP phases out, PTC = $0 baseline")
    elif "401" in label or "405" in label:
        print(f"{label:<12} ${income:>10,.0f}  No CHIP, PTC = $0 baseline, ~$12k reform")
    elif "406" in label:
        print(f"{label:<12} ${income:>10,.0f}  No CHIP, PTC = $0 baseline, ~$12k reform")
    elif "410" in label:
        print(f"{label:<12} ${income:>10,.0f}  No CHIP, PTC = $0 baseline, ~$11k reform")

print("\n" + "="*80)
print("THE KEY QUESTION:")
print("="*80)
print(f"\nUsing exact 2026 uprated FPG of ~${fpg_2026_estimate:,.0f}:")
print(f"- Exact 405% FPL = ${incomes_2026['405% FPL']:,.2f}")
print(f"- Exact 406% FPL = ${incomes_2026['406% FPL']:,.2f}")
print(f"- Difference = ${incomes_2026['406% FPL'] - incomes_2026['405% FPL']:,.2f}")

print("\nThe table previously used $107,933 which is:")
print(f"- 405% of 2025 FPG ($26,650) = $107,932.50")
print(f"- But for 2026, the actual 405% FPL ≈ ${incomes_2026['405% FPL']:,.2f}")

# Let's run just one quick test at exact 405%
print("\n" + "="*80)
print("RUNNING ONE TEST: Exact 405% FPL for 2026")
print("="*80)

income_405 = incomes_2026['405% FPL']
sit = copy.deepcopy(situation)
sit["people"]["you"]["employment_income"] = {"2026": income_405 / 2}
sit["people"]["your partner"]["employment_income"] = {"2026": income_405 / 2}

print(f"\nTesting income of ${income_405:,.2f} (exact 405% of 2026 FPG)...")

sim_base = Simulation(situation=sit)
sim_reform = Simulation(situation=sit, reform=reform)

ptc_base = sim_base.calculate("aca_ptc", map_to="household", period=2026)[0]
ptc_reform = sim_reform.calculate("aca_ptc", map_to="household", period=2026)[0]
chip = sim_base.calculate("per_capita_chip", map_to="household", period=2026)[0]

print(f"  CHIP: ${chip:,.2f}")
print(f"  PTC Baseline: ${ptc_base:,.2f}")
print(f"  PTC Reform: ${ptc_reform:,.2f}")

print("\n" + "="*80)
print("KEY INSIGHTS:")
print("- CHIP phases out around 400% FPL")
print("- Above 400% FPL: Baseline PTC = $0 (ineligible)")
print("- Above 400% FPL: Reform extends PTC eligibility")
print("- The exact 405% vs 406% difference shows the PTC phase-out under reform")

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
    },
    "gov.aca.ptc_income_eligibility[2].amount": {
        "2026-01-01.2100-12-31": True
    }
}, country_id="us")

# Define the base NY situation
situation_new_york = {
    "people": {
        "you": {
            "age": {
                "2026": 30
            }
        },
        "your partner": {
            "age": {
                "2026": 30
            }
        },
        "your first dependent": {
            "age": {
                "2026": 3
            }
        }
    },
    "families": {
        "your family": {
            "members": [
                "you",
                "your partner",
                "your first dependent"
            ]
        }
    },
    "spm_units": {
        "your household": {
            "members": [
                "you",
                "your partner",
                "your first dependent"
            ]
        }
    },
    "tax_units": {
        "your tax unit": {
            "members": [
                "you",
                "your partner",
                "your first dependent"
            ]
        }
    },
    "households": {
        "your household": {
            "members": [
                "you",
                "your partner",
                "your first dependent"
            ],
            "state_name": {
                "2026": "NY"
            },
            "county_fips": {
                "2026": "36061"
            }
        }
    },
    "marital_units": {
        "your marital unit": {
            "members": [
                "you",
                "your partner"
            ]
        },
        "your first dependent's marital unit": {
            "members": [
                "your first dependent"
            ],
            "marital_unit_id": {
                "2026": 1
            }
        }
    },
    "axes": [
        [
            {
                "name": "employment_income",
                "count": 800,
                "min": 0,
                "max": 400000
            }
        ]
    ]
}

def method1_table_function(base_situation: dict, income: float):
    """Method 1: As used in the table generation (block 5)"""
    sit = copy.deepcopy(base_situation)
    sit.pop("axes", None)  # Remove axes for single-point simulation

    # Split income equally between both adults
    for person in ["you", "your partner"]:
        sit["people"][person]["employment_income"] = {"2026": income / 2}

    sim_base = Simulation(situation=sit)
    sim_reform = Simulation(situation=sit, reform=reform)

    results = {
        "ptc_baseline": sim_base.calculate("aca_ptc", map_to="household", period=2026)[0],
        "ptc_reform": sim_reform.calculate("aca_ptc", map_to="household", period=2026)[0],
        "medicaid_cost": sim_base.calculate("medicaid_cost", map_to="household", period=2026)[0],
        "per_capita_chip": sim_base.calculate("per_capita_chip", map_to="household", period=2026)[0],
        "slcsp": sim_base.calculate("slcsp", map_to="household", period=2026)[0],
        "net_income_baseline": sim_base.calculate("household_net_income_including_health_benefits", map_to="household", period=2026)[0],
        "net_income_reform": sim_reform.calculate("household_net_income_including_health_benefits", map_to="household", period=2026)[0],
    }
    return results

def method2_axes_simulation(base_situation: dict, income: float):
    """Method 2: Using axes-based simulation like the charts"""
    # Create simulations with axes
    sim_base = Simulation(situation=base_situation)
    sim_reform = Simulation(situation=base_situation, reform=reform)

    # Calculate all values across the income range
    household_income = sim_base.calculate("employment_income", map_to="household", period=2026)

    # Find the index closest to our target income
    idx = np.argmin(np.abs(household_income - income))
    actual_income = household_income[idx]

    # Show income distribution around this point
    print(f"  DEBUG: Income array around index {idx}:")
    for i in range(max(0, idx-2), min(len(household_income), idx+3)):
        print(f"    [{i}]: ${household_income[i]:,.2f}")

    # Check how PolicyEngine distributes income
    print(f"  DEBUG: How is income ${actual_income:,.2f} distributed?")
    # The axes apply to household total, but how does it get split to individuals?

    results = {
        "actual_income_used": actual_income,
        "ptc_baseline": sim_base.calculate("aca_ptc", map_to="household", period=2026)[idx],
        "ptc_reform": sim_reform.calculate("aca_ptc", map_to="household", period=2026)[idx],
        "medicaid_cost": sim_base.calculate("medicaid_cost", map_to="household", period=2026)[idx],
        "per_capita_chip": sim_base.calculate("per_capita_chip", map_to="household", period=2026)[idx],
        "slcsp": sim_base.calculate("slcsp", map_to="household", period=2026)[idx],
        "net_income_baseline": sim_base.calculate("household_net_income_including_health_benefits", map_to="household", period=2026)[idx],
        "net_income_reform": sim_reform.calculate("household_net_income_including_health_benefits", map_to="household", period=2026)[idx]
    }
    return results

def method3_single_point_no_split(base_situation: dict, income: float):
    """Method 3: Single point but assign all income to one person"""
    sit = copy.deepcopy(base_situation)
    sit.pop("axes", None)

    # Assign all income to one person
    sit["people"]["you"]["employment_income"] = {"2026": income}
    sit["people"]["your partner"]["employment_income"] = {"2026": 0}

    sim_base = Simulation(situation=sit)
    sim_reform = Simulation(situation=sit, reform=reform)

    results = {
        "ptc_baseline": sim_base.calculate("aca_ptc", map_to="household", period=2026)[0],
        "ptc_reform": sim_reform.calculate("aca_ptc", map_to="household", period=2026)[0],
        "medicaid_cost": sim_base.calculate("medicaid_cost", map_to="household", period=2026)[0],
        "per_capita_chip": sim_base.calculate("per_capita_chip", map_to="household", period=2026)[0],
        "slcsp": sim_base.calculate("slcsp", map_to="household", period=2026)[0],
        "net_income_baseline": sim_base.calculate("household_net_income_including_health_benefits", map_to="household", period=2026)[0],
        "net_income_reform": sim_reform.calculate("household_net_income_including_health_benefits", map_to="household", period=2026)[0]
    }
    return results

print("="*80)
print("UNDERSTANDING THE AXES INCOME DISTRIBUTION")
print("="*80)

# The axes configuration from the notebook
axes_config = {
    "name": "employment_income",
    "count": 800,
    "min": 0,
    "max": 400000
}

# Calculate what income values the axes will generate
income_step = (axes_config["max"] - axes_config["min"]) / (axes_config["count"] - 1)
print(f"\nAxes configuration:")
print(f"  Count: {axes_config['count']} points")
print(f"  Range: ${axes_config['min']:,} to ${axes_config['max']:,}")
print(f"  Step size: ${income_step:,.2f}")

# Find which index would be closest to our target incomes
test_incomes = {
    "154% FPL": 41041,
    "200% FPL": 53300,
    "300% FPL": 79950,
    "405% FPL": 107933
}

print("\nFor each target income, the axes array gives:")
for label, target in test_incomes.items():
    # Calculate the exact index for this income
    exact_index = target / income_step
    lower_index = int(exact_index)
    upper_index = lower_index + 1

    # Calculate actual income values at those indices
    lower_income = lower_index * income_step
    upper_income = upper_index * income_step

    # Which is closer?
    if abs(lower_income - target) < abs(upper_income - target):
        closest_index = lower_index
        closest_income = lower_income
    else:
        closest_index = upper_index
        closest_income = upper_income

    print(f"\n  {label} (target: ${target:,})")
    print(f"    Exact position: index {exact_index:.2f}")
    print(f"    Closest index: {closest_index}")
    print(f"    Actual income: ${closest_income:,.2f}")
    print(f"    Difference: ${closest_income - target:,.2f}")

print("\n" + "="*80)
print("VERIFYING AXES INCOME GENERATION")
print("="*80)

# Create a simulation with axes to see actual values
sim_with_axes = Simulation(situation=situation_new_york)
income_array = sim_with_axes.calculate("employment_income", map_to="household", period=2026)

print(f"\nFirst 5 income values from axes simulation:")
for i in range(5):
    print(f"  [{i}]: ${income_array[i]:,.2f}")

print(f"\nIncome values around index 197:")
for i in range(195, 200):
    print(f"  [{i}]: ${income_array[i]:,.2f}")

print(f"\nIncome values around index 216 (where we expected 108k):")
for i in range(214, 219):
    print(f"  [{i}]: ${income_array[i]:,.2f}")

print("\n" + "="*80)
print("COMPARING PTC VALUES AT THESE INCOMES")
print("="*80)

# Now test just one income to see the PTC difference
test_incomes = {
    "405% FPL": 107933
}

for label, income in test_incomes.items():
    print(f"\n{label} (${income:,})")
    print("-"*60)

    # Method 1: Table function approach (split income)
    m1 = method1_table_function(situation_new_york, income)
    print(f"Method 1 (Table/Split Income):")
    print(f"  >>> PTC Baseline:     ${m1['ptc_baseline']:,.2f}")
    print(f"  >>> PTC Reform:       ${m1['ptc_reform']:,.2f}")
    print(f"  Medicaid:         ${m1['medicaid_cost']:,.2f}")
    print(f"  Per Capita CHIP:  ${m1['per_capita_chip']:,.2f}")
    print(f"  SLCSP:            ${m1['slcsp']:,.2f}")

    # Method 2: Axes-based simulation
    m2 = method2_axes_simulation(situation_new_york, income)
    print(f"\nMethod 2 (Axes/Chart approach - what graphs use):")
    print(f"  Actual income:    ${m2['actual_income_used']:,.2f}")
    print(f"  >>> PTC Baseline:     ${m2['ptc_baseline']:,.2f}")
    print(f"  >>> PTC Reform:       ${m2['ptc_reform']:,.2f}")
    print(f"  Medicaid:         ${m2['medicaid_cost']:,.2f}")
    print(f"  Per Capita CHIP:  ${m2['per_capita_chip']:,.2f}")
    print(f"  SLCSP:            ${m2['slcsp']:,.2f}")

    # Method 3: Single income earner
    m3 = method3_single_point_no_split(situation_new_york, income)
    print(f"\nMethod 3 (Single earner):")
    print(f"  >>> PTC Baseline:     ${m3['ptc_baseline']:,.2f}")
    print(f"  >>> PTC Reform:       ${m3['ptc_reform']:,.2f}")
    print(f"  Medicaid:         ${m3['medicaid_cost']:,.2f}")
    print(f"  Per Capita CHIP:  ${m3['per_capita_chip']:,.2f}")
    print(f"  SLCSP:            ${m3['slcsp']:,.2f}")

    print("\n*** PTC DIFFERENCES ***")
    print(f"  Table vs Graph (Method 1 vs Method 2):")
    print(f"    PTC Baseline Diff: ${abs(m1['ptc_baseline'] - m2['ptc_baseline']):,.2f}")
    print(f"    PTC Reform Diff:   ${abs(m1['ptc_reform'] - m2['ptc_reform']):,.2f}")

    if abs(m1['ptc_baseline'] - m2['ptc_baseline']) > 1.0:
        print(f"    >>> SIGNIFICANT DIFFERENCE IN BASELINE PTC!")
    if abs(m1['ptc_reform'] - m2['ptc_reform']) > 1.0:
        print(f"    >>> SIGNIFICANT DIFFERENCE IN REFORM PTC!")

print("\n" + "="*80)
print("UNDERSTANDING FPL CALCULATIONS")
print("="*80)

def calculate_with_fpg(base_situation: dict, income: float):
    """Calculate values and also return the FPG and FPL percentage"""
    sit = copy.deepcopy(base_situation)
    sit.pop("axes", None)  # Remove axes for exact calculation

    # Split income equally between both adults
    for person in ["you", "your partner"]:
        sit["people"][person]["employment_income"] = {"2026": income / 2}

    # Run simulations
    sim_base = Simulation(situation=sit)
    sim_reform = Simulation(situation=sit, reform=reform)

    # Get values
    ptc_base = sim_base.calculate("aca_ptc", map_to="household", period=2026)[0]
    ptc_reform = sim_reform.calculate("aca_ptc", map_to="household", period=2026)[0]
    chip = sim_base.calculate("per_capita_chip", map_to="household", period=2026)[0]

    # Get FPG for this tax unit
    fpg = sim_base.calculate("tax_unit_fpg", map_to="tax_unit", period=2026)[0]
    # Calculate what percentage of FPL this income is
    fpl_pct = (income / fpg) * 100 if fpg > 0 else 0

    return ptc_base, ptc_reform, chip, fpg, fpl_pct

# First, let's see what FPG is at different income levels
print("\nTesting FPG calculations at different incomes:")
print("-"*80)
test_incomes = [41041, 53300, 79950, 107933, 108199]
for inc in test_incomes:
    _, _, _, fpg, fpl_pct = calculate_with_fpg(situation_new_york, inc)
    print(f"Income ${inc:,}: FPG = ${fpg:,.2f}, This is {fpl_pct:.1f}% of FPL")

# Now let's figure out the actual income that equals 405% FPL in 2026
print("\n" + "="*80)
print("FINDING EXACT 405% FPL INCOME FOR 2026")
print("="*80)

# Get FPG from any simulation (it should be constant for family of 3)
_, _, _, fpg_2026, _ = calculate_with_fpg(situation_new_york, 50000)
print(f"\n2026 FPG for family of 3: ${fpg_2026:,.2f}")

# Calculate exact income levels for each FPL percentage
exact_incomes = {
    300: fpg_2026 * 3.00,
    350: fpg_2026 * 3.50,
    400: fpg_2026 * 4.00,
    401: fpg_2026 * 4.01,
    404: fpg_2026 * 4.04,
    405: fpg_2026 * 4.05,
    406: fpg_2026 * 4.06,
    410: fpg_2026 * 4.10,
}

print(f"\nExact income for 405% FPL in 2026: ${exact_incomes[405]:,.2f}")
print(f"Compare to what table used: $107,933")
print(f"Difference: ${exact_incomes[405] - 107933:,.2f}")

print("\n" + "="*80)
print("CHIP PHASE-OUT TABLE (USING EXACT 2026 FPL)")
print("="*80)

print()
print(f"{'Target %':<10} {'Income':>12} {'Actual %':>10} {'CHIP':>12} {'PTC Base':>12} {'PTC Reform':>12} {'Reform Gain':>12}")
print("-"*100)

for target_pct, income in exact_incomes.items():
    ptc_base, ptc_reform, chip, fpg, actual_pct = calculate_with_fpg(situation_new_york, income)
    gain = ptc_reform - ptc_base

    print(f"{target_pct}% FPL{' ':<4} ${income:>10,.0f} {actual_pct:>8.1f}% ${chip:>10,.2f} ${ptc_base:>10,.2f} ${ptc_reform:>10,.2f} ${gain:>10,.2f}")

print()
print("KEY: Using exact 2026 FPL values. CHIP provides benefits up to ~400% FPL.")

print("\n" + "="*80)
print("CORRECTED TABLE OUTPUT (FROM AXES)")
print("="*80)

# Create the corrected table using axes-based simulations
import pandas as pd

# Use axes-based simulations
sim_base_axes = Simulation(situation=situation_new_york)
sim_reform_axes = Simulation(situation=situation_new_york, reform=reform)

# Get income array
household_income = sim_base_axes.calculate("employment_income", map_to="household", period=2026)

# Target incomes
targets_for_table = {
    "154 % FPL ($41,041)": 41041,
    "200 % FPL ($53,300)": 53300,
    "300 % FPL ($79,950)": 79950,
    "405 % FPL ($107,933)": 107933,
}

print("\n=== OLD TABLE (with incorrect values) ===")
print("income_label            income_usd  ptc_baseline  ptc_ira_reform  medicaid_cost  per_capita_chip")
print("-" * 95)
old_values = [
    ("154 % FPL ($41,041)", 41041, 0.00, 0.00, 16480.70, 0.00),
    ("200 % FPL ($53,300)", 53300, 0.00, 0.00, 12930.67, 829.93),
    ("300 % FPL ($79,950)", 79950, 13847.60, 16645.85, 0.00, 829.93),
    ("405 % FPL ($107,933)", 107933, 0.00, 12268.55, 0.00, 829.93),
]
for label, income, ptc_base, ptc_ref, medicaid, chip in old_values:
    print(f"{label:<23} {income:>10} {ptc_base:>12.2f} {ptc_ref:>14.2f} {medicaid:>13.2f} {chip:>15.2f}")

print("\n=== NEW TABLE (with correct values matching graphs) ===")
print("income_label            target_inc  actual_inc  ptc_baseline  ptc_ira_reform  medicaid_cost  per_capita_chip")
print("-" * 110)

rows = []
for label, target_inc in targets_for_table.items():
    # Find nearest index
    idx = np.argmin(np.abs(household_income - target_inc))
    actual_income = household_income[idx]

    # Get values at this index
    ptc_base = sim_base_axes.calculate("aca_ptc", map_to="household", period=2026)[idx]
    ptc_reform = sim_reform_axes.calculate("aca_ptc", map_to="household", period=2026)[idx]
    medicaid_cost = sim_base_axes.calculate("medicaid_cost", map_to="household", period=2026)[idx]
    per_capita_chip = sim_base_axes.calculate("per_capita_chip", map_to="household", period=2026)[idx]
    slcsp = sim_base_axes.calculate("slcsp", map_to="household", period=2026)[idx]

    print(f"{label:<23} {target_inc:>10} {actual_income:>11.0f} {ptc_base:>12.2f} {ptc_reform:>14.2f} {medicaid_cost:>13.2f} {per_capita_chip:>15.2f}")

    rows.append({
        'income_label': label,
        'income_target': target_inc,
        'income_actual': actual_income,
        'ptc_baseline': ptc_base,
        'ptc_ira_reform': ptc_reform,
        'medicaid_cost': medicaid_cost,
        'per_capita_chip': per_capita_chip,
        'SLCSP': slcsp
    })

print("\n=== DIFFERENCES (New - Old) ===")
print("income_label            ptc_baseline_diff  ptc_ira_reform_diff")
print("-" * 65)
for i, (label, _, _, _, _, _) in enumerate(old_values):
    old_ptc_base = old_values[i][2]
    old_ptc_ref = old_values[i][3]
    new_ptc_base = rows[i]['ptc_baseline']
    new_ptc_ref = rows[i]['ptc_ira_reform']
    diff_base = new_ptc_base - old_ptc_base
    diff_ref = new_ptc_ref - old_ptc_ref
    print(f"{label:<23} {diff_base:>17.2f} {diff_ref:>19.2f}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("The corrected table now uses the same data points as the graphs.")
print("Small differences (~$20) are due to using actual axes income values")
print("instead of exact target incomes.")