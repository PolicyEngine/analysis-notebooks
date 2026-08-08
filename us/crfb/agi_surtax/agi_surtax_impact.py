from policyengine_us import Microsimulation
from policyengine_core.reforms import Reform
import pandas as pd


def run_10yr_impact(reform, csv_path, label=""):
    """Run 10-year income tax impact analysis for a reform."""
    pd.DataFrame(columns=["year", "revenue_billions"]).to_csv(csv_path, index=False)

    total = 0
    for year in range(2026, 2036):
        baseline = Microsimulation()
        reformed = Microsimulation(reform=reform)

        baseline_tax = baseline.calculate("income_tax", period=year).sum() / 1e9
        reformed_tax = reformed.calculate("income_tax", period=year).sum() / 1e9

        revenue = reformed_tax - baseline_tax
        total += revenue
        print(f"{year}: ${revenue:.2f}B")

        pd.DataFrame([{"year": year, "revenue_billions": round(revenue, 2)}]).to_csv(
            csv_path, mode="a", header=False, index=False
        )

    pd.DataFrame([{"year": "Total", "revenue_billions": round(total, 2)}]).to_csv(
        csv_path, mode="a", header=False, index=False
    )
    print(f"\n10-Year Total{' (' + label + ')' if label else ''}: ${total:.2f}B")
    return total


def validate_income_sources(year=2026):
    """Validate that key income sources have data in the microsimulation."""
    print(f"\n{'=' * 80}")
    print(f"Income Source Validation ({year})")
    print("=" * 80)

    baseline = Microsimulation()

    # Sources with external benchmarks for validation
    # Format: (variable_name, label, external_low, external_high, source_note)
    sources = [
        (
            "traditional_401k_contributions",
            "Traditional 401(k) contributions",
            250,
            300,
            "JCT JCX-48-24: $251B tax expenditure implies ~$300-400B contributions",
        ),
        (
            "tax_exempt_social_security",
            "Tax-exempt Social Security",
            580,
            690,
            "SSA: $1.38T total benefits (2023), ~42-50% tax-exempt",
        ),
        (
            "health_insurance_premiums",
            "Employer health insurance premiums",
            900,
            1000,
            "CMS/KFF: $1.6T private insurance, ~75% employer-paid",
        ),
        (
            "tax_exempt_interest_income",
            "Tax-exempt interest income",
            120,
            150,
            "CRS IF12969: $4.2T muni bonds at 3-4% yield",
        ),
        (
            "health_savings_account_ald",
            "Health Savings Account (ALD)",
            50,
            60,
            "Devenir 2024: $56B total HSA contributions",
        ),
        (
            "traditional_ira_contributions",
            "Traditional IRA contributions",
            20,
            25,
            "ICI: $22B traditional IRA contributions (2020)",
        ),
        (
            "traditional_403b_contributions",
            "Traditional 403(b) contributions",
            50,
            70,
            "Expected: similar to 401k scale for nonprofits/education",
        ),
    ]

    results = []
    print(
        f"{'Income Source':<35} {'PE 2026':>12} {'External':>15} {'Status':>10}"
    )
    print("-" * 80)

    for var_name, label, ext_low, ext_high, note in sources:
        try:
            total = baseline.calculate(var_name, period=year).sum() / 1e9
            external_range = f"${ext_low}-{ext_high}B"

            if total == 0:
                status = "⚠️ No data"
            elif ext_low <= total <= ext_high:
                status = "✅ Match"
            elif total < ext_low * 0.5:
                status = "❌ Low"
            elif total > ext_high * 1.5:
                status = "❌ High"
            else:
                status = "⚠️ Close"

            print(f"{label:<35} {f'${total:.1f}B':>12} {external_range:>15} {status:>10}")
            results.append((label, total, ext_low, ext_high, status, note))
        except Exception as e:
            print(f"{label:<35} {'N/A':>12} {f'${ext_low}-{ext_high}B':>15} {'❌ Error':>10}")
            results.append((label, None, ext_low, ext_high, f"Error: {e}", note))

    print("-" * 80)
    print("\nNotes on external benchmarks:")
    for label, total, ext_low, ext_high, status, note in results:
        if "❌" in status or "⚠️" in status:
            print(f"  • {label}: {note}")

    return results


if __name__ == "__main__":
    # Validate income sources first
    validate_income_sources(2026)

    # Basic AGI surtax (1% on $100k/$200k, 2% on $1M)
    reform_basic = Reform.from_dict(
        {
            "gov.contrib.crfb.surtax.in_effect": {"2026-01-01.2100-12-31": True},
        },
        country_id="us",
    )

    print("=" * 50)
    print("Basic AGI Surtax")
    print("=" * 50)
    run_10yr_impact(reform_basic, "agi_surtax_10yr_impact.csv", "Basic")

    # Surtax with EXPANDED BASE (adds retirement contributions, HSA, tax-exempt income, etc.)
    reform_expanded = Reform.from_dict(
        {
            "gov.contrib.crfb.surtax.in_effect": {"2026-01-01.2100-12-31": True},
            "gov.contrib.crfb.surtax.increased_base.in_effect": {
                "2026-01-01.2100-12-31": True
            },
        },
        country_id="us",
    )

    print("\n" + "=" * 50)
    print("Expanded Base AGI Surtax")
    print("=" * 50)
    run_10yr_impact(reform_expanded, "agi_surtax_expanded_base_10yr_impact.csv", "Expanded Base")

    # CBO Option 46b comparison: 2% flat surtax on AGI above $100k/$200k
    reform_cbo_2pct = Reform.from_dict(
        {
            "gov.contrib.crfb.surtax.in_effect": {"2026-01-01.2100-12-31": True},
            # Override to flat 2% (no tiered structure)
            "gov.contrib.crfb.surtax.rate.single[1].rate": {
                "2026-01-01.2100-12-31": 0.02
            },
            "gov.contrib.crfb.surtax.rate.single[2].rate": {
                "2026-01-01.2100-12-31": 0.02
            },
            "gov.contrib.crfb.surtax.rate.joint[1].rate": {
                "2026-01-01.2100-12-31": 0.02
            },
            "gov.contrib.crfb.surtax.rate.joint[2].rate": {
                "2026-01-01.2100-12-31": 0.02
            },
        },
        country_id="us",
    )

    print("\n" + "=" * 50)
    print("CBO 2% Flat Surtax Comparison")
    print("=" * 50)
    run_10yr_impact(reform_cbo_2pct, "cbo_comparison_2pct_10yr.csv", "CBO 2% Flat")
