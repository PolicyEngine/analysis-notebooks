"""Tests for benchmarks.py on small synthetic households, with no model or microdata.

The arrays below are made up to exercise the arithmetic. No number here reaches
results/.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pytest
from benchmarks import (
    BENCHMARKS,
    MARRIED_OWN_CHILD_FAMILIES_BY_INCOME,
    MARRIED_RETURNS_BY_AGI,
    benchmark_table,
    load_file,
    measures,
    with_weight_factors,
)
from hypothesis import given, settings
from hypothesis import strategies as st


def small_run() -> dict[str, np.ndarray]:
    """Three units in two homes: a couple with a child, a lodger, a single parent."""
    return {
        "household.household_id": np.array([20, 10]),
        "household.household_weight": np.array([3.0, 2.0]),
        "tax_unit.tax_unit_id": np.array([1, 2, 3]),
        "tax_unit.tax_unit_weight": np.array([2.0, 2.0, 3.0]),
        "tax_unit.filing_status": np.array(["JOINT", "SINGLE", "HEAD_OF_HOUSEHOLD"]),
        "tax_unit.tax_unit_is_filer": np.array([True, False, True]),
        "tax_unit.adjusted_gross_income": np.array([120_000.0, 9_000.0, 30_000.0]),
        "tax_unit.non_refundable_ctc": np.array([2_000.0, 0.0, 2_000.0]),
        "tax_unit.ctc_limiting_tax_liability": np.array([9_000.0, 0.0, 500.0]),
        "person.person_tax_unit_id": np.array([1, 1, 1, 2, 3, 3]),
        "person.person_household_id": np.array([10, 10, 10, 10, 20, 20]),
        "person.age": np.array([40, 39, 6, 25, 33, 7]),
        "person.is_household_head": np.array([1, 0, 0, 0, 1, 0], dtype=bool),
        "person.is_tax_unit_dependent": np.array([0, 0, 1, 0, 0, 1], dtype=bool),
        "tax_unit.income_tax": np.array([9_000.0, 0.0, 500.0]),
        # Householder, wife, own child, lodger; householder, own child.
        "person.cps_relationship": np.array([1, 4, 5, 14, 1, 5]),
    }


def test_counts_at_each_entity_weight():
    result = measures(small_run())
    assert result["children_under_18"] == 5
    assert result["households"] == 5
    assert result["married_couple_households"] == 2
    assert result["married_couple_households_with_own_child"] == 2
    assert result["children_in_married_couple_households"] == 2
    assert result["share_of_children_in_married_couple_households"] == 2 / 5
    assert result["children_in_married_tax_units"] == 2
    assert result["joint_filers"] == 2
    assert result["all_filers"] == 5
    assert result["head_of_household_filers"] == 3


def test_infants_count_at_the_unit_weight_and_split_by_marriage():
    run = small_run()
    # One infant in the couple's unit and one in the head of household's.
    run["person.age"] = np.array([40, 39, 0, 25, 33, 0])
    result = measures(run)
    assert result["children_under_1"] == 5
    assert result["share_of_infants_in_married_tax_units"] == 2 / 5


def test_a_one_year_old_is_not_an_infant():
    run = small_run()
    run["person.age"] = np.array([40, 39, 1, 25, 33, 0])
    result = measures(run)
    assert result["children_under_1"] == 3
    assert result["share_of_infants_in_married_tax_units"] == 0


def test_the_credit_stops_at_the_tax_liability():
    result = measures(small_run())
    assert result["joint_child_credit"] == 4_000
    # The head of household owes $500 of tax, so $1,500 of the $2,000 goes.
    assert result["other_child_credit"] == 1_500
    assert result["other_returns_with_child_credit"] == 3


def test_a_negative_liability_leaves_no_credit():
    run = small_run()
    run["tax_unit.ctc_limiting_tax_liability"] = np.array([-5.0, 0.0, -1.0])
    result = measures(run)
    assert result["joint_child_credit"] == 0
    assert result["joint_returns_with_child_credit"] == 0


def test_surviving_spouses_sit_in_the_joint_column_but_not_among_married_units():
    run = small_run()
    run["tax_unit.filing_status"] = np.array(["JOINT", "SINGLE", "SURVIVING_SPOUSE"])
    result = measures(run)
    assert result["joint_filers"] == 5
    assert result["married_tax_units"] == 2


def test_separate_returns_sit_on_the_married_side_of_the_irs_lines():
    run = small_run()
    run["tax_unit.filing_status"] = np.array(["JOINT", "SINGLE", "SEPARATE"])
    result = measures(run)
    assert result["joint_filers"] == 5
    assert result["married_tax_units"] == 2
    assert result["joint_child_credit"] == 5_500
    assert result["other_child_credit"] == 0
    assert result["joint_returns_with_child_credit"] == 5
    assert result["other_returns_with_child_credit"] == 0
    assert result["joint_filers_agi_25000_to_50000"] == 3


def test_a_joint_unit_that_files_nothing_stays_off_the_return_rows():
    run = small_run()
    run["tax_unit.tax_unit_is_filer"] = np.array([False, False, True])
    result = measures(run)
    assert result["joint_filers"] == 0
    assert result["joint_filers_agi_100000_to_200000"] == 0
    assert result["all_filers"] == 3


def test_the_advance_rows_pair_separate_with_joint_and_widowers_with_the_rest():
    run = small_run()
    run["tax_unit.filing_status"] = np.array(["SEPARATE", "SINGLE", "SURVIVING_SPOUSE"])
    result = measures(run)
    # Two children in the separate unit and three with the surviving spouse.
    assert result["share_of_advance_children_joint"] == 2 / 5
    assert result["children_outside_joint_units"] == 3


def test_the_advance_share_leaves_out_units_past_the_phase_out():
    run = small_run()
    run["tax_unit.adjusted_gross_income"] = np.array([500_000.0, 9_000.0, 30_000.0])
    # The joint unit runs past $400,000 plus $40,000 for its one child.
    assert measures(run)["share_of_advance_children_joint"] == 0


def test_a_surviving_spouse_takes_the_200000_advance_threshold():
    run = small_run()
    run["tax_unit.filing_status"] = np.array(["SURVIVING_SPOUSE", "SINGLE", "JOINT"])
    # $300,000 clears the joint threshold and passes the one for everyone else.
    run["tax_unit.adjusted_gross_income"] = np.array([300_000.0, 9_000.0, 300_000.0])
    # The surviving spouse's child drops out of the advance payments, so every
    # child left in them sits in the joint unit.
    assert measures(run)["share_of_advance_children_joint"] == 1


def test_income_bands_cover_every_filer_once():
    result = measures(small_run())
    bands = [f"joint_filers_agi_{item[0]}" for item in MARRIED_RETURNS_BY_AGI]
    assert sum(result[name] for name in bands) == result["joint_filers"]
    assert MARRIED_RETURNS_BY_AGI[0][1] == -np.inf
    assert MARRIED_RETURNS_BY_AGI[-1][2] == np.inf
    for low, high in pairwise(MARRIED_RETURNS_BY_AGI):
        assert low[2] == high[1]


def test_the_published_bands_add_to_the_published_total():
    bands = sum(item[3] for item in MARRIED_RETURNS_BY_AGI)
    # Table 1.2 rounds each row of its columns, so the sum can miss by one or two.
    assert abs(bands - (54_568_939 + 4_139_858)) <= 2


def test_the_published_family_bands_add_to_the_published_total():
    assert sum(item[3] for item in MARRIED_OWN_CHILD_FAMILIES_BY_INCOME) == 22_978_636


def test_family_income_bands_hold_each_married_household_with_a_child_once():
    result = measures(small_run())
    bands = [
        f"married_own_child_income_{item[0]}"
        for item in MARRIED_OWN_CHILD_FAMILIES_BY_INCOME
    ]
    assert (
        sum(result[name] for name in bands)
        == result["married_couple_households_with_own_child"]
    )
    # The couple's $120,000 and the lodger's $9,000 share one household.
    assert result["married_own_child_income_100000_to_200000"] == 2


def test_the_relationship_rows_read_the_survey_codes():
    run = small_run()
    # The model files the couple separately, and the survey still shows a wife.
    run["tax_unit.filing_status"] = np.array(["SEPARATE", "SINGLE", "SINGLE"])
    result = measures(run)
    assert result["married_couple_households"] == 0
    assert result["married_couple_households_by_relationship"] == 2
    assert result["married_couple_households_with_own_child_by_relationship"] == 2
    assert result["children_in_married_couple_households_by_relationship"] == 2
    assert result[
        "share_of_children_in_married_couple_households_by_relationship"
    ] == pytest.approx(2 / 5)
    # The couple's unit and the lodger's add to $129,000 of household AGI.
    assert result["married_own_child_income_100000_to_200000_by_relationship"] == 2
    assert result["married_own_child_income_under_25000_by_relationship"] == 0


def test_a_file_without_codes_leaves_the_relationship_rows_blank():
    plain = small_run()
    del plain["person.cps_relationship"]
    table = benchmark_table({"plain": plain, "coded": small_run()})
    rows = table[table["measure"].str.endswith("_by_relationship")]
    assert len(rows) == 4 + len(MARRIED_OWN_CHILD_FAMILIES_BY_INCOME)
    assert rows["plain"].isna().all()
    assert rows["coded"].notna().all()
    others = table[~table["measure"].str.endswith("_by_relationship")]
    assert others["plain"].equals(others["coded"])


def test_every_benchmark_names_a_measure_the_run_produces():
    produced = measures(small_run())
    assert {item.measure for item in BENCHMARKS} <= set(produced)


def test_the_table_lines_up_published_figures_with_each_file():
    table = benchmark_table({"one": small_run(), "two": small_run()})
    row = table.set_index("measure").loc["children_under_18"]
    assert row["published"] == 72_548_879
    assert row["one"] == row["two"] == 5


def test_household_factors_reach_the_tax_units_inside_each_household():
    run = small_run()
    # Rows hold households 20 and 10, so the factor of 3 falls on the couple's home.
    after = with_weight_factors(run, np.array([1.0, 3.0]))
    assert after["household.household_weight"].tolist() == [3, 6]
    assert after["tax_unit.tax_unit_weight"].tolist() == [6, 6, 3]


def test_a_file_spec_can_carry_factors(tmp_path):
    arrays = small_run()
    codes = arrays.pop("person.cps_relationship")
    np.savez(tmp_path / "filing_2024.npz", **arrays)
    np.savez(
        tmp_path / "relationship_2024.npz",
        **{
            "person.person_household_id": arrays["person.person_household_id"],
            "person.cps_relationship": codes,
        },
    )
    np.savez(
        tmp_path / "f.npz",
        household_id=arrays["household.household_id"],
        factor=np.array([2.0, 2.0]),
    )
    name, run = load_file(f"doubled={tmp_path},{tmp_path / 'f.npz'}")
    assert name == "doubled"
    assert measures(run)["households"] == 2 * measures(arrays)["households"]
    assert run["person.cps_relationship"].tolist() == codes.tolist()
    assert load_file(f"plain={tmp_path}")[1]["household.household_weight"].sum() == 5


def test_factors_from_another_file_raise(tmp_path):
    arrays = small_run()
    np.savez(tmp_path / "filing_2024.npz", **arrays)
    np.savez(
        tmp_path / "f.npz",
        household_id=arrays["household.household_id"][::-1],
        factor=np.array([1.0, 3.0]),
    )
    with pytest.raises(ValueError, match="another file"):
        load_file(f"foreign={tmp_path},{tmp_path / 'f.npz'}")


def test_a_filing_status_outside_the_known_names_raises():
    run = small_run()
    run["tax_unit.filing_status"] = np.array(["0", "1", "2"])
    with pytest.raises(ValueError, match="unknown filing status"):
        measures(run)


def test_a_child_link_to_no_unit_raises():
    run = small_run()
    run["person.person_tax_unit_id"] = np.array([1, 1, 1, 2, 3, 9])
    with pytest.raises(ValueError, match="no row"):
        measures(run)


@settings(max_examples=60, deadline=None)
@given(st.lists(st.floats(0.5, 500.0), min_size=3, max_size=3))
def test_children_split_exactly_across_status_at_any_weights(raw):
    """Invariant: children in joint units and in the other columns add to all."""
    run = small_run()
    run["tax_unit.tax_unit_weight"] = np.array(raw)
    result = measures(run)
    assert result["children_in_married_tax_units"] + result[
        "children_outside_joint_units"
    ] == pytest.approx(result["children_under_18"])


@settings(max_examples=60, deadline=None)
@given(st.floats(0.01, 100.0))
def test_every_count_scales_with_the_weights_and_every_share_stays(scale):
    """Invariant: doubling weights doubles counts and leaves shares alone."""
    run = small_run()
    run["person.age"] = np.array([40, 39, 0, 25, 33, 7])
    base = measures(run)
    run["tax_unit.tax_unit_weight"] = run["tax_unit.tax_unit_weight"] * scale
    run["household.household_weight"] = run["household.household_weight"] * scale
    scaled = measures(run)
    for name, value in base.items():
        expected = value if name.startswith("share") else value * scale
        assert scaled[name] == pytest.approx(expected)
