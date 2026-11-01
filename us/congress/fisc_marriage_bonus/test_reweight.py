"""Tests for reweight.py on small synthetic households, with no model or microdata.

The arrays below are made up to exercise the balancing. No number here reaches
results/.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from reweight import (
    apply_weight_factors,
    entropy_balance,
    household_moments,
    household_position,
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
    }


def test_moments_follow_each_household_whatever_the_row_order():
    moments = household_moments(small_run())
    # Rows run 30, 10, 20: the person alone, the married couple, the parent.
    assert moments["people"].tolist() == [1, 3, 2]
    assert moments["children_under_18"].tolist() == [0, 1, 1]
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
