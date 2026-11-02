"""Property tests for the FISC marriage bonus calculations.

Run with:
    uv run --python 3.13 --with 'policyengine[models]==6.11.1' --with pytest \
        --with hypothesis pytest us/congress/fisc_marriage_bonus/test_analysis.py -n 0

The tests in TestModelAgainstBill build household simulations and need no
microdata. They load the tax-benefit system, which takes about a minute.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra import numpy as hnp

from analysis import (
    FISC_POLICY,
    NEGATIVE_INCOME_GROUP,
    SCENARIOS,
    bonus_lost_to_limits,
    closed_form_bonus,
    closed_form_credit,
    concentration_coefficient,
    decile_table,
    group_shares,
    stepped_credit,
    uncapped_credit,
    weighted_decile,
    weighted_gini,
)

SIZE = st.integers(min_value=20, max_value=200)


def floats(low, high):
    return st.floats(low, high, allow_nan=False, allow_infinity=False, width=64)


@st.composite
def households(draw):
    n = draw(SIZE)
    return {
        "income": draw(hnp.arrays(float, n, elements=floats(-50_000, 2_000_000))),
        "weight": draw(hnp.arrays(float, n, elements=floats(1, 5_000))),
        "people": draw(hnp.arrays(int, n, elements=st.integers(1, 8))),
        "amount": draw(hnp.arrays(float, n, elements=floats(0, 30_000))),
    }


class TestClosedFormBonus:
    @given(
        base=floats(0, 40_000),
        joint=st.booleans(),
        agi=floats(-100_000, 1_000_000),
    )
    def test_bonus_stays_between_zero_and_its_statutory_rate(self, base, joint, agi):
        bonus = float(closed_form_bonus(base, joint, agi))
        assert -1e-9 <= bonus <= 0.2 * base + 1e-9

    @given(base=floats(0, 40_000), agi=floats(-100_000, 1_000_000))
    def test_unmarried_units_receive_no_bonus(self, base, agi):
        assert float(closed_form_bonus(base, False, agi)) == 0

    @given(base=floats(0, 40_000), joint=st.booleans(), agi=floats(0, 1_000_000))
    def test_zero_rate_produces_no_bonus(self, base, joint, agi):
        assert float(closed_form_bonus(base, joint, agi, bonus_rate=0)) == 0

    @given(base=floats(0, 40_000), joint=st.booleans(), agi=floats(-100_000, 1_000_000))
    def test_credit_never_exceeds_agi_floored_at_zero(self, base, joint, agi):
        assert float(closed_form_credit(base, joint, agi)) <= max(agi, 0) + 1e-9

    @given(
        base=floats(0, 40_000),
        low=floats(250_000, 900_000),
        step=floats(0, 100_000),
    )
    def test_credit_falls_with_income_in_the_phase_out(self, base, low, step):
        assert float(closed_form_credit(base, True, low + step)) <= float(
            closed_form_credit(base, True, low)
        )


class TestSteppedCredit:
    def test_the_bill_steps_once_per_whole_thousand(self):
        base = np.array([8_000.0])
        just_below = stepped_credit(base, True, 250_999.0, bonus_rate=0)
        at_the_step = stepped_credit(base, True, 251_000.0, bonus_rate=0)
        assert just_below == pytest.approx(8_000)
        assert at_the_step == pytest.approx(8_000 - 12 * 16.67)

    @given(
        base=floats(0, 40_000),
        joint=st.booleans(),
        agi=floats(-100_000, 1_000_000),
    )
    def test_steps_stay_within_a_step_of_the_smooth_model(self, base, joint, agi):
        gap = float(stepped_credit(base, joint, agi)) - float(
            closed_form_credit(base, joint, agi)
        )
        tolerance = 200.04 + 0.04 * max(agi, 0) / 1_000
        assert abs(gap) <= tolerance

    @given(base=floats(0, 40_000), joint=st.booleans(), agi=floats(0, 1_000_000))
    def test_the_cap_applies_to_the_stepped_credit(self, base, joint, agi):
        assert float(stepped_credit(base, joint, agi)) <= agi + 1e-9


class TestUncappedCredit:
    @given(base=floats(1, 40_000), joint=st.booleans(), agi=floats(-100_000, 0))
    def test_zero_or_negative_agi_keeps_the_payment(self, base, joint, agi):
        assert float(uncapped_credit(base, joint, agi)) >= base
        assert float(closed_form_credit(base, joint, agi)) == 0


class TestBonusLostToLimits:
    @given(
        base=floats(0, 40_000),
        joint=st.booleans(),
        agi=floats(-100_000, 1_000_000),
    )
    def test_parts_sum_to_the_statutory_bonus(self, base, joint, agi):
        to_phase_out, to_cap = bonus_lost_to_limits(base, joint, agi)
        paid = closed_form_bonus(base, joint, agi)
        statutory = 0.2 * base * joint
        assert float(to_phase_out + to_cap + paid) == pytest.approx(statutory)
        assert float(to_phase_out) >= -1e-9

    @given(base=floats(0, 40_000), agi=floats(0, 250_000))
    def test_no_joint_filer_under_the_threshold_loses_to_the_phase_out(self, base, agi):
        to_phase_out, _ = bonus_lost_to_limits(base, True, agi)
        assert float(to_phase_out) == pytest.approx(0, abs=1e-6)

    @given(base=floats(0, 40_000), agi=floats(100_000, 1_000_000))
    def test_the_cap_takes_nothing_once_agi_covers_the_credit(self, base, agi):
        _, to_cap = bonus_lost_to_limits(base, True, agi)
        if agi >= 1.2 * base:
            assert float(to_cap) == pytest.approx(0, abs=1e-6)


class TestDecileTable:
    # Host load can push one example past Hypothesis's 200 ms default.
    @settings(deadline=None)
    @given(households())
    def test_rows_sum_to_the_aggregate(self, hh):
        groups = weighted_decile(hh["income"], hh["weight"], hh["people"])
        table = decile_table(groups, hh["amount"], hh["income"], hh["weight"])
        aggregate = (hh["amount"] * hh["weight"]).sum()
        assert table.dollars.sum() == pytest.approx(aggregate, rel=1e-9, abs=1e-6)
        assert table.households.sum() == pytest.approx(hh["weight"].sum(), rel=1e-9)

    @settings(deadline=None)
    @given(households())
    def test_shares_sum_to_one_when_any_dollars_flow(self, hh):
        groups = weighted_decile(hh["income"], hh["weight"], hh["people"])
        table = decile_table(groups, hh["amount"], hh["income"], hh["weight"])
        if table.dollars.sum() > 0:
            assert table.share_of_total.sum() == pytest.approx(1)

    @settings(deadline=None)
    @given(households())
    def test_receipt_shares_are_proportions(self, hh):
        groups = weighted_decile(hh["income"], hh["weight"], hh["people"])
        table = decile_table(groups, hh["amount"], hh["income"], hh["weight"])
        assert table.share_of_households_receiving.between(0, 1).all()

    @settings(deadline=None)
    @given(households())
    def test_groups_are_ordered_by_income(self, hh):
        groups = weighted_decile(hh["income"], hh["weight"], hh["people"])
        ranked = groups != NEGATIVE_INCOME_GROUP
        order = np.argsort(hh["income"][ranked], kind="stable")
        assert (np.diff(groups[ranked][order]) >= 0).all()

    @settings(deadline=None)
    @given(households())
    def test_negative_incomes_take_their_own_group(self, hh):
        groups = weighted_decile(hh["income"], hh["weight"], hh["people"])
        assert ((groups == NEGATIVE_INCOME_GROUP) == (hh["income"] < 0)).all()

    def test_group_shares_cover_the_named_deciles(self):
        groups = np.arange(1, 11)
        amount = np.ones(10)
        table = decile_table(groups, amount, np.full(10, 100.0), np.ones(10))
        assert group_shares(table) == pytest.approx(
            {"bottom_five_deciles": 0.5, "top_three_deciles": 0.3}
        )


class TestConcentrationCoefficient:
    @settings(deadline=None)
    @given(households())
    def test_equal_amount_per_unit_gives_zero(self, hh):
        amount = np.full(len(hh["income"]), 100.0)
        coefficient = concentration_coefficient(amount, hh["income"], hh["weight"])
        assert coefficient == pytest.approx(0, abs=1e-9)

    @given(households(), floats(0.1, 1_000))
    def test_scaling_the_amount_changes_nothing(self, hh, scale):
        amount = hh["amount"] + 1
        args = (hh["income"], hh["weight"])
        assert concentration_coefficient(scale * amount, *args) == pytest.approx(
            concentration_coefficient(amount, *args), rel=1e-9
        )

    @settings(deadline=None)
    @given(households(), st.randoms(use_true_random=False))
    def test_the_order_of_the_rows_changes_nothing(self, hh, generator):
        order = list(range(len(hh["income"])))
        generator.shuffle(order)
        amount = hh["amount"] + 1
        assert concentration_coefficient(
            amount[order], hh["income"][order], hh["weight"][order]
        ) == pytest.approx(
            concentration_coefficient(amount, hh["income"], hh["weight"]), abs=1e-9
        )

    def test_units_tied_on_income_share_a_rank(self):
        coefficient = concentration_coefficient(
            np.array([0.0, 100.0]), np.ones(2), np.ones(2)
        )
        assert coefficient == pytest.approx(0)

    def test_amounts_at_the_top_score_near_one(self):
        n = 1_000
        amount = np.zeros(n)
        amount[-1] = 1
        coefficient = concentration_coefficient(amount, np.arange(n), np.ones(n))
        assert coefficient == pytest.approx(1, abs=0.002)

    def test_amounts_at_the_bottom_score_near_minus_one(self):
        n = 1_000
        amount = np.zeros(n)
        amount[0] = 1
        coefficient = concentration_coefficient(amount, np.arange(n), np.ones(n))
        assert coefficient == pytest.approx(-1, abs=0.002)


class TestWeightedGini:
    @settings(deadline=None)
    @given(households())
    def test_agrees_with_microdf(self, hh):
        from microdf import MicroSeries

        income = np.abs(hh["income"])
        assert weighted_gini(income, hh["weight"]) == pytest.approx(
            MicroSeries(income, weights=hh["weight"]).gini(), abs=1e-9
        )

    @settings(deadline=None)
    @given(households())
    def test_stays_between_zero_and_one_without_negatives(self, hh):
        gini = weighted_gini(np.abs(hh["income"]), hh["weight"])
        assert -1e-9 <= gini <= 1 + 1e-9

    def test_equal_incomes_give_zero(self):
        gini = weighted_gini(np.full(5, 40_000.0), np.arange(1.0, 6.0))
        assert gini == pytest.approx(0)


class TestScenarios:
    def test_every_variant_keeps_the_reform_on(self):
        for name, policy in SCENARIOS.items():
            if name.startswith("fisc"):
                assert FISC_POLICY.items() <= policy.items()

    def test_the_full_no_cap_run_starts_from_the_reform(self):
        assert SCENARIOS["fisc_no_agi_cap"] == FISC_POLICY

    def test_baseline_applies_nothing(self):
        assert SCENARIOS["baseline"] == {}

    def test_march_2025_baseline_leaves_the_reform_off(self):
        assert FISC_POLICY.keys().isdisjoint(SCENARIOS["baseline_march_2025_ctc"])


def household_income_tax(reform, *, joint, child_age, income):
    """Federal income tax of a single-earner family in a state with no income tax.

    The FISC credit exists only once the reform registers it, so the household
    calculator cannot return it by name. It reaches income tax one for one as a
    refundable credit, and the comparison below reads it there.
    """
    import policyengine as pe

    people = [{"age": 35, "employment_income": income}]
    if joint:
        people.append({"age": 35})
    people.append({"age": child_age})
    result = pe.us.calculate_household(
        people=people,
        household={"state_code": "TX", "county_fips": "48201"},
        year=2026,
        reform=reform,
        extra_variables=["filing_status", "adjusted_gross_income"],
    )
    assert (str(result.tax_unit.filing_status) == "JOINT") is joint
    assert float(result.tax_unit.adjusted_gross_income) == pytest.approx(income)
    return float(result.tax_unit.income_tax)


class TestModelAgainstBill:
    """Differential check: the model's bonus against its annual reading of the bill.

    The off-grid incomes sit between the bill's $1,000 steps, where the model's
    smooth phase-out and the closed form still agree.
    """

    @pytest.mark.parametrize("joint", [True, False])
    @pytest.mark.parametrize("child_age", [0, 3, 10])
    @pytest.mark.parametrize(
        "income",
        [1_000, 5_000, 60_000, 255_000, 255_500, 262_000, 262_750, 310_000, 700_000],
    )
    def test_bonus_matches_the_closed_form(self, joint, child_age, income):
        base = {0: 8_000, 3: 4_800, 10: 3_000}[child_age]
        kwargs = {"joint": joint, "child_age": child_age, "income": income}
        modelled = household_income_tax(
            SCENARIOS["fisc_no_bonus"], **kwargs
        ) - household_income_tax(SCENARIOS["fisc"], **kwargs)
        assert modelled == pytest.approx(
            float(closed_form_bonus(base, joint, income)), abs=1.0
        )
