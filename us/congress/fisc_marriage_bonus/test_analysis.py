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
    closed_form_bonus,
    closed_form_credit,
    concentration_coefficient,
    decile_table,
    group_shares,
    weighted_decile,
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


class TestDecileTable:
    @given(households())
    def test_rows_sum_to_the_aggregate(self, hh):
        groups = weighted_decile(hh["income"], hh["weight"], hh["people"])
        table = decile_table(groups, hh["amount"], hh["income"], hh["weight"])
        aggregate = (hh["amount"] * hh["weight"]).sum()
        assert table.dollars.sum() == pytest.approx(aggregate, rel=1e-9, abs=1e-6)
        assert table.households.sum() == pytest.approx(hh["weight"].sum(), rel=1e-9)

    @given(households())
    def test_shares_sum_to_one_when_any_dollars_flow(self, hh):
        groups = weighted_decile(hh["income"], hh["weight"], hh["people"])
        table = decile_table(groups, hh["amount"], hh["income"], hh["weight"])
        if table.dollars.sum() > 0:
            assert table.share_of_total.sum() == pytest.approx(1)

    @given(households())
    def test_receipt_shares_are_proportions(self, hh):
        groups = weighted_decile(hh["income"], hh["weight"], hh["people"])
        table = decile_table(groups, hh["amount"], hh["income"], hh["weight"])
        assert table.share_of_households_receiving.between(0, 1).all()

    @given(households())
    def test_groups_are_ordered_by_income(self, hh):
        groups = weighted_decile(hh["income"], hh["weight"], hh["people"])
        ranked = groups != NEGATIVE_INCOME_GROUP
        order = np.argsort(hh["income"][ranked], kind="stable")
        assert (np.diff(groups[ranked][order]) >= 0).all()

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
    def test_equal_amount_per_person_gives_zero(self, hh):
        amount = hh["people"] * 100.0
        coefficient = concentration_coefficient(
            amount, hh["income"], hh["weight"], hh["people"]
        )
        assert coefficient == pytest.approx(0, abs=1e-9)

    @given(households(), floats(0.1, 1_000))
    def test_scaling_the_amount_changes_nothing(self, hh, scale):
        amount = hh["amount"] + 1
        args = (hh["income"], hh["weight"], hh["people"])
        assert concentration_coefficient(scale * amount, *args) == pytest.approx(
            concentration_coefficient(amount, *args), rel=1e-9
        )

    def test_amounts_at_the_top_score_near_one(self):
        n = 1_000
        amount = np.zeros(n)
        amount[-1] = 1
        coefficient = concentration_coefficient(
            amount, np.arange(n), np.ones(n), np.ones(n)
        )
        assert coefficient == pytest.approx(1, abs=0.002)

    def test_amounts_at_the_bottom_score_near_minus_one(self):
        n = 1_000
        amount = np.zeros(n)
        amount[0] = 1
        coefficient = concentration_coefficient(
            amount, np.arange(n), np.ones(n), np.ones(n)
        )
        assert coefficient == pytest.approx(-1, abs=0.002)


class TestScenarios:
    def test_every_variant_keeps_the_reform_on(self):
        for name, policy in SCENARIOS.items():
            if name != "baseline":
                assert FISC_POLICY.items() <= policy.items()

    def test_baseline_applies_nothing(self):
        assert SCENARIOS["baseline"] == {}


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
    """Differential check: the model's bonus against the bill's closed form."""

    @pytest.mark.parametrize("joint", [True, False])
    @pytest.mark.parametrize("child_age", [0, 3, 10])
    @pytest.mark.parametrize(
        "income", [1_000, 5_000, 60_000, 255_000, 262_000, 310_000, 700_000]
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
