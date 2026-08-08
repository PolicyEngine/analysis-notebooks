"""Generate interactive distributional charts for Utah HB 15 blog post."""

import plotly.graph_objects as go
import numpy as np
from policyengine_us import Microsimulation
from policyengine_core.periods import instant
from policyengine_core.reforms import Reform

YEAR = 2027
OUTPUT_DIR = "/Users/daphnehansell/Documents/GitHub/utah-hb15-charts"
UT_DATASET = "hf://policyengine/policyengine-us-data/states/UT.h5"

# PolicyEngine colors
BLUE_PRIMARY = '#2C6496'
TEAL_ACCENT = '#39C6C0'
GRAY = '#808080'
DARK_GRAY = '#616161'
LIGHT_BLUE = '#6FA8DC'


def create_ut_medicaid_expansion_repeal():
    """Create reform that repeals Utah's Medicaid expansion."""
    def modify_parameters(parameters):
        parameters.gov.hhs.medicaid.eligibility.categories.adult.income_limit.UT.update(
            start=instant(f"{YEAR}-01-01"),
            stop=instant("2100-12-31"),
            value=float("-inf"),
        )
        return parameters

    class reform(Reform):
        def apply(self):
            self.modify_parameters(modify_parameters)

    return reform


def create_chart_html(fig):
    """Create standalone HTML with Plotly chart."""
    fig.update_layout(
        font=dict(family="Roboto, sans-serif"),
        paper_bgcolor='white',
        plot_bgcolor='white',
        margin=dict(l=60, r=40, t=60, b=60),
    )

    html = fig.to_html(
        include_plotlyjs='cdn',
        full_html=True,
        config={'displayModeBar': False, 'responsive': True}
    )

    html = html.replace(
        '<head>',
        '<head>\n<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet">'
    )

    return html


def generate_distributional_charts():
    """Generate distributional analysis charts."""

    print("Loading simulations...")
    baseline = Microsimulation(dataset=UT_DATASET)
    reform = Microsimulation(dataset=UT_DATASET, reform=create_ut_medicaid_expansion_repeal())

    # Get data
    person_weights = baseline.calculate("person_weight", YEAR).values
    baseline_medicaid = baseline.calculate("medicaid_enrolled", YEAR).values
    reform_medicaid = reform.calculate("medicaid_enrolled", YEAR).values
    loses_medicaid = baseline_medicaid & ~reform_medicaid

    reform_ptc_eligible = reform.calculate("is_aca_ptc_eligible", YEAR).values
    coverage_gap = loses_medicaid & ~reform_ptc_eligible
    gains_aca = loses_medicaid & reform_ptc_eligible

    # Income and demographics
    spm_income = baseline.calculate("spm_unit_net_income", YEAR, map_to="person").values
    age = baseline.calculate("age", YEAR).values

    # Weighted data for those losing coverage
    affected_weights = person_weights * loses_medicaid.astype(float)
    gap_weights = person_weights * coverage_gap.astype(float)
    aca_weights = person_weights * gains_aca.astype(float)

    # =========================================================================
    # Chart 1: Income Distribution by Decile
    # =========================================================================
    print("Creating income distribution chart by decile...")

    # Calculate income deciles for the entire Utah population
    # Use weighted percentiles to define decile boundaries

    # Calculate weighted decile boundaries for all people
    sorted_indices = np.argsort(spm_income)
    sorted_income = spm_income[sorted_indices]
    sorted_weights = person_weights[sorted_indices]
    cumulative_weights = np.cumsum(sorted_weights)
    total_weight = cumulative_weights[-1]

    # Find income thresholds at each decile
    decile_thresholds = [0]
    for decile in range(1, 10):
        target_weight = total_weight * decile / 10
        idx = np.searchsorted(cumulative_weights, target_weight)
        decile_thresholds.append(sorted_income[min(idx, len(sorted_income) - 1)])
    decile_thresholds.append(float('inf'))

    # Create decile labels with income ranges
    decile_labels = []
    for i in range(10):
        low = decile_thresholds[i]
        high = decile_thresholds[i + 1]
        if i == 9:
            decile_labels.append(f'10th\n(>${low/1000:.0f}k)')
        else:
            decile_labels.append(f'{i+1}{"st" if i==0 else "nd" if i==1 else "rd" if i==2 else "th"}\n(${low/1000:.0f}-{high/1000:.0f}k)')

    # Calculate weighted counts for each decile
    gap_counts = []
    aca_counts = []

    for i in range(10):
        low = decile_thresholds[i]
        high = decile_thresholds[i + 1]
        in_decile = (spm_income >= low) & (spm_income < high)
        gap_counts.append((gap_weights * in_decile.astype(float)).sum())
        aca_counts.append((aca_weights * in_decile.astype(float)).sum())

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Coverage Gap',
        x=decile_labels,
        y=[c / 1000 for c in gap_counts],
        marker_color=TEAL_ACCENT,
        hovertemplate='Decile %{x}<br>Coverage Gap: %{y:.1f}k people<extra></extra>'
    ))

    fig.add_trace(go.Bar(
        name='ACA Transition',
        x=decile_labels,
        y=[c / 1000 for c in aca_counts],
        marker_color=BLUE_PRIMARY,
        hovertemplate='Decile %{x}<br>ACA Transition: %{y:.1f}k people<extra></extra>'
    ))

    fig.update_layout(
        title='Affected Population by Household Income Decile',
        xaxis_title='Household Income Decile',
        yaxis_title='People (thousands)',
        barmode='stack',
        height=500,
        width=700,
        legend=dict(orientation='h', yanchor='top', y=1.05, xanchor='center', x=0.5),
        hovermode='x unified',
        xaxis=dict(tickangle=0),
        margin=dict(b=100, t=80),
    )

    html = create_chart_html(fig)
    with open(f'{OUTPUT_DIR}/income-distribution.html', 'w') as f:
        f.write(html)
    print(f'  Saved {OUTPUT_DIR}/income-distribution.html')

    # =========================================================================
    # Chart 2: Age Distribution
    # =========================================================================
    print("Creating age distribution chart...")

    age_bins = [(18, 25), (26, 34), (35, 44), (45, 54), (55, 64)]
    age_labels = ['18-25', '26-34', '35-44', '45-54', '55-64']

    gap_age_counts = []
    aca_age_counts = []

    for min_age, max_age in age_bins:
        in_bin = (age >= min_age) & (age <= max_age)
        gap_age_counts.append((gap_weights * in_bin.astype(float)).sum())
        aca_age_counts.append((aca_weights * in_bin.astype(float)).sum())

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Coverage Gap',
        x=age_labels,
        y=[c / 1000 for c in gap_age_counts],
        marker_color=TEAL_ACCENT,
        hovertemplate='Age %{x}<br>Coverage Gap: %{y:.1f}k people<extra></extra>'
    ))

    fig.add_trace(go.Bar(
        name='ACA Transition',
        x=age_labels,
        y=[c / 1000 for c in aca_age_counts],
        marker_color=BLUE_PRIMARY,
        hovertemplate='Age %{x}<br>ACA Transition: %{y:.1f}k people<extra></extra>'
    ))

    fig.update_layout(
        title='Affected Population by Age',
        xaxis_title='Age Group',
        yaxis_title='People (thousands)',
        barmode='stack',
        height=450,
        width=700,
        legend=dict(orientation='h', yanchor='top', y=1.05, xanchor='center', x=0.5),
        hovermode='x unified',
        xaxis=dict(tickangle=0),
        margin=dict(t=80),
    )

    html = create_chart_html(fig)
    with open(f'{OUTPUT_DIR}/age-distribution.html', 'w') as f:
        f.write(html)
    print(f'  Saved {OUTPUT_DIR}/age-distribution.html')

    print("Done!")


if __name__ == "__main__":
    generate_distributional_charts()
