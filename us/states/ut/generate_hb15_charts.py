"""Generate charts for Utah HB 15 blog post."""

import numpy as np
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
    print('Generating data...')
    incomes = np.arange(5000, 40001, 2000)

    single_baseline_medicaid, single_baseline_ptc = [], []
    single_reform_medicaid, single_reform_ptc = [], []
    parent_baseline_medicaid, parent_baseline_ptc = [], []
    parent_reform_medicaid, parent_reform_ptc = [], []

    for i, income in enumerate(incomes):
        print(f'  Processing income ${income:,} ({i+1}/{len(incomes)})')

        # Single adult
        single_situation = {
            'people': {'adult': {'age': {YEAR: 35}, 'employment_income': {YEAR: int(income)}, 'monthly_hours_worked': {YEAR: 100}}},
            'tax_units': {'tax_unit': {'members': ['adult']}},
            'spm_units': {'spm_unit': {'members': ['adult']}},
            'households': {'household': {'members': ['adult'], 'state_code': {YEAR: 'UT'}}},
            'families': {'family': {'members': ['adult']}},
            'marital_units': {'marital_unit': {'members': ['adult']}},
        }
        base = Simulation(situation=single_situation)
        ref = Simulation(situation=single_situation, reform=create_ut_medicaid_expansion_repeal())
        single_baseline_medicaid.append(base.calculate('medicaid', YEAR, map_to='person')[0])
        single_baseline_ptc.append(base.calculate('premium_tax_credit', YEAR)[0])
        single_reform_medicaid.append(ref.calculate('medicaid', YEAR, map_to='person')[0])
        single_reform_ptc.append(ref.calculate('premium_tax_credit', YEAR)[0])

        # Parent + child
        parent_situation = {
            'people': {'parent': {'age': {YEAR: 30}, 'employment_income': {YEAR: int(income)}, 'monthly_hours_worked': {YEAR: 100}}, 'child': {'age': {YEAR: 8}}},
            'tax_units': {'tax_unit': {'members': ['parent', 'child']}},
            'spm_units': {'spm_unit': {'members': ['parent', 'child']}},
            'households': {'household': {'members': ['parent', 'child'], 'state_code': {YEAR: 'UT'}}},
            'families': {'family': {'members': ['parent', 'child']}},
            'marital_units': {'marital_unit': {'members': ['parent']}},
        }
        base = Simulation(situation=parent_situation)
        ref = Simulation(situation=parent_situation, reform=create_ut_medicaid_expansion_repeal())
        parent_baseline_medicaid.append(base.calculate('medicaid', YEAR, map_to='person')[0])
        parent_baseline_ptc.append(base.calculate('premium_tax_credit', YEAR)[0])
        parent_reform_medicaid.append(ref.calculate('medicaid', YEAR, map_to='person')[0])
        parent_reform_ptc.append(ref.calculate('premium_tax_credit', YEAR)[0])

    incomes_arr = np.array(incomes)

    # Single Adult Chart
    print('Creating single adult chart...')
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=incomes_arr/1000, y=single_baseline_medicaid, mode='lines', name='Medicaid (Baseline)', line=dict(color=TEAL_ACCENT, width=2)))
    fig.add_trace(go.Scatter(x=incomes_arr/1000, y=single_baseline_ptc, mode='lines', name='ACA PTC (Baseline)', line=dict(color=BLUE_PRIMARY, width=2)))
    fig.add_trace(go.Scatter(x=incomes_arr/1000, y=single_reform_medicaid, mode='lines', name='Medicaid (Reform)', line=dict(color=TEAL_ACCENT, width=2, dash='dot')))
    fig.add_trace(go.Scatter(x=incomes_arr/1000, y=single_reform_ptc, mode='lines', name='ACA PTC (Reform)', line=dict(color=BLUE_PRIMARY, width=2, dash='dot')))
    fig.update_layout(
        title='Single Adult: Health Benefits by Income',
        xaxis_title='Household Income ($1,000s)',
        yaxis_title='Annual Benefit',
        yaxis=dict(tickformat='$,.0f'),
        height=500,
        width=800,
        legend=dict(orientation='h', yanchor='bottom', y=-0.25, xanchor='center', x=0.5),
    )
    fig = format_fig(fig)
    fig.write_image('hb15_single_adult.png', scale=2)
    print('  Saved hb15_single_adult.png')

    # Parent + Child Chart
    print('Creating parent+child chart...')
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=incomes_arr/1000, y=parent_baseline_medicaid, mode='lines', name='Medicaid (Baseline)', line=dict(color=TEAL_ACCENT, width=2)))
    fig.add_trace(go.Scatter(x=incomes_arr/1000, y=parent_baseline_ptc, mode='lines', name='ACA PTC (Baseline)', line=dict(color=BLUE_PRIMARY, width=2)))
    fig.add_trace(go.Scatter(x=incomes_arr/1000, y=parent_reform_medicaid, mode='lines', name='Medicaid (Reform)', line=dict(color=TEAL_ACCENT, width=2, dash='dot')))
    fig.add_trace(go.Scatter(x=incomes_arr/1000, y=parent_reform_ptc, mode='lines', name='ACA PTC (Reform)', line=dict(color=BLUE_PRIMARY, width=2, dash='dot')))
    fig.update_layout(
        title='Single Parent + Child: Health Benefits by Income',
        xaxis_title='Household Income ($1,000s)',
        yaxis_title='Annual Benefit',
        yaxis=dict(tickformat='$,.0f'),
        height=500,
        width=800,
        legend=dict(orientation='h', yanchor='bottom', y=-0.25, xanchor='center', x=0.5),
    )
    fig = format_fig(fig)
    fig.write_image('hb15_parent_child.png', scale=2)
    print('  Saved hb15_parent_child.png')

    print('Done!')


if __name__ == '__main__':
    main()
