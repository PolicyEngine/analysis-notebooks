#!/usr/bin/env python3
"""
FAST MTR calculation using axes-based simulations for net income.
Texas couple (ages 25 & 28, no kids) - baseline vs IRA extension reform.
"""

from policyengine_us import Simulation
from policyengine_core.reforms import Reform
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from policyengine_core.charts import format_fig
import time
from datetime import datetime

# PolicyEngine app colors
DARK_GRAY = "#616161"
BLUE_PRIMARY = "#2C6496"

# Define the IRA extension reform
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

def create_tx_household_situation_with_axes(period=2026, count=100, max_income=200_000):
    """Creates a TX couple situation WITH AXES for vectorized calculation."""
    return {
        "people": {
            "you": {
                "age": {str(period): 25},
                "employment_income": {str(period): 0},  # Will be set by axes
                "self_employment_income": {str(period): 0}
            },
            "your partner": {
                "age": {str(period): 28},
                "employment_income": {str(period): 0},  # Will be set by axes
                "self_employment_income": {str(period): 0}
            }
        },
        "families": {
            "your family": {
                "members": ["you", "your partner"]
            }
        },
        "spm_units": {
            "your household": {
                "members": ["you", "your partner"]
            }
        },
        "tax_units": {
            "your tax unit": {
                "members": ["you", "your partner"]
            }
        },
        "households": {
            "your household": {
                "members": ["you", "your partner"],
                "state_name": {str(period): "TX"},
                "county_fips": {str(period): "48015"}
            }
        },
        "marital_units": {
            "your marital unit": {
                "members": ["you", "your partner"]
            }
        },
        "axes": [[
            {
                "name": "employment_income",
                "min": 0,
                "max": max_income,
                "count": count,
                "period": str(period)
            }
        ]]
    }

def main():
    print("=" * 70)
    print("FAST MTR CALCULATION USING AXES - TEXAS COUPLE")
    print("Expected runtime: 1-2 minutes (vs 25+ minutes with loops!)")
    print("=" * 70)

    start_time = time.time()
    print(f"\nStart time: {datetime.now().strftime('%H:%M:%S')}\n")

    # Use 200 points for good resolution
    num_points = 200

    # Step 1: Baseline with axes
    print(f"STEP 1: Calculating baseline at {num_points} points using axes...")
    baseline_start = time.time()

    situation_baseline = create_tx_household_situation_with_axes(period=2026, count=num_points, max_income=200_000)

    try:
        sim_baseline = Simulation(situation=situation_baseline)

        # Get the income values from the axes
        household_income_baseline = sim_baseline.calculate("employment_income", map_to="household", period=2026)

        # Calculate net income including health benefits
        baseline_net_income = sim_baseline.calculate(
            "household_net_income_including_health_benefits",
            map_to="household",
            period=2026
        )

        # Also get ACA PTC for verification
        baseline_aca_ptc = sim_baseline.calculate("aca_ptc", map_to="household", period=2026)

        baseline_time = time.time() - baseline_start
        print(f"✓ Baseline calculated in {baseline_time:.1f} seconds!\n")

    except Exception as e:
        print(f"✗ Baseline failed: {e}")
        return

    # Step 2: Reform with axes
    print(f"STEP 2: Calculating reform at {num_points} points using axes...")
    reform_start = time.time()

    situation_reform = create_tx_household_situation_with_axes(period=2026, count=num_points, max_income=200_000)

    try:
        sim_reform = Simulation(situation=situation_reform, reform=reform)

        # Get the income values from the axes
        household_income_reform = sim_reform.calculate("employment_income", map_to="household", period=2026)

        # Calculate net income including health benefits WITH REFORM
        reform_net_income = sim_reform.calculate(
            "household_net_income_including_health_benefits",
            map_to="household",
            period=2026
        )

        # Also get ACA PTC for verification
        reform_aca_ptc = sim_reform.calculate("aca_ptc", map_to="household", period=2026)

        reform_time = time.time() - reform_start
        print(f"✓ Reform calculated in {reform_time:.1f} seconds!")
        print(f"🎉 THIS IS {(25*60)/reform_time:.0f}X FASTER THAN LOOPING!\n")

    except Exception as e:
        print(f"✗ Reform failed: {e}")
        return

    # Step 3: Calculate MTRs from adjacent points
    print("STEP 3: Calculating MTRs from adjacent points...")

    def calc_mtr(incomes, net_incomes):
        mtrs = []
        mtr_incomes = []
        for i in range(len(incomes) - 1):
            income_change = incomes[i + 1] - incomes[i]
            net_change = net_incomes[i + 1] - net_incomes[i]
            if income_change > 0 and not np.isnan(net_incomes[i]) and not np.isnan(net_incomes[i + 1]):
                mtr = 1 - (net_change / income_change)
                mtrs.append(mtr)
                mtr_incomes.append((incomes[i] + incomes[i + 1]) / 2)
        return np.array(mtr_incomes), np.array(mtrs)

    baseline_mtr_incomes, baseline_mtrs = calc_mtr(household_income_baseline, baseline_net_income)
    reform_mtr_incomes, reform_mtrs = calc_mtr(household_income_reform, reform_net_income)

    print(f"✓ MTRs calculated\n")

    # Verify the calculations
    print("VERIFICATION:")
    print(f"Baseline average MTR: {baseline_mtrs.mean():.2%}")
    print(f"Reform average MTR: {reform_mtrs.mean():.2%}")

    # Check at $150k
    idx_150k = np.argmin(np.abs(baseline_mtr_incomes - 150_000))
    if idx_150k < len(baseline_mtrs):
        print(f"\nAt ~$150k income:")
        print(f"  Baseline MTR: {baseline_mtrs[idx_150k]:.2%}")
        print(f"  Reform MTR: {reform_mtrs[idx_150k]:.2%}")
        print(f"  Difference: {reform_mtrs[idx_150k] - baseline_mtrs[idx_150k]:.2%}")
        print(f"  (Should be ~8.5% higher for reform)")

    # Check ACA amounts at 400% FPL (around $87k for couple)
    idx_87k = np.argmin(np.abs(household_income_baseline - 87_000))
    print(f"\nAt ~$87k income (near 400% FPL cliff):")
    print(f"  Baseline ACA PTC: ${baseline_aca_ptc[idx_87k]:,.2f}")
    print(f"  Reform ACA PTC: ${reform_aca_ptc[idx_87k]:,.2f}")

    # Step 4: Create visualization
    print("\nSTEP 4: Creating visualization...")

    fig = go.Figure()

    # Baseline MTR (solid line)
    fig.add_trace(go.Scatter(
        x=baseline_mtr_incomes,
        y=np.clip(baseline_mtrs, -1.0, 1.0),
        mode='lines',
        name='Baseline',
        line=dict(color=DARK_GRAY, width=2),
        hovertemplate='Income: $%{x:,.0f}<br>Baseline MTR: %{y:.1%}<extra></extra>'
    ))

    # Reform MTR (dashed line)
    fig.add_trace(go.Scatter(
        x=reform_mtr_incomes,
        y=np.clip(reform_mtrs, -1.0, 1.0),
        mode='lines',
        name='IRA Extension',
        line=dict(color=BLUE_PRIMARY, width=2, dash='dash'),
        hovertemplate='Income: $%{x:,.0f}<br>Reform MTR: %{y:.1%}<extra></extra>'
    ))

    # Update layout
    fig.update_layout(
        title='Marginal tax rate including health benefits - Texas Couple',
        xaxis_title='Employment income',
        yaxis_title='Marginal tax rate',
        xaxis=dict(
            tickformat='$,.0f',
            range=[0, 200_000],
            gridcolor='lightgray',
            showgrid=True
        ),
        yaxis=dict(
            tickformat='.0%',
            range=[-1.0, 1.0],
            gridcolor='lightgray',
            showgrid=True,
            zeroline=True,
            zerolinewidth=1,
            zerolinecolor='gray'
        ),
        height=600,
        width=1000,
        hovermode='x unified',
        plot_bgcolor='white',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    fig = format_fig(fig)
    fig.show()

    # Save outputs with extra height for logo
    fig.write_image("tx_mtr_baseline_vs_reform_fast.png", width=1000, height=650, scale=2)
    print("Chart saved as tx_mtr_baseline_vs_reform_fast.png")

    # Save data
    combined_df = pd.DataFrame({
        'income': baseline_mtr_incomes,
        'baseline_mtr': baseline_mtrs,
        'baseline_mtr_display': np.clip(baseline_mtrs, -1.0, 1.0)
    }).merge(
        pd.DataFrame({
            'income': reform_mtr_incomes,
            'reform_mtr': reform_mtrs,
            'reform_mtr_display': np.clip(reform_mtrs, -1.0, 1.0)
        }),
        on='income',
        how='outer'
    ).sort_values('income')

    combined_df.to_csv("tx_mtr_baseline_vs_reform_fast.csv", index=False)
    print("Data saved to tx_mtr_baseline_vs_reform_fast.csv")

    # Total time
    total_time = time.time() - start_time
    print(f"\n" + "=" * 70)
    print(f"TOTAL RUNTIME: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
    print(f"End time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"\nThis was ~{(25*60)/total_time:.0f}X faster than the loop-based approach!")
    print("=" * 70)

if __name__ == "__main__":
    main()