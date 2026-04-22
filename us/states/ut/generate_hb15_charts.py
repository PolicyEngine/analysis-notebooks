"""Generate charts and tables for Utah HB 15 blog post."""

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

# FPL values for 2027
FPL_1_PERSON = 16334
FPL_2_PERSON = 22138


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


def generate_table_data():
    """Generate table data at selected income levels."""

    print("=" * 60)
    print("SINGLE ADULT TABLE DATA")
    print("=" * 60)

    # Selected income levels for single adult
    single_incomes = [
        (12000, "75%", "Coverage gap"),
        (16334, "100%", "FPL threshold"),
        (18000, "110%", "ACA eligible"),
        (22541, "138%", "Expansion limit"),
        (25000, "153%", "Above expansion"),
    ]

    print(f"{'Income':<12} {'% FPL':<8} {'Medicaid (Base)':<18} {'Medicaid (Reform)':<18} {'ACA PTC (Base)':<16} {'ACA PTC (Reform)':<16} {'Notes'}")
    print("-" * 120)

    for income, fpl_pct, notes in single_incomes:
        situation = {
            'people': {'adult': {'age': {YEAR: 35}, 'employment_income': {YEAR: income}, 'monthly_hours_worked': {YEAR: 100}}},
            'tax_units': {'tax_unit': {'members': ['adult']}},
            'spm_units': {'spm_unit': {'members': ['adult']}},
            'households': {'household': {'members': ['adult'], 'state_code': {YEAR: 'UT'}}},
            'families': {'family': {'members': ['adult']}},
            'marital_units': {'marital_unit': {'members': ['adult']}},
        }

        base = Simulation(situation=situation)
        ref = Simulation(situation=situation, reform=create_ut_medicaid_expansion_repeal())

        b_medicaid = base.calculate('medicaid', YEAR, map_to='person')[0]
        r_medicaid = ref.calculate('medicaid', YEAR, map_to='person')[0]
        b_ptc = base.calculate('premium_tax_credit', YEAR)[0]
        r_ptc = ref.calculate('premium_tax_credit', YEAR)[0]

        print(f"${income:<11,} {fpl_pct:<8} ${b_medicaid:<17,.0f} ${r_medicaid:<17,.0f} ${b_ptc:<15,.0f} ${r_ptc:<15,.0f} {notes}")

    print()
    print("=" * 60)
    print("SINGLE PARENT + CHILD TABLE DATA")
    print("=" * 60)

    # Selected income levels for parent+child
    # Note: Utah has parent Medicaid at 46% FPL, so very low income parents still get coverage
    parent_incomes = [
        (8000, "36%", "Parent Medicaid (below 46% FPL)"),
        (12000, "54%", "Coverage gap (above 46% FPL)"),
        (22138, "100%", "FPL threshold"),
        (30550, "138%", "Expansion limit"),
        (35000, "158%", "Above expansion (CHIP)"),
    ]

    print(f"{'Income':<12} {'% FPL':<8} {'Parent Medicaid (B)':<20} {'Parent Medicaid (R)':<20} {'Child Medicaid/CHIP':<20} {'ACA PTC (B)':<14} {'ACA PTC (R)':<14} {'Notes'}")
    print("-" * 140)

    for income, fpl_pct, notes in parent_incomes:
        situation = {
            'people': {
                'parent': {'age': {YEAR: 30}, 'employment_income': {YEAR: income}, 'monthly_hours_worked': {YEAR: 100}},
                'child': {'age': {YEAR: 8}},
            },
            'tax_units': {'tax_unit': {'members': ['parent', 'child']}},
            'spm_units': {'spm_unit': {'members': ['parent', 'child']}},
            'households': {'household': {'members': ['parent', 'child'], 'state_code': {YEAR: 'UT'}}},
            'families': {'family': {'members': ['parent', 'child']}},
            'marital_units': {'marital_unit': {'members': ['parent']}},
        }

        base = Simulation(situation=situation)
        ref = Simulation(situation=situation, reform=create_ut_medicaid_expansion_repeal())

        # Parent is index 0, child is index 1
        b_parent_medicaid = base.calculate('medicaid', YEAR, map_to='person')[0]
        r_parent_medicaid = ref.calculate('medicaid', YEAR, map_to='person')[0]
        b_child_medicaid = base.calculate('medicaid', YEAR, map_to='person')[1]
        b_child_chip = base.calculate('chip', YEAR, map_to='person')[1]
        b_ptc = base.calculate('premium_tax_credit', YEAR)[0]
        r_ptc = ref.calculate('premium_tax_credit', YEAR)[0]

        # Child coverage = Medicaid + CHIP (same in both scenarios)
        child_total = b_child_medicaid + b_child_chip
        child_coverage = f"${child_total:,.0f}"

        print(f"${income:<11,} {fpl_pct:<8} ${b_parent_medicaid:<19,.0f} ${r_parent_medicaid:<19,.0f} {child_coverage:<20} ${b_ptc:<13,.0f} ${r_ptc:<13,.0f} {notes}")


def generate_charts():
    """Generate charts for the blog post."""

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
        'axes': [[{'name': 'employment_income', 'count': 500, 'min': 0, 'max': 120000}]],
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
        'axes': [[{'name': 'employment_income', 'count': 500, 'min': 0, 'max': 120000}]],
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
    # Parent is every other starting at 0, child is every other starting at 1
    parent_baseline_medicaid = parent_base.calculate('medicaid', YEAR, map_to='person')[::2]
    parent_baseline_ptc = parent_base.calculate('premium_tax_credit', YEAR, map_to='person')[::2]
    parent_reform_medicaid = parent_reform.calculate('medicaid', YEAR, map_to='person')[::2]
    parent_reform_ptc = parent_reform.calculate('premium_tax_credit', YEAR, map_to='person')[::2]
    # Child coverage = Medicaid + CHIP (same in baseline and reform)
    child_medicaid = parent_base.calculate('medicaid', YEAR, map_to='person')[1::2]
    child_chip = parent_base.calculate('chip', YEAR, map_to='person')[1::2]
    child_coverage = child_medicaid + child_chip
    parent_income = parent_income[::2]

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
        xaxis=dict(tickformat='$,.0f', range=[0, 120000]),
        yaxis=dict(tickformat='$,.0f'),
        height=600,
        width=1000,
        legend=dict(orientation='h', yanchor='bottom', y=-0.2, xanchor='center', x=0.5),
    )
    fig = format_fig(fig)
    fig.write_image('hb15_single_adult.png', scale=2)
    print('  Saved hb15_single_adult.png')

    # Parent + Child Chart (including child's Medicaid/CHIP)
    print('Creating parent+child chart...')
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=parent_income, y=parent_baseline_medicaid, mode='lines', name='Parent Medicaid (Baseline)', line=dict(color=TEAL_ACCENT, width=2)))
    fig.add_trace(go.Scatter(x=parent_income, y=child_coverage, mode='lines', name='Child Medicaid/CHIP', line=dict(color=GRAY, width=2)))
    fig.add_trace(go.Scatter(x=parent_income, y=parent_baseline_ptc, mode='lines', name='ACA PTC (Baseline)', line=dict(color=BLUE_PRIMARY, width=2)))
    fig.add_trace(go.Scatter(x=parent_income, y=parent_reform_medicaid, mode='lines', name='Parent Medicaid (Reform)', line=dict(color=TEAL_ACCENT, width=2, dash='dot')))
    fig.add_trace(go.Scatter(x=parent_income, y=parent_reform_ptc, mode='lines', name='ACA PTC (Reform)', line=dict(color=BLUE_PRIMARY, width=2, dash='dot')))
    fig.update_layout(
        title='Single Parent + Child: Health Benefits by Income',
        xaxis_title='Household Income',
        yaxis_title='Benefit Amount',
        xaxis=dict(tickformat='$,.0f', range=[0, 120000]),
        yaxis=dict(tickformat='$,.0f'),
        height=600,
        width=1000,
        legend=dict(orientation='h', yanchor='bottom', y=-0.2, xanchor='center', x=0.5),
    )
    fig = format_fig(fig)
    fig.write_image('hb15_parent_child.png', scale=2)
    print('  Saved hb15_parent_child.png')

    print('Done with charts!')


def main():
    generate_table_data()
    print()
    generate_charts()


if __name__ == '__main__':
    main()
