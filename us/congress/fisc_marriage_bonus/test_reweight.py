"""Tests for reweight.py on small synthetic households, with no model or microdata.

The arrays below are made up to exercise the balancing. No number here reaches
results/.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from reweight import (
    ACS_SHARE_OF_CHILDREN_IN_MARRIED_COUPLE_HOUSEHOLDS,
    ALL_RETURNS_2023,
    CHILD_CREDIT_2023,
    CHILDREN_ANY_HOUSEHOLD_2024,
    CHILDREN_MARRIED_HOUSEHOLD_2024,
    HEAD_OF_HOUSEHOLD_RETURNS_2023,
    MARRIED_OWN_CHILD_FAMILIES_BY_INCOME,
    MARRIED_RETURNS_BY_AGI,
    apply_weight_factors,
    calibrate,
    child_credit_after_tax_limit,
    child_credit_moments,
    entropy_balance,
    family_income_moments,
    filer_moments,
    household_moments,
    household_position,
    load_filing_run,
    published_targets,
    relationship_moments,
)


def small_run() -> dict[str, np.ndarray]:
    """Three households: a married couple with a child, a parent, a person alone."""
    return {
        "household.household_id": np.array([30, 10, 20]),
        "household.household_weight": np.array([2.0, 3.0, 4.0]),
        "tax_unit.tax_unit_id": np.array([7, 8, 9]),
        "tax_unit.filing_status": np.array(["SINGLE", "JOINT", "HEAD_OF_HOUSEHOLD"]),
        "tax_unit.adjusted_gross_income": np.array([10.0, 100.0, 40.0]),
        "tax_unit.income_tax": np.array([1.0, 12.0, 3.0]),
        "person.person_household_id": np.array([10, 10, 10, 20, 20, 30]),
        "person.person_tax_unit_id": np.array([8, 8, 8, 9, 9, 7]),
        "person.age": np.array([40, 38, 4, 30, 12, 70]),
        "person.is_household_head": np.array([1, 0, 0, 1, 0, 1], dtype=bool),
        "person.is_tax_unit_dependent": np.array([0, 0, 1, 0, 1, 0], dtype=bool),
        "person.person_id": np.array([101, 102, 103, 104, 105, 106]),
        # Householder, wife, own child; householder, own child; householder alone.
        "person.cps_relationship": np.array([1, 4, 5, 1, 5, 2]),
        # Married, married, never married; divorced, never married; widowed.
        "person.cps_marital_status": np.array([1, 1, 7, 5, 7, 4]),
    }


def test_moments_follow_each_household_whatever_the_row_order():
    moments = household_moments(small_run())
    # Rows run 30, 10, 20: the person alone, the married couple, the parent.
    assert moments["people"].tolist() == [1, 3, 2]
    assert moments["children_under_18"].tolist() == [0, 1, 1]
    assert moments["children_under_1"].tolist() == [0, 0, 0]
    assert moments["children_under_6"].tolist() == [0, 1, 0]
    assert moments["people_65_and_over"].tolist() == [1, 0, 0]
    assert moments["married_couple_households"].tolist() == [0, 1, 0]
    assert moments["married_couple_households_with_own_child"].tolist() == [0, 1, 0]
    assert moments["children_in_married_couple_households"].tolist() == [0, 1, 0]
    assert moments["adjusted_gross_income"].tolist() == [10, 100, 40]
    assert moments["income_tax"].tolist() == [1, 12, 3]


def test_a_married_grandparent_counts_the_child_of_a_single_parent_in_the_home():
    run = small_run()
    # The child's parent is a separate unmarried tax unit in the married couple's
    # household, as the ACS counts a child by the householder's marital status.
    run["person.person_household_id"] = np.array([10, 10, 10, 10, 10, 30])
    run["household.household_id"] = np.array([30, 10])
    run["household.household_weight"] = np.array([2.0, 3.0])
    moments = household_moments(run)
    assert moments["children_in_married_couple_households"].tolist() == [0, 2]
    # The own-child count looks only at the head's tax unit.
    assert moments["married_couple_households_with_own_child"].tolist() == [0, 1]


def test_an_own_child_must_share_the_heads_tax_unit():
    run = small_run()
    # The couple keeps unit 8 alone and the child's unit 9 lodges with them.
    run["person.person_household_id"] = np.array([10, 10, 10, 10, 10, 30])
    run["person.person_tax_unit_id"] = np.array([8, 8, 9, 9, 9, 7])
    run["person.is_household_head"] = np.array([1, 0, 0, 0, 0, 1], dtype=bool)
    run["household.household_id"] = np.array([30, 10])
    run["household.household_weight"] = np.array([2.0, 3.0])
    moments = household_moments(run)
    assert moments["married_couple_households"].tolist() == [0, 1]
    assert moments["married_couple_households_with_own_child"].tolist() == [0, 0]
    assert moments["children_in_married_couple_households"].tolist() == [0, 2]


def test_a_dependent_head_does_not_make_a_married_couple_household():
    run = small_run()
    # The 16-year-old heads the home but sits as a dependent in the parents'
    # joint unit, and the parents are not the householder.
    run["person.age"] = np.array([59, 58, 16, 30, 12, 70])
    run["person.is_household_head"] = np.array([0, 0, 1, 1, 0, 1], dtype=bool)
    moments = household_moments(run)
    assert moments["married_couple_households"].tolist() == [0, 0, 0]
    assert moments["married_couple_households_with_own_child"].tolist() == [0, 0, 0]
    assert moments["children_in_married_couple_households"].tolist() == [0, 0, 0]


def test_a_surviving_spouse_does_not_make_a_married_couple_household():
    run = small_run()
    run["tax_unit.filing_status"] = np.array(
        ["SINGLE", "SURVIVING_SPOUSE", "HEAD_OF_HOUSEHOLD"]
    )
    moments = household_moments(run)
    assert moments["married_couple_households"].tolist() == [0, 0, 0]


def test_a_one_year_old_is_not_an_infant():
    run = small_run()
    run["person.age"] = np.array([40, 38, 1, 30, 0, 70])
    assert household_moments(run)["children_under_1"].tolist() == [0, 0, 1]


def test_relationship_moments_follow_each_household_whatever_the_row_order():
    moments = relationship_moments(small_run())
    assert moments["married_couple_households"].tolist() == [0, 1, 0]
    assert moments["married_couple_households_with_own_child"].tolist() == [0, 1, 0]
    assert moments["children_in_households"].tolist() == [0, 1, 1]
    assert moments["children_in_married_couple_households"].tolist() == [0, 1, 0]


def test_a_spouse_makes_a_married_couple_household_whatever_the_filing():
    run = small_run()
    run["tax_unit.filing_status"] = np.array(["SINGLE", "SEPARATE", "SINGLE"])
    assert household_moments(run)["married_couple_households"].tolist() == [0, 0, 0]
    assert relationship_moments(run)["married_couple_households"].tolist() == [0, 1, 0]


def test_parents_who_live_with_their_child_householder_are_no_couple_household():
    run = small_run()
    # The 16-year-old is the reference person, and the couple are their parents.
    run["person.age"] = np.array([59, 58, 16, 30, 12, 70])
    run["person.cps_relationship"] = np.array([8, 8, 1, 1, 5, 2])
    moments = relationship_moments(run)
    assert moments["married_couple_households"].tolist() == [0, 0, 0]
    assert moments["children_in_households"].tolist() == [0, 0, 1]


def test_a_grandchild_counts_among_children_but_is_no_own_child():
    run = small_run()
    run["person.cps_relationship"] = np.array([1, 4, 7, 1, 5, 2])
    moments = relationship_moments(run)
    assert moments["married_couple_households"].tolist() == [0, 1, 0]
    assert moments["married_couple_households_with_own_child"].tolist() == [0, 0, 0]
    assert moments["children_in_married_couple_households"].tolist() == [0, 1, 0]


def test_a_householder_or_spouse_under_18_is_not_counted_among_children():
    run = small_run()
    run["person.age"] = np.array([17, 17, 1, 17, 12, 70])
    run["person.cps_relationship"] = np.array([1, 3, 5, 1, 5, 2])
    moments = relationship_moments(run)
    assert moments["children_in_households"].tolist() == [0, 1, 1]
    assert moments["children_in_married_couple_households"].tolist() == [0, 1, 0]


def test_an_ever_married_child_counts_among_children_but_is_no_own_child():
    run = small_run()
    # The ACS counts only never-married children as own children; 6 is separated.
    run["person.cps_marital_status"] = np.array([1, 1, 6, 5, 7, 4])
    moments = relationship_moments(run)
    assert moments["married_couple_households"].tolist() == [0, 1, 0]
    assert moments["married_couple_households_with_own_child"].tolist() == [0, 0, 0]
    assert moments["children_in_married_couple_households"].tolist() == [0, 1, 0]


def test_the_share_moment_is_zero_where_the_acs_share_holds():
    moments = relationship_moments(small_run())
    share = ACS_SHARE_OF_CHILDREN_IN_MARRIED_COUPLE_HOUSEHOLDS
    assert moments["children_in_married_couple_households_above_acs_share"] == (
        pytest.approx([0, 1 - share, -share])
    )
    # Weights that put the ACS share of these children in the married household.
    weights = np.array([1.0, share, 1 - share])
    assert moments["children_in_married_couple_households_above_acs_share"] @ (
        weights
    ) == pytest.approx(0, abs=1e-15)
    married = moments["children_in_married_couple_households"] @ weights
    children = moments["children_in_households"] @ weights
    assert married / children == pytest.approx(share)


@pytest.mark.parametrize(
    "name", ["person.cps_relationship", "person.cps_marital_status"]
)
def test_a_run_without_relationship_codes_cannot_calibrate(name):
    run = small_run()
    del run[name]
    with pytest.raises(ValueError, match="relationship.py"):
        calibrate(run)


def test_the_solve_counts_households_by_the_codes_and_returns_by_filing(
    monkeypatch,
):
    seen = {}

    def keep_every_weight(weights, moments, targets):
        seen.update(moments=moments)
        return np.ones(weights.size)

    monkeypatch.setattr("reweight.entropy_balance", keep_every_weight)
    run = with_filers(with_credits(small_run()))
    run["tax_unit.filing_status"] = np.array(["SINGLE", "SINGLE", "SINGLE"])
    result = calibrate(run, detailed=True, child_credit=True, filers=True)
    row = dict(zip(result.targets, seen["moments"]))
    assert row["married_couple_households"].tolist() == [0, 1, 0]
    # with_filers gives the couple's unit an AGI of $120,000.
    assert row["married_own_child_income_100000_to_200000"].tolist() == [0, 1, 0]
    assert row["joint_returns_with_child_credit"].tolist() == [0, 0, 0]


DATASET_SHA256 = "ab" * 32
CODE_NAMES = ("person.cps_relationship", "person.cps_marital_status")


def save_run_and_codes(work, person_ids=None, dataset_sha256=DATASET_SHA256):
    """Save small_run without its codes, then the codes as relationship.py does."""
    arrays = small_run()
    codes = {name: arrays.pop(name) for name in CODE_NAMES}
    np.savez(work / "filing_2024.npz", **arrays)
    (work / "filing_2024.json").write_text(
        json.dumps({"bundle": {"runtime_dataset_sha256": DATASET_SHA256}})
    )
    np.savez(
        work / "relationship_2024.npz",
        dataset_sha256=dataset_sha256,
        **{
            "person.person_id": (
                arrays["person.person_id"] if person_ids is None else person_ids
            )
        },
        **codes,
    )
    return codes


def test_a_run_picks_up_the_codes_saved_beside_it(tmp_path):
    arrays = small_run()
    for name in CODE_NAMES:
        arrays.pop(name)
    np.savez(tmp_path / "filing_2024.npz", **arrays)
    assert "person.cps_relationship" not in load_filing_run(tmp_path)
    codes = save_run_and_codes(tmp_path)
    run = load_filing_run(tmp_path)
    for name in CODE_NAMES:
        assert run[name].tolist() == codes[name].tolist()


def test_codes_saved_for_other_people_raise(tmp_path):
    # Swapping two people of one household and one age passes every other check.
    save_run_and_codes(tmp_path, person_ids=np.array([102, 101, 103, 104, 105, 106]))
    with pytest.raises(ValueError, match="other people"):
        load_filing_run(tmp_path)


def test_codes_from_another_dataset_raise(tmp_path):
    save_run_and_codes(tmp_path, dataset_sha256="cd" * 32)
    with pytest.raises(ValueError, match="another dataset"):
        load_filing_run(tmp_path)


def test_a_run_without_person_ids_cannot_take_codes(tmp_path):
    save_run_and_codes(tmp_path)
    with np.load(tmp_path / "filing_2024.npz") as saved:
        arrays = {
            name: saved[name] for name in saved.files if name != "person.person_id"
        }
    np.savez(tmp_path / "filing_2024.npz", **arrays)
    with pytest.raises(ValueError, match="other people"):
        load_filing_run(tmp_path)


def test_income_bands_split_married_households_with_a_child_and_no_others():
    moments = household_moments(small_run())
    bands = family_income_moments(moments)
    assert sum(bands.values()).tolist() == (
        moments["married_couple_households_with_own_child"].tolist()
    )
    assert bands["married_own_child_income_under_25000"].tolist() == [0, 1, 0]


def test_the_income_solve_swaps_the_family_total_for_its_bands():
    moments = household_moments(small_run())
    moments |= family_income_moments(moments)
    weights = np.array([2.0, 3.0, 4.0])
    targets = published_targets(moments, weights, detailed=True)
    assert "married_couple_households_with_own_child" not in targets
    assert targets["children_under_1"] == 3_617_221
    published = [item[3] for item in MARRIED_OWN_CHILD_FAMILIES_BY_INCOME]
    bands = [item[0] for item in MARRIED_OWN_CHILD_FAMILIES_BY_INCOME]
    assert [targets[f"married_own_child_income_{b}"] for b in bands] == published


def with_credits(run: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Units 7, 8 and 9 carry no credit, a credit under the limit and one above it."""
    return run | {
        "tax_unit.non_refundable_ctc": np.array([0.0, 2000.0, 2000.0]),
        "tax_unit.ctc_limiting_tax_liability": np.array([500.0, 5000.0, -50.0]),
    }


def test_the_credit_stops_at_the_tax_limit_and_never_goes_negative():
    assert child_credit_after_tax_limit(with_credits(small_run())).tolist() == [
        0,
        2000,
        0,
    ]


def test_child_credit_lines_follow_each_household_whatever_the_row_order():
    run = with_credits(small_run())
    run["tax_unit.ctc_limiting_tax_liability"] = np.array([500.0, 5000.0, 700.0])
    moments = child_credit_moments(run)
    # Rows run 30, 10, 20: the person alone, the married couple, the parent.
    assert moments["joint_returns_with_child_credit"].tolist() == [0, 1, 0]
    assert moments["joint_child_credit"].tolist() == [0, 2000, 0]
    assert moments["other_returns_with_child_credit"].tolist() == [0, 0, 1]
    assert moments["other_child_credit"].tolist() == [0, 0, 700]


def test_a_surviving_spouse_sits_on_the_joint_side_as_in_the_irs_tables():
    run = with_credits(small_run())
    run["tax_unit.filing_status"] = np.array(
        ["SINGLE", "SURVIVING_SPOUSE", "HEAD_OF_HOUSEHOLD"]
    )
    assert child_credit_moments(run)["joint_child_credit"].tolist() == [0, 2000, 0]


def test_a_separate_return_sits_on_the_married_side_of_the_credit_lines():
    run = with_credits(small_run())
    run["tax_unit.filing_status"] = np.array(["SINGLE", "SEPARATE", "SINGLE"])
    moments = child_credit_moments(run)
    assert moments["joint_returns_with_child_credit"].tolist() == [0, 1, 0]
    assert moments["joint_child_credit"].tolist() == [0, 2000, 0]
    assert moments["other_child_credit"].tolist() == [0, 0, 0]


def with_filers(run: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Unit 7 files nothing, and units 8 and 9 file on incomes the IRS bands split."""
    return run | {
        "tax_unit.tax_unit_is_filer": np.array([False, True, True]),
        "tax_unit.adjusted_gross_income": np.array([10.0, 120_000.0, 40_000.0]),
    }


def test_filer_lines_follow_each_household_and_skip_units_that_file_nothing():
    moments = filer_moments(with_filers(small_run()))
    # Rows run 30, 10, 20: the person alone, the married couple, the parent.
    assert moments["all_filers"].tolist() == [0, 1, 1]
    assert moments["head_of_household_filers"].tolist() == [0, 0, 1]
    assert moments["joint_filers_agi_100000_to_200000"].tolist() == [0, 1, 0]
    assert moments["joint_filers_agi_under_25000"].tolist() == [0, 0, 0]


def test_a_married_unit_that_files_nothing_stays_off_the_agi_lines():
    run = with_filers(small_run())
    run["tax_unit.tax_unit_is_filer"] = np.array([False, False, True])
    assert filer_moments(run)["joint_filers_agi_100000_to_200000"].tolist() == [0, 0, 0]


def test_separate_and_surviving_spouse_returns_join_the_married_agi_lines():
    run = with_filers(small_run())
    run["tax_unit.filing_status"] = np.array(["SINGLE", "SEPARATE", "SURVIVING_SPOUSE"])
    moments = filer_moments(run)
    assert moments["joint_filers_agi_100000_to_200000"].tolist() == [0, 1, 0]
    assert moments["joint_filers_agi_25000_to_50000"].tolist() == [0, 0, 1]
    assert moments["head_of_household_filers"].tolist() == [0, 0, 0]


def test_the_filer_solve_adds_the_irs_return_lines_to_the_targets():
    moments = household_moments(small_run())
    weights = np.array([2.0, 3.0, 4.0])
    targets = published_targets(moments, weights, filers=True)
    assert targets["all_filers"] == ALL_RETURNS_2023
    assert targets["head_of_household_filers"] == HEAD_OF_HOUSEHOLD_RETURNS_2023
    for label, _, _, returns in MARRIED_RETURNS_BY_AGI:
        assert targets[f"joint_filers_agi_{label}"] == returns
    assert "all_filers" not in published_targets(moments, weights)


def test_every_solve_holds_the_files_people_income_and_tax():
    moments = household_moments(small_run())
    weights = np.array([2.0, 3.0, 4.0])
    targets = published_targets(moments, weights)
    assert targets["people"] == moments["people"] @ weights
    assert targets["people_65_and_over"] == moments["people_65_and_over"] @ weights
    assert targets["adjusted_gross_income"] == (
        moments["adjusted_gross_income"] @ weights
    )
    assert targets["income_tax"] == moments["income_tax"] @ weights


def test_the_married_child_target_holds_the_acs_share_not_its_count():
    moments = household_moments(small_run())
    targets = published_targets(moments, np.array([2.0, 3.0, 4.0]))
    assert targets["children_in_married_couple_households_above_acs_share"] == 0
    assert "children_in_married_couple_households" not in targets
    assert ACS_SHARE_OF_CHILDREN_IN_MARRIED_COUPLE_HOUSEHOLDS == (
        CHILDREN_MARRIED_HOUSEHOLD_2024 / CHILDREN_ANY_HOUSEHOLD_2024
    )


def test_the_child_credit_solve_adds_the_irs_lines_to_the_targets():
    moments = household_moments(small_run())
    weights = np.array([2.0, 3.0, 4.0])
    targets = published_targets(moments, weights, child_credit=True)
    assert CHILD_CREDIT_2023.items() <= targets.items()
    assert "joint_child_credit" not in published_targets(moments, weights)


def many_households(size: int = 3000) -> dict[str, np.ndarray]:
    """Made-up households with every mix of marriage, children, age and income.

    Heads, spouses and children alone would tie the people count to the household,
    couple and child targets, so some households also hold another adult.
    """
    generator = np.random.default_rng(3)
    married = generator.random(size) < 0.5
    children = generator.integers(0, 4, size)
    elderly = generator.random(size) < 0.2
    other_adult = generator.random(size) < 0.3
    people = 1 + married + children + other_adult
    home = np.repeat(np.arange(size), people)
    head = np.concatenate([[0], np.cumsum(people)[:-1]])
    age = generator.integers(0, 18, people.sum())
    age[head] = np.where(elderly, 70, 40)
    spouses = head[married] + 1
    age[spouses] = 40
    is_head = np.zeros(people.sum(), dtype=bool)
    is_head[head] = True
    adult = is_head.copy()
    adult[spouses] = True
    last = head + people - 1
    age[last[other_adult]] = 30
    adult[last[other_adult]] = True
    code = np.full(people.sum(), 5)
    code[head] = 1
    code[spouses] = 3
    code[last[other_adult]] = 12
    marital_status = np.full(people.sum(), 7)
    marital_status[head[married]] = 1
    marital_status[spouses] = 1
    return {
        "household.household_id": np.arange(size),
        "household.household_weight": generator.uniform(1.5e4, 4.5e4, size),
        "tax_unit.tax_unit_id": np.arange(size),
        "tax_unit.filing_status": np.where(married, "JOINT", "SINGLE"),
        "tax_unit.adjusted_gross_income": generator.choice(
            [1e4, 4e4, 8e4, 1.5e5, 3e5], size
        ),
        "tax_unit.income_tax": generator.uniform(0, 1e4, size),
        "person.person_household_id": home,
        "person.person_tax_unit_id": home,
        "person.age": age,
        "person.is_household_head": is_head,
        "person.is_tax_unit_dependent": ~adult,
        "person.cps_relationship": code,
        "person.cps_marital_status": marital_status,
    }


def test_a_detailed_solve_hits_every_target_on_many_records():
    run = many_households()
    result = calibrate(run, detailed=True)
    for name, target in result.targets.items():
        if target:
            assert result.after[name] == pytest.approx(target, rel=1e-6)
    moments = relationship_moments(run)
    weights = run["household.household_weight"] * result.factors
    assert moments["children_in_married_couple_households"] @ weights / (
        moments["children_in_households"] @ weights
    ) == pytest.approx(ACS_SHARE_OF_CHILDREN_IN_MARRIED_COUPLE_HOUSEHOLDS, rel=1e-9)
    assert (result.factors > 0).all()


def test_the_fullest_solve_hands_every_target_to_the_balancing(monkeypatch):
    seen = {}

    def double_every_weight(weights, moments, targets):
        seen.update(moments=moments, targets=targets)
        return np.full(weights.size, 2.0)

    monkeypatch.setattr("reweight.entropy_balance", double_every_weight)
    run = with_filers(with_credits(small_run()))
    result = calibrate(run, detailed=True, child_credit=True, filers=True)
    assert seen["moments"].shape == (27, 3)
    assert seen["targets"].tolist() == list(result.targets.values())
    for name in result.targets:
        assert result.after[name] == 2 * result.before[name]


class FakeSimulation:
    """Holds household arrays the way apply_weight_factors reads and sets them."""

    class Values:
        def __init__(self, values: np.ndarray):
            self.values = values

    def __init__(self, ids: np.ndarray, weights: np.ndarray, sticky: bool = False):
        self.arrays = {"household_id": ids, "household_weight": weights}
        self.sticky = sticky

    def calculate(self, variable: str, period: int) -> FakeSimulation.Values:
        return self.Values(self.arrays[variable])

    def set_input(self, variable: str, period: int, values: np.ndarray) -> None:
        if not self.sticky:
            self.arrays[variable] = values


def save_factors(path, ids, factors):
    np.savez(path, household_id=np.array(ids), factor=np.array(factors))
    return path


def test_factors_multiply_the_weights_of_the_year_they_run(tmp_path):
    path = save_factors(tmp_path / "f.npz", [3, 1], [0.5, 2.0])
    sim = FakeSimulation(np.array([3, 1]), np.array([10.0, 20.0]))
    apply_weight_factors(sim, 2026, path)
    assert sim.arrays["household_weight"].tolist() == [5.0, 40.0]


def test_factors_from_another_file_raise(tmp_path):
    path = save_factors(tmp_path / "f.npz", [1, 3], [0.5, 2.0])
    sim = FakeSimulation(np.array([3, 1]), np.array([10.0, 20.0]))
    with pytest.raises(ValueError, match="another file"):
        apply_weight_factors(sim, 2026, path)


@pytest.mark.parametrize(
    ("ids", "factors", "message"),
    [
        ([3, 1], [np.nan, 2.0], "finite and positive"),
        ([3, 1], [0.0, 2.0], "finite and positive"),
        ([3, 1], [np.inf, 2.0], "finite and positive"),
        ([3, 3], [0.5, 2.0], "appears twice"),
        ([3, 1], [0.5], "differ in shape"),
    ],
)
def test_a_factor_file_that_cannot_reweight_raises(tmp_path, ids, factors, message):
    # A NaN makes every later comparison false, so it has to fail at the load.
    path = save_factors(tmp_path / "f.npz", ids, factors)
    sim = FakeSimulation(np.array([3, 1]), np.array([10.0, 20.0]))
    with pytest.raises(ValueError, match=message):
        apply_weight_factors(sim, 2026, path)


def test_a_simulation_that_keeps_its_old_weights_raises(tmp_path):
    path = save_factors(tmp_path / "f.npz", [3, 1], [0.5, 2.0])
    sim = FakeSimulation(np.array([3, 1]), np.array([10.0, 20.0]), sticky=True)
    with pytest.raises(ValueError, match="old household weights"):
        apply_weight_factors(sim, 2026, path)


def test_a_link_to_no_row_raises():
    with pytest.raises(ValueError, match="no row"):
        household_position(np.array([1, 2]), np.array([3]))


def test_balancing_hits_the_targets_and_leaves_a_met_target_alone():
    weights = np.array([1.0, 2.0, 3.0, 4.0])
    moments = np.array([[1.0, 1.0, 1.0, 1.0], [1.0, 0.0, 1.0, 0.0]])
    met = moments @ weights
    assert np.allclose(entropy_balance(weights, moments, met), 1.0)

    targets = np.array([12.0, 6.0])
    factors = entropy_balance(weights, moments, targets)
    assert np.allclose(moments @ (weights * factors), targets)
    assert (factors > 0).all()


def test_a_zero_target_is_met_relative_to_its_own_scale():
    """A share held as a zero-sum moment, with totals so large that a gap of 1e-9
    children sits below rounding."""
    generator = np.random.default_rng(5)
    weights = generator.uniform(1e6, 5e6, 20_000)
    married = generator.random(20_000) < 0.5
    children = generator.integers(0, 4, 20_000).astype(float)
    share = 0.67
    moments = np.vstack([np.ones(20_000), children * (married - share)])
    targets = np.array([weights.sum(), 0.0])
    factors = entropy_balance(weights, moments, targets)
    reweighted = weights * factors
    assert reweighted @ (children * married) / (reweighted @ children) == (
        pytest.approx(share, rel=1e-9)
    )
    assert reweighted.sum() == pytest.approx(weights.sum(), rel=1e-9)


def test_a_zero_target_is_met_at_the_final_weights_after_a_large_cut():
    """Review 12's counterexample: the starting weights shrink a billionfold, so a
    miss measured against their total would let a residual near one through."""
    weights = np.array([1e9, 2e9])
    moments = np.array([[1.0, 1.0], [1.0, -1.0]])
    reweighted = weights * entropy_balance(weights, moments, np.array([3.0, 0.0]))
    assert reweighted == pytest.approx([1.5, 1.5], rel=1e-9)
    assert abs(moments[1] @ reweighted) < 1e-9 * reweighted.sum()


def test_a_small_target_is_met_when_the_weights_shrink_to_it():
    """Review 13's counterexamples: each target sits far below its moment's total
    at the starting weights and well above rounding at the final ones."""
    weights = np.array([1e10])
    factors = entropy_balance(weights, np.array([[1.0]]), np.array([1.0]))
    assert weights * factors == pytest.approx([1.0], rel=1e-9)

    weights = np.array([1.0, 2.0, 1.0])
    moments = np.array([[1.0, 1.0, 1.0], [0.0, 0.0, 1.0], [1.0, -1.0, 0.0]])
    targets = np.array([4.0, 4.0 - 1e-6, 1e-10])
    reached = moments @ (weights * entropy_balance(weights, moments, targets))
    assert reached == pytest.approx(targets, rel=1e-9)


@pytest.mark.parametrize(
    ("weights", "target"),
    [([2.0, 1.0], 1e-12), ([1e9, 1e9], 1e-6), ([1.0, 1.0], 2.0**-25)],
)
def test_a_target_this_near_zero_must_be_zero(weights, target):
    """Each tolerance falls below the rounding of a two-record sum."""
    with pytest.raises(ValueError, match="must be zero"):
        entropy_balance(np.array(weights), np.array([[1.0, -1.0]]), np.array([target]))


def test_balancing_refuses_targets_no_positive_weights_can_reach():
    weights = np.array([1.0, 1.0])
    moments = np.array([[1.0, 1.0], [1.0, 0.0]])
    # Only the first record carries the second moment, so it cannot exceed the first.
    with pytest.raises((ValueError, np.linalg.LinAlgError)):
        entropy_balance(weights, moments, np.array([1.0, 2.0]))


@settings(max_examples=60, deadline=None)
@given(
    st.lists(st.floats(0.5, 5.0), min_size=6, max_size=30),
    st.floats(0.8, 1.25),
    st.floats(0.85, 1.15),
)
def test_any_reachable_target_is_met_with_positive_factors(raw, total, married):
    """Invariant: from any weights, a reachable target lands within tolerance."""
    weights = np.array(raw)
    married_flag = (np.arange(weights.size) % 2 == 0).astype(float)
    moments = np.vstack([np.ones_like(weights), married_flag])
    start = moments @ weights
    targets = np.array([start[0] * total, start[1] * total * married])
    factors = entropy_balance(weights, moments, targets)
    assert np.allclose(moments @ (weights * factors), targets, rtol=1e-8)
    assert (factors > 0).all()


def test_balancing_finishes_when_the_dual_stops_moving_within_rounding():
    """A minimized counterexample: the line search used to stall near the end."""
    weights = np.array([4.0, 4.0, 2.375, 1.21875, 1.5, 2.5])
    married = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
    moments = np.vstack([np.ones(6), married])
    targets = (moments @ weights) * np.array([1.046875, 1.046875 * 1.109375])
    factors = entropy_balance(weights, moments, targets)
    assert np.allclose(moments @ (weights * factors), targets, rtol=1e-8)


@settings(max_examples=30, deadline=None)
@given(st.lists(st.floats(0.5, 5.0), min_size=6, max_size=30), st.floats(0.8, 1.25))
def test_factors_stay_equal_across_records_the_targets_cannot_tell_apart(raw, total):
    """Invariant: records with identical moments keep one factor."""
    weights = np.array(raw)
    moments = np.ones((1, weights.size))
    factors = entropy_balance(weights, moments, np.array([weights.sum() * total]))
    assert np.allclose(factors, factors[0])
