"""
Number of children by AGI bin: CPS 2023 vs Enhanced CPS 2024.

Run:
    uv run --python 3.11 \
      --with policyengine-us \
      --with plotly \
      python us/irs/income/credits/ctc/children_by_agi_bin.py

Outputs a table and a grouped bar chart comparing the two datasets.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from policyengine_us import Microsimulation


# Default dataset paths
CPS_2023 = Path(
    "/Users/pavelmakarchuk/policyengine-us-data/policyengine_us_data/storage/cps_2023.h5"
)
ENHANCED_CPS_2024 = "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5@1.46.0"

# AGI bins. Keep negative AGI separate, and treat exactly $0 as part of
# the $0-$10k bucket rather than the negative bucket.
AGI_BINS = [0, 10_000, 20_000, 30_000, 50_000, 75_000, 100_000, 150_000, 200_000, 500_000, np.inf]
AGI_LABELS = [
    "<$0",
    "$0-$10k",
    "$10k-$20k",
    "$20k-$30k",
    "$30k-$50k",
    "$50k-$75k",
    "$75k-$100k",
    "$100k-$150k",
    "$150k-$200k",
    "$200k-$500k",
    "$500k+",
]

YEAR = 2025


def get_children_by_agi(sim: Microsimulation, year: int) -> pd.DataFrame:
    """Return weighted number of children in each AGI bin.

    Uses person_weight at person level (consistent with API/app-v2 approach).
    AGI is mapped from tax_unit to person via membership.
    """
    # AGI at tax_unit level — extract raw values (not MicroSeries weighted sum)
    agi = sim.calculate("adjusted_gross_income", period=year)

    # Person-level variables — use .values to get raw numpy arrays
    age = sim.calculate("age", period=year)
    is_child = np.array(age.values < 18)

    # person_weight is the correct weight for person-level counts
    person_weight = sim.calculate("person_weight", period=year)

    # Map tax_unit AGI to person level via tax_unit membership
    tax_unit_id = sim.calculate("person_tax_unit_id", period=year)
    tax_unit_ids = sim.calculate("tax_unit_id", period=year)
    tax_unit_agi = pd.Series(
        np.array(agi.values), index=np.array(tax_unit_ids.values)
    )
    person_agi = pd.Series(np.array(tax_unit_id.values)).map(tax_unit_agi)

    df = pd.DataFrame({
        "agi": person_agi.values,
        "is_child": is_child,
        "weight": person_weight.values,
    })

    # Filter to children only
    children = df[df["is_child"]].copy()

    # Bin by AGI. Use left-closed intervals so:
    # - negative AGI remains in the "<$0" bucket
    # - AGI == 0 falls in the "$0-$10k" bucket
    bins = [-np.inf] + AGI_BINS
    children["agi_bin"] = pd.cut(
        children["agi"],
        bins=bins,
        labels=AGI_LABELS,
        right=False,
    )

    # Weighted count per bin
    result = children.groupby("agi_bin", observed=False)["weight"].sum().reset_index()
    result.columns = ["agi_bin", "children"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare number of children by AGI bin across datasets"
    )
    parser.add_argument(
        "--cps-2023",
        default=str(CPS_2023),
        help="Path to cps_2023.h5",
    )
    parser.add_argument(
        "--enhanced-cps-2024",
        default=ENHANCED_CPS_2024,
        help="Path or identifier for enhanced_cps_2024",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=YEAR,
        help="Simulation year (default: 2025)",
    )
    parser.add_argument(
        "--output-dir",
        default="us/irs/income/credits/ctc/legacy_webapp_charts",
        help="Directory to write output chart",
    )
    args = parser.parse_args()

    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Loading CPS 2023 from: {args.cps_2023}")
    sim_cps = Microsimulation(dataset=args.cps_2023)

    print(f"Loading Enhanced CPS 2024: {args.enhanced_cps_2024}")
    sim_ecps = Microsimulation(dataset=args.enhanced_cps_2024)

    print(f"\nComputing children by AGI bin for year {args.year}...")
    df_cps = get_children_by_agi(sim_cps, args.year)
    df_ecps = get_children_by_agi(sim_ecps, args.year)

    # Merge for comparison
    comparison = df_cps.merge(df_ecps, on="agi_bin", suffixes=("_cps23", "_ecps24"))
    comparison["difference"] = comparison["children_ecps24"] - comparison["children_cps23"]
    comparison["pct_diff"] = (
        comparison["difference"] / comparison["children_cps23"].replace(0, np.nan) * 100
    )

    # Format for display
    display = comparison.copy()
    display["children_cps23"] = display["children_cps23"].apply(lambda x: f"{x:,.0f}")
    display["children_ecps24"] = display["children_ecps24"].apply(lambda x: f"{x:,.0f}")
    display["difference"] = display["difference"].apply(lambda x: f"{x:+,.0f}")
    display["pct_diff"] = display["pct_diff"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "N/A")

    print("\n" + "=" * 80)
    print("NUMBER OF CHILDREN BY AGI BIN: CPS 2023 vs Enhanced CPS 2024")
    print("=" * 80)
    print(display.to_string(index=False))
    print(f"\nTotal children CPS 2023:         {comparison['children_cps23'].sum():,.0f}")
    print(f"Total children Enhanced CPS 2024: {comparison['children_ecps24'].sum():,.0f}")

    # Save as tab-separated with comma-formatted numbers
    csv_path = outdir / "children_by_agi_bin.tsv"
    out = comparison.copy()
    out["children_cps23"] = out["children_cps23"].apply(lambda x: f"{x:,.0f}")
    out["children_ecps24"] = out["children_ecps24"].apply(lambda x: f"{x:,.0f}")
    out["difference"] = out["difference"].apply(lambda x: f"{x:+,.0f}")
    out["pct_diff"] = out["pct_diff"].apply(lambda x: f"{x:+.1f}%")
    out.to_csv(csv_path, index=False, sep="\t")
    print(f"\nCSV saved to: {csv_path}")

    # Grouped bar chart
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=comparison["agi_bin"],
        y=comparison["children_cps23"],
        name="CPS 2023",
        marker_color="#2C6496",
    ))
    fig.add_trace(go.Bar(
        x=comparison["agi_bin"],
        y=comparison["children_ecps24"],
        name="Enhanced CPS 2024",
        marker_color="#D8E6F3",
    ))
    fig.update_layout(
        title="Number of Children by AGI Bin",
        xaxis_title="AGI Bin",
        yaxis_title="Number of Children (weighted)",
        yaxis_tickformat=",",
        barmode="group",
        font={"family": "Roboto Serif"},
        plot_bgcolor="rgba(0,0,0,0)",
        height=550,
        margin={"t": 60, "b": 100, "l": 80, "r": 20},
        legend={"yanchor": "top", "y": 0.99, "xanchor": "right", "x": 0.99},
    )
    fig.update_xaxes(tickangle=-45)

    chart_path = outdir / "children_by_agi_bin.html"
    fig.write_html(str(chart_path), include_plotlyjs="cdn")
    print(f"Chart saved to: {chart_path}")


if __name__ == "__main__":
    main()
