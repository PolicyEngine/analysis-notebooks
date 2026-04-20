"""
Render legacy PolicyEngine app charts from the old macro payload.

This script targets the closest reproducible setup we found for the November 4,
2025 legacy web-app path:

    uv run --python 3.11 \
      --with policyengine==0.3.9 \
      --with policyengine-us==1.425.4 \
      --with policyengine-core==3.20.1 \
      --with plotly \
      python us/irs/income/credits/ctc/render_legacy_webapp_charts.py

It writes Plotly HTML files for the chart families whose payloads are present in
the old macro output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from policyengine import Simulation

from reproduce_legacy_webapp_path import DEFAULT_DATASET, build_reform


BLUE = "#2C6496"
BLUE_LIGHT = "#D8E6F3"
DARK_GRAY = "#616161"
LIGHT_GRAY = "#F2F2F2"
MEDIUM_LIGHT_GRAY = "#BDBDBD"
PLOT_FONT = "Roboto Serif"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET),
        help="Path to the dataset file used by the old macro simulation.",
    )
    parser.add_argument(
        "--time-period",
        type=int,
        default=2025,
        help="Simulation year.",
    )
    parser.add_argument(
        "--region",
        default="us",
        help="Region argument passed to the old macro simulation.",
    )
    parser.add_argument(
        "--output-dir",
        default="us/irs/income/credits/ctc/legacy_webapp_charts",
        help="Directory to write HTML charts and payload JSON into.",
    )
    return parser.parse_args()


def run_impact(dataset: Path, time_period: int, region: str) -> dict:
    simulation = Simulation(
        country="us",
        scope="macro",
        reform=build_reform(),
        time_period=time_period,
        region=region,
        data=str(dataset),
    )
    return simulation.calculate_economy_comparison().model_dump()


def base_layout(title: str, height: int = 500) -> dict:
    return {
        "title": {"text": title},
        "font": {"family": PLOT_FONT},
        "plot_bgcolor": "rgba(0,0,0,0)",
        "showlegend": False,
        "height": height,
        "margin": {"t": 60, "b": 80, "l": 60, "r": 20},
    }


def write_chart(fig: go.Figure, path: Path) -> None:
    fig.write_html(str(path), include_plotlyjs="cdn")


def render_budget_chart(impact: dict, outdir: Path) -> None:
    budget = impact["budget"]
    state_tax = budget["state_tax_revenue_impact"] / 1e9
    tax = (budget["tax_revenue_impact"] - budget["state_tax_revenue_impact"]) / 1e9
    spending = -budget["benefit_spending_impact"] / 1e9
    total = budget["budgetary_impact"] / 1e9

    labels = []
    values = []
    for label, value in [
        ("Federal tax revenues", tax),
        ("State and local income tax revenues", state_tax),
        ("Benefit spending", spending),
        ("Net impact", total),
    ]:
        if value != 0:
            labels.append(label)
            values.append(value)

    measures = ["relative"] * max(len(values) - 1, 0) + ["total"]
    fig = go.Figure(
        go.Waterfall(
            x=labels,
            y=values,
            measure=measures,
            text=[f"${v:,.1f}bn" for v in values],
            textposition="inside",
            increasing={"marker": {"color": BLUE}},
            decreasing={"marker": {"color": DARK_GRAY}},
            totals={"marker": {"color": DARK_GRAY if total < 0 else BLUE}},
            connector={"line": {"color": MEDIUM_LIGHT_GRAY, "width": 2, "dash": "dot"}},
        )
    )
    fig.update_layout(
        **base_layout("Budgetary impact"),
        yaxis={"title": "Budgetary impact (bn)", "tickformat": "$,.1f"},
    )
    write_chart(fig, outdir / "budgetary_impact_overall.html")


def render_decile_average_chart(impact: dict, outdir: Path) -> None:
    data = impact["decile"]["average"]
    x = list(data.keys())
    y = list(data.values())
    fig = go.Figure(
        go.Bar(
            x=x,
            y=y,
            marker={"color": [DARK_GRAY if value < 0 else BLUE for value in y]},
            text=[f"${value:,.0f}" for value in y],
            textangle=0,
        )
    )
    fig.update_layout(
        **base_layout("Distributional impact by income decile (average)"),
        xaxis={"title": "Income decile"},
        yaxis={"title": "Average change in household income", "tickformat": "$,.0f"},
    )
    write_chart(fig, outdir / "distributional_income_decile_average.html")


def render_decile_relative_chart(impact: dict, outdir: Path) -> None:
    data = impact["decile"]["relative"]
    x = list(data.keys())
    y = list(data.values())
    fig = go.Figure(
        go.Bar(
            x=x,
            y=y,
            marker={"color": [DARK_GRAY if value < 0 else BLUE for value in y]},
            text=[f"{value:+.1%}" for value in y],
            textangle=0,
        )
    )
    fig.update_layout(
        **base_layout("Distributional impact by income decile (relative)"),
        xaxis={"title": "Income decile"},
        yaxis={"title": "Relative change in household income", "tickformat": "+,.1%"},
    )
    write_chart(fig, outdir / "distributional_income_decile_relative.html")


def render_intra_decile_chart(impact: dict, outdir: Path) -> None:
    all_data = impact["intra_decile"]["all"]
    deciles = impact["intra_decile"]["deciles"]
    categories = [
        "Gain more than 5%",
        "Gain less than 5%",
        "No change",
        "Lose less than 5%",
        "Lose more than 5%",
    ]
    colors = {
        "Gain more than 5%": BLUE,
        "Gain less than 5%": BLUE_LIGHT,
        "No change": LIGHT_GRAY,
        "Lose less than 5%": MEDIUM_LIGHT_GRAY,
        "Lose more than 5%": DARK_GRAY,
    }

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.10,
        row_heights=[0.12, 0.88],
    )

    for category in categories:
        fig.add_trace(
            go.Bar(
                x=[all_data[category]],
                y=["All"],
                orientation="h",
                name=category,
                marker={"color": colors[category]},
                text=[f"{all_data[category]:.0%}"],
                textposition="inside",
                showlegend=True,
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Bar(
                x=deciles[category],
                y=[str(i) for i in range(1, 11)],
                orientation="h",
                name=category,
                marker={"color": colors[category]},
                text=[f"{value:.0%}" for value in deciles[category]],
                textposition="inside",
                showlegend=False,
            ),
            row=2,
            col=1,
        )

    fig.update_layout(
        **base_layout("Winners and losers by income decile", height=650),
        barmode="stack",
        legend={
            "title": {"text": "Change in income"},
            "font": {"family": PLOT_FONT},
        },
    )
    fig.update_xaxes(title_text="Population share", tickformat=".0%", row=2, col=1)
    fig.update_yaxes(title_text="", row=1, col=1)
    fig.update_yaxes(title_text="Income decile", row=2, col=1)
    write_chart(fig, outdir / "winners_losers_income_decile.html")


def render_poverty_chart(
    series: dict,
    outpath: Path,
    title: str,
    labels: list[str],
    keys: list[str],
    yaxis_title: str,
) -> None:
    changes = [series[key]["reform"] / series[key]["baseline"] - 1 for key in keys]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=changes,
            marker={"color": [BLUE if value < 0 else DARK_GRAY for value in changes]},
            text=[f"{value:+.1%}" for value in changes],
            textangle=0,
        )
    )
    fig.update_layout(
        **base_layout(title),
        yaxis={"title": yaxis_title, "tickformat": "+,.1%"},
    )
    write_chart(fig, outpath)


def render_inequality_chart(impact: dict, outdir: Path) -> None:
    inequality = impact["inequality"]
    labels = ["Gini index", "Top 10% share", "Top 1% share"]
    keys = ["gini", "top_10_pct_share", "top_1_pct_share"]
    changes = [
        inequality[key]["reform"] / inequality[key]["baseline"] - 1 for key in keys
    ]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=changes,
            marker={"color": [BLUE if value < 0 else DARK_GRAY for value in changes]},
            text=[f"{value:+.1%}" for value in changes],
            textangle=0,
        )
    )
    fig.update_layout(
        **base_layout("Income inequality impact"),
        yaxis={"title": "Relative change", "tickformat": "+,.1%"},
    )
    write_chart(fig, outdir / "inequality_impact.html")


def main() -> None:
    args = parse_args()
    dataset_path = Path(args.dataset).expanduser()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    impact = run_impact(dataset_path, args.time_period, args.region)

    (outdir / "impact_payload.json").write_text(
        json.dumps(impact, indent=2, sort_keys=True)
    )

    render_budget_chart(impact, outdir)
    render_decile_average_chart(impact, outdir)
    render_decile_relative_chart(impact, outdir)
    render_intra_decile_chart(impact, outdir)
    render_poverty_chart(
        impact["poverty"]["poverty"],
        outdir / "poverty_by_age.html",
        "Poverty impact by age",
        ["Children", "Working-age adults", "Seniors", "All"],
        ["child", "adult", "senior", "all"],
        "Relative change in poverty rate",
    )
    render_poverty_chart(
        impact["poverty"]["deep_poverty"],
        outdir / "deep_poverty_by_age.html",
        "Deep poverty impact by age",
        ["Children", "Working-age adults", "Seniors", "All"],
        ["child", "adult", "senior", "all"],
        "Relative change in deep poverty rate",
    )
    render_poverty_chart(
        {
            "male": impact["poverty_by_gender"]["poverty"]["male"],
            "female": impact["poverty_by_gender"]["poverty"]["female"],
            "all": impact["poverty"]["poverty"]["all"],
        },
        outdir / "poverty_by_gender.html",
        "Poverty impact by gender",
        ["Male", "Female", "All"],
        ["male", "female", "all"],
        "Relative change in poverty rate",
    )
    render_poverty_chart(
        {
            "male": impact["poverty_by_gender"]["deep_poverty"]["male"],
            "female": impact["poverty_by_gender"]["deep_poverty"]["female"],
            "all": impact["poverty"]["deep_poverty"]["all"],
        },
        outdir / "deep_poverty_by_gender.html",
        "Deep poverty impact by gender",
        ["Male", "Female", "All"],
        ["male", "female", "all"],
        "Relative change in deep poverty rate",
    )
    render_poverty_chart(
        {
            "white": impact["poverty_by_race"]["poverty"]["white"],
            "black": impact["poverty_by_race"]["poverty"]["black"],
            "hispanic": impact["poverty_by_race"]["poverty"]["hispanic"],
            "other": impact["poverty_by_race"]["poverty"]["other"],
            "all": impact["poverty"]["poverty"]["all"],
        },
        outdir / "poverty_by_race.html",
        "Poverty impact by race and ethnicity",
        ["White (non-Hispanic)", "Black (non-Hispanic)", "Hispanic", "Other", "All"],
        ["white", "black", "hispanic", "other", "all"],
        "Relative change in poverty rate",
    )
    render_inequality_chart(impact, outdir)

    skipped = {
        "cliff_impact": impact.get("cliff_impact") is None,
        "wealth_decile": impact.get("wealth_decile") is None,
        "intra_wealth_decile": impact.get("intra_wealth_decile") is None,
        "constituency_impact": impact.get("constituency_impact") is None,
        "detailed_budget": not impact.get("detailed_budget"),
    }
    (outdir / "skipped_sections.json").write_text(
        json.dumps(skipped, indent=2, sort_keys=True)
    )

    print(json.dumps({"output_dir": str(outdir), "skipped": skipped}, indent=2))


if __name__ == "__main__":
    main()
