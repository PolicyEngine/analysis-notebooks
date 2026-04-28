#!/usr/bin/env python
"""
CTC Reform Analysis for 2026-2035
Calculates changes in net income and income tax for each year
"""

from policyengine_us import Microsimulation
from policyengine_core.reforms import Reform
import pandas as pd
import gc
import os

# Define the CTC reform
reform = Reform.from_dict(
    {
        "gov.irs.credits.ctc.phase_out.threshold.JOINT": {
            "2025-01-01.2100-12-31": 150000
        },
        "gov.irs.credits.ctc.phase_out.threshold.SINGLE": {
            "2025-01-01.2100-12-31": 75000
        },
        "gov.irs.credits.ctc.phase_out.threshold.SEPARATE": {
            "2025-01-01.2100-12-31": 75000
        },
        "gov.irs.credits.ctc.phase_out.threshold.SURVIVING_SPOUSE": {
            "2025-01-01.2100-12-31": 150000
        },
        "gov.irs.credits.ctc.phase_out.threshold.HEAD_OF_HOUSEHOLD": {
            "2025-01-01.2100-12-31": 75000
        },
    },
    country_id="us",
)

print("Running CTC Reform Analysis for 2026-2035...")
print("=" * 50)

# CSV filename
csv_filename = "us/ctc_reform_2026_2035_results.csv"

# Remove existing file if it exists
if os.path.exists(csv_filename):
    os.remove(csv_filename)
    print(f"Removed existing {csv_filename}")

# Store results
results = []

# Analyze each year
for year in range(2026, 2036):
    print(f"\nAnalyzing year {year}...")

    # Create simulations fresh for each year to avoid memory issues
    baseline = Microsimulation()
    reformed = Microsimulation(reform=reform)

    # Calculate net income
    baseline_income = baseline.calculate("household_net_income", period=year)
    reformed_income = reformed.calculate("household_net_income", period=year)
    income_change = (reformed_income - baseline_income).sum()

    # Calculate income tax (aggregated to household level)
    baseline_tax = baseline.calculate("income_tax", period=year, map_to="household")
    reformed_tax = reformed.calculate("income_tax", period=year, map_to="household")
    tax_change = (reformed_tax - baseline_tax).sum()

    result = {
        "year": year,
        "net_income_change": income_change,
        "income_tax_change": tax_change
    }
    results.append(result)

    print(f"  Net income change: ${income_change:,.0f}")
    print(f"  Income tax change: ${tax_change:,.0f}")

    # Write to CSV incrementally
    df_temp = pd.DataFrame(results)
    df_temp.to_csv(csv_filename, index=False)
    print(f"  Saved progress to {csv_filename}")

    # Clean up memory
    del baseline
    del reformed
    del baseline_income
    del reformed_income
    del baseline_tax
    del reformed_tax
    gc.collect()

# Create final DataFrame with total
df = pd.DataFrame(results)

# Add total row
total_row = pd.DataFrame([{
    "year": "Total",
    "net_income_change": df["net_income_change"].sum(),
    "income_tax_change": df["income_tax_change"].sum()
}])

df = pd.concat([df, total_row], ignore_index=True)

# Save final CSV with total
df.to_csv(csv_filename, index=False)

print("\n" + "=" * 50)
print("SUMMARY RESULTS")
print("=" * 50)
print(df.to_string(index=False))

print(f"\nResults saved to: {csv_filename}")
print("Done!")