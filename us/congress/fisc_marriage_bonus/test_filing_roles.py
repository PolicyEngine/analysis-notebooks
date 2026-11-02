"""Tests for filing_roles.py on a few made-up tax units, with no model or microdata.

The arrays below are made up to exercise the comparison. No number here reaches
results/.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from filing_roles import filing_roles, model_roles


def units() -> pd.DataFrame:
    """A joint couple, a head of household the model files jointly, and a joint
    return the model splits."""
    return pd.DataFrame(
        {
            "tax_unit_id": [1, 2, 3],
            "filing_status_input": ["JOINT", "HEAD_OF_HOUSEHOLD", "JOINT"],
        }
    )


def people() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "person_tax_unit_id": [1, 1, 2, 2, 2, 3, 3],
            # The file's third couple has separated, so the model files them apart.
            "is_separated": [False] * 5 + [True, False],
            "A_MARITL": [1, 1, 5, 7, 7, 1, 1],
            "age": [40.0, 38.0, 45.0, 22.0, 6.0, 50.0, 49.0],
        }
    )


def runs() -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    fisc = {
        "tax_unit.tax_unit_id": np.array([1, 2, 3]),
        "tax_unit.joint": np.array([True, True, False]),
        "tax_unit.tax_unit_weight": np.array([2.0, 3.0, 4.0]),
        "tax_unit.family_income_supplement_credit": np.array([600.0, 1200.0, 500.0]),
        "tax_unit.family_income_supplement_credit_base_amount": np.array(
            [500.0, 1000.0, 500.0]
        ),
        "tax_unit.adjusted_gross_income": np.array([50_000.0, 40_000.0, 60_000.0]),
        "tax_unit.age_head": np.array([40.0, 45.0, 50.0]),
        "tax_unit.age_spouse": np.array([38.0, 22.0, 0.0]),
    }
    no_bonus = fisc | {
        "tax_unit.family_income_supplement_credit": np.array([500.0, 1000.0, 500.0])
    }
    return fisc, no_bonus


def test_a_head_of_household_the_model_files_jointly_counts_once():
    lines = filing_roles(units(), people(), *runs())
    assert lines["joint_in_model_not_in_file_records"] == 1
    assert lines["joint_in_model_not_in_file_weight"] == 3
    assert lines["joint_in_model_not_in_file_bonus"] == 3 * 200
    # The model's spouse is the 22-year-old, whom the survey lists as never married.
    assert lines["their_spouse_never_married_records"] == 1
    assert lines["their_spouse_weighted_median_age"] == 22


def test_a_joint_return_the_model_splits_counts_the_other_way():
    lines = filing_roles(units(), people(), *runs())
    assert lines["joint_in_file_not_in_model_records"] == 1
    assert lines["joint_in_file_not_in_model_weight"] == 4
    assert lines["joint_in_file_not_in_model_bonus_if_joint"] == pytest.approx(4 * 100)
    assert lines["net_bonus_the_model_adds"] == pytest.approx(600 - 400)


def test_units_in_another_order_raise():
    with pytest.raises(ValueError, match="another order"):
        filing_roles(units().iloc[::-1], people(), *runs())


@pytest.mark.parametrize(
    ("role", "ages"),
    [
        ("spouse", [38.0, 45.0, 0.0]),
        # An ordinary joint unit, which the model and the file both file jointly.
        ("spouse", [999.0, 22.0, 0.0]),
        ("head", [40.0, 22.0, 50.0]),
    ],
)
def test_every_head_and_spouse_must_match_the_runs_ages(role, ages):
    fisc, no_bonus = runs()
    fisc[f"tax_unit.age_{role}"] = np.array(ages)
    with pytest.raises(ValueError, match=f"the {role}s picked here differ"):
        filing_roles(units(), people(), fisc, no_bonus)


def test_the_model_takes_the_oldest_adults_and_breaks_ties_by_listing():
    table = pd.DataFrame(
        {
            "person_tax_unit_id": [5, 5, 5, 6, 6],
            "is_separated": [False] * 5,
            "age": [30.0, 17.0, 30.0, 25.0, 60.0],
        }
    )
    head, spouse = model_roles(table)
    assert head.tolist() == [True, False, False, False, True]
    assert spouse.tolist() == [False, False, True, True, False]


def test_a_separated_member_leaves_the_unit_without_a_spouse():
    table = pd.DataFrame(
        {
            "person_tax_unit_id": [5, 5, 5],
            "is_separated": [False, True, False],
            "age": [50.0, 45.0, 10.0],
        }
    )
    head, spouse = model_roles(table)
    assert head.tolist() == [True, False, False]
    assert not spouse.any()


def test_a_unit_of_children_has_no_head():
    table = pd.DataFrame(
        {
            "person_tax_unit_id": [5, 5],
            "is_separated": [False, False],
            "age": [17.0, 9.0],
        }
    )
    head, spouse = model_roles(table)
    assert not head.any() and not spouse.any()
