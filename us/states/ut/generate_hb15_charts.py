"""Generate charts for Utah HB 15 blog post using axes feature."""

import plotly.graph_objects as go
from policyengine_us import Simulation
from policyengine_core.periods import instant
from policyengine_core.reforms import Reform
from policyengine_core.charts import format_fig

YEAR = 2027
GRAY = '#808080'
BLUE_PRIMARY = '#2C6496'
TEAL_ACCENT = '#39C6C0'
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


def main():
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
        'axes': [[{'name': 'employment_income', 'count': 500, 'min': 0, 'max': 50000}]],
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
        'axes': [[{'name': 'employment_income', 'count': 500, 'min': 0, 'max': 50000}]],
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
    # Get only the parent's medicaid (index 0), not the child's
    parent_baseline_medicaid = parent_base.calculate('medicaid', YEAR, map_to='person')[::2]  # Every other (parent only)
    parent_baseline_ptc = parent_base.calculate('premium_tax_credit', YEAR, map_to='person')[::2]
    parent_reform_medicaid = parent_reform.calculate('medicaid', YEAR, map_to='person')[::2]
    parent_reform_ptc = parent_reform.calculate('premium_tax_credit', YEAR, map_to='person')[::2]
    parent_income = parent_income[::2]  # Match the income array

    # Single Adult Chart
    print('Creating single adult chart...')
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=single_income, y=single_baseline_medicaid, mode='lines', name='Medicaid (Baseline)', line=dict(color=TEAL_ACCENT, width=2)))
    fig.add_trace(go.Scatter(x=single_income, y=single_baseline_ptc, mode='lines', name='ACA PTC (Baseline)', line=dict(color=BLUE_PRIMARY, width=2)))
    fig.add_trace(go.Scatter(x=single_income, y=single_reform_medicaid, mode='lines', name='Medicaid (Reform)', line=dict(color=TEAL_ACCENT, width=2, dash='dot')))
    fig.add_trace(go.Scatter(x=single_income, y=single_reform_ptc, mode='lines', name='ACA PTC (Reform)', line=dict(color=BLUE_PRIMARY, width=2, dash='dot')))
    fig.update_layout(
        title='Single Adult: Health Benefits by Income',
        xaxis_title='Household Income',
        yaxis_title='Benefit Amount',
        xaxis=dict(tickformat='$,.0f', range=[0, 50000]),
        yaxis=dict(tickformat='$,.0f'),
        height=600,
        width=1000,
        legend=dict(orientation='h', yanchor='bottom', y=-0.2, xanchor='center', x=0.5),
    )
    fig = format_fig(fig)
    fig.write_image('hb15_single_adult.png', scale=2)
    print('  Saved hb15_single_adult.png')

    # Parent + Child Chart
    print('Creating parent+child chart...')
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=parent_income, y=parent_baseline_medicaid, mode='lines', name='Medicaid (Baseline)', line=dict(color=TEAL_ACCENT, width=2)))
    fig.add_trace(go.Scatter(x=parent_income, y=parent_baseline_ptc, mode='lines', name='ACA PTC (Baseline)', line=dict(color=BLUE_PRIMARY, width=2)))
    fig.add_trace(go.Scatter(x=parent_income, y=parent_reform_medicaid, mode='lines', name='Medicaid (Reform)', line=dict(color=TEAL_ACCENT, width=2, dash='dot')))
    fig.add_trace(go.Scatter(x=parent_income, y=parent_reform_ptc, mode='lines', name='ACA PTC (Reform)', line=dict(color=BLUE_PRIMARY, width=2, dash='dot')))
    fig.update_layout(
        title='Single Parent + Child: Health Benefits by Income',
        xaxis_title='Household Income',
        yaxis_title='Benefit Amount',
        xaxis=dict(tickformat='$,.0f', range=[0, 50000]),
        yaxis=dict(tickformat='$,.0f'),
        height=600,
        width=1000,
        legend=dict(orientation='h', yanchor='bottom', y=-0.2, xanchor='center', x=0.5),
    )
    fig = format_fig(fig)
    fig.write_image('hb15_parent_child.png', scale=2)
    print('  Saved hb15_parent_child.png')

    print('Done!')


if __name__ == '__main__':
    main()
