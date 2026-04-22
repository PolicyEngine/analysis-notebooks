"""Generate interactive HTML charts for Utah HB 15 blog post."""

import plotly.graph_objects as go
from policyengine_us import Simulation
from policyengine_core.periods import instant
from policyengine_core.reforms import Reform
import os

YEAR = 2027
OUTPUT_DIR = "/Users/daphnehansell/Documents/GitHub/utah-hb15-charts"

# PolicyEngine colors
BLUE_PRIMARY = '#2C6496'
TEAL_ACCENT = '#39C6C0'
GRAY = '#808080'
DARK_GRAY = '#616161'


def create_ut_medicaid_expansion_repeal():
    def modify_parameters(parameters):
        parameters.gov.hhs.medicaid.eligibility.categories.adult.income_limit.UT.update(
            start=instant(f'{YEAR}-01-01'),
            stop=instant('2100-12-31'),
            value=float('-inf'),
        )
        return parameters

    class reform(Reform):
        def apply(self):
            self.modify_parameters(modify_parameters)

    return reform


def create_chart_html(fig, title):
    """Create standalone HTML with Plotly chart."""
    # Update layout for embedding
    fig.update_layout(
        font=dict(family="Roboto, sans-serif"),
        paper_bgcolor='white',
        plot_bgcolor='white',
        margin=dict(l=60, r=40, t=60, b=60),
    )

    # Get Plotly HTML
    html = fig.to_html(
        include_plotlyjs='cdn',
        full_html=True,
        config={'displayModeBar': False, 'responsive': True}
    )

    # Add Roboto font
    html = html.replace(
        '<head>',
        '<head>\n<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet">'
    )

    return html


def generate_charts():
    """Generate interactive charts for the blog post."""

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Single adult situation with axes
    single_situation = {
        'people': {
            'adult': {
                'age': {YEAR: 35},
                'monthly_hours_worked': {YEAR: 100},
            }
        },
        'tax_units': {'tax_unit': {'members': ['adult']}},
        'spm_units': {'spm_unit': {'members': ['adult']}},
        'households': {'household': {'members': ['adult'], 'state_code': {YEAR: 'UT'}}},
        'families': {'family': {'members': ['adult']}},
        'marital_units': {'marital_unit': {'members': ['adult']}},
        'axes': [[{'name': 'employment_income', 'count': 300, 'min': 0, 'max': 100000}]],
    }

    # Parent + child situation with axes
    parent_situation = {
        'people': {
            'parent': {
                'age': {YEAR: 30},
                'monthly_hours_worked': {YEAR: 100},
            },
            'child': {'age': {YEAR: 8}},
        },
        'tax_units': {'tax_unit': {'members': ['parent', 'child']}},
        'spm_units': {'spm_unit': {'members': ['parent', 'child']}},
        'households': {'household': {'members': ['parent', 'child'], 'state_code': {YEAR: 'UT'}}},
        'families': {'family': {'members': ['parent', 'child']}},
        'marital_units': {'marital_unit': {'members': ['parent']}},
        'axes': [[{'name': 'employment_income', 'count': 300, 'min': 0, 'max': 100000}]],
    }

    print('Creating simulations...')
    single_base = Simulation(situation=single_situation)
    single_reform = Simulation(situation=single_situation, reform=create_ut_medicaid_expansion_repeal())
    parent_base = Simulation(situation=parent_situation)
    parent_reform = Simulation(situation=parent_situation, reform=create_ut_medicaid_expansion_repeal())

    print('Calculating single adult data...')
    single_income = single_base.calculate('employment_income', YEAR)
    single_baseline_medicaid = single_base.calculate('medicaid', YEAR, map_to='person')
    single_baseline_ptc = single_base.calculate('premium_tax_credit', YEAR, map_to='person')
    single_reform_medicaid = single_reform.calculate('medicaid', YEAR, map_to='person')
    single_reform_ptc = single_reform.calculate('premium_tax_credit', YEAR, map_to='person')

    print('Calculating parent+child data...')
    parent_income = parent_base.calculate('employment_income', YEAR)
    # Parent coverage
    parent_baseline_medicaid = parent_base.calculate('medicaid', YEAR, map_to='person')[::2]
    parent_baseline_ptc = parent_base.calculate('premium_tax_credit', YEAR, map_to='person')[::2]
    parent_reform_medicaid = parent_reform.calculate('medicaid', YEAR, map_to='person')[::2]
    parent_reform_ptc = parent_reform.calculate('premium_tax_credit', YEAR, map_to='person')[::2]
    # Child coverage (same under baseline and reform - children keep Medicaid/CHIP)
    child_baseline_medicaid = parent_base.calculate('medicaid', YEAR, map_to='person')[1::2]
    child_baseline_chip = parent_base.calculate('chip', YEAR, map_to='person')[1::2]
    child_reform_medicaid = parent_reform.calculate('medicaid', YEAR, map_to='person')[1::2]
    child_reform_chip = parent_reform.calculate('chip', YEAR, map_to='person')[1::2]
    # Household totals (parent + child)
    household_baseline_medicaid = parent_baseline_medicaid + child_baseline_medicaid + child_baseline_chip
    household_reform_medicaid = parent_reform_medicaid + child_reform_medicaid + child_reform_chip
    parent_income = parent_income[::2]

    # Single Adult Chart
    print('Creating single adult chart...')
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=single_income, y=single_baseline_medicaid,
        mode='lines', name='Medicaid (Baseline)',
        line=dict(color=TEAL_ACCENT, width=3),
        hovertemplate='Income: $%{x:,.0f}<br>Medicaid: $%{y:,.0f}<extra></extra>'
    ))
    fig.add_trace(go.Scatter(
        x=single_income, y=single_baseline_ptc,
        mode='lines', name='ACA PTC (Baseline)',
        line=dict(color=BLUE_PRIMARY, width=3),
        hovertemplate='Income: $%{x:,.0f}<br>ACA PTC: $%{y:,.0f}<extra></extra>'
    ))
    fig.add_trace(go.Scatter(
        x=single_income, y=single_reform_medicaid,
        mode='lines', name='Medicaid (Reform)',
        line=dict(color=TEAL_ACCENT, width=3, dash='dot'),
        hovertemplate='Income: $%{x:,.0f}<br>Medicaid: $%{y:,.0f}<extra></extra>'
    ))
    fig.add_trace(go.Scatter(
        x=single_income, y=single_reform_ptc,
        mode='lines', name='ACA PTC (Reform)',
        line=dict(color=BLUE_PRIMARY, width=3, dash='dot'),
        hovertemplate='Income: $%{x:,.0f}<br>ACA PTC: $%{y:,.0f}<extra></extra>'
    ))

    fig.update_layout(
        title='Single Adult: Health Benefits by Income (Utah 2027)',
        xaxis_title='Household Income',
        yaxis_title='Annual Benefit Amount',
        xaxis=dict(tickformat='$,.0f', range=[0, 100000]),
        yaxis=dict(tickformat='$,.0f'),
        height=500,
        width=800,
        legend=dict(orientation='h', yanchor='bottom', y=-0.25, xanchor='center', x=0.5),
        hovermode='x unified',
    )

    html = create_chart_html(fig, 'Single Adult')
    with open(f'{OUTPUT_DIR}/single-adult.html', 'w') as f:
        f.write(html)
    print(f'  Saved {OUTPUT_DIR}/single-adult.html')

    # Parent + Child Chart
    print('Creating parent+child chart...')
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=parent_income, y=household_baseline_medicaid,
        mode='lines', name='Medicaid/CHIP (Baseline)',
        line=dict(color=TEAL_ACCENT, width=3),
        hovertemplate='Income: $%{x:,.0f}<br>Medicaid/CHIP: $%{y:,.0f}<extra></extra>'
    ))
    fig.add_trace(go.Scatter(
        x=parent_income, y=parent_baseline_ptc,
        mode='lines', name='ACA PTC (Baseline)',
        line=dict(color=BLUE_PRIMARY, width=3),
        hovertemplate='Income: $%{x:,.0f}<br>ACA PTC: $%{y:,.0f}<extra></extra>'
    ))
    fig.add_trace(go.Scatter(
        x=parent_income, y=household_reform_medicaid,
        mode='lines', name='Medicaid/CHIP (Reform)',
        line=dict(color=TEAL_ACCENT, width=3, dash='dot'),
        hovertemplate='Income: $%{x:,.0f}<br>Medicaid/CHIP: $%{y:,.0f}<extra></extra>'
    ))
    fig.add_trace(go.Scatter(
        x=parent_income, y=parent_reform_ptc,
        mode='lines', name='ACA PTC (Reform)',
        line=dict(color=BLUE_PRIMARY, width=3, dash='dot'),
        hovertemplate='Income: $%{x:,.0f}<br>ACA PTC: $%{y:,.0f}<extra></extra>'
    ))

    fig.update_layout(
        title='Single Parent + Child: Health Benefits by Income (Utah 2027)',
        xaxis_title='Household Income',
        yaxis_title='Annual Benefit Amount',
        xaxis=dict(tickformat='$,.0f', range=[0, 100000]),
        yaxis=dict(tickformat='$,.0f'),
        height=500,
        width=800,
        legend=dict(orientation='h', yanchor='bottom', y=-0.25, xanchor='center', x=0.5),
        hovermode='x unified',
    )

    html = create_chart_html(fig, 'Parent + Child')
    with open(f'{OUTPUT_DIR}/parent-child.html', 'w') as f:
        f.write(html)
    print(f'  Saved {OUTPUT_DIR}/parent-child.html')

    print('Done!')


if __name__ == '__main__':
    generate_charts()
