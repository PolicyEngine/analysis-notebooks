"""Tests for relationship.py on a small made-up person table, with no microdata.

The arrays below are made up to exercise the checks. No number here reaches
results/.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from relationship import relationship_codes


def people() -> pd.DataFrame:
    """A couple with a child, and a person alone, as the dataset lists them."""
    return pd.DataFrame(
        {
            "person_id": [1, 2, 3, 4],
            "person_household_id": [10, 10, 10, 20],
            "age": [40.0, 38.0, 4.0, 70.0],
            "A_EXPRRP": [1, 4, 5, 2],
            "A_MARITL": [1, 1, 7, 4],
        }
    )


def run() -> dict[str, np.ndarray]:
    return {
        "person.person_id": np.array([1, 2, 3, 4]),
        "person.person_household_id": np.array([10, 10, 10, 20]),
        "person.age": np.array([40, 38, 4, 70], dtype=np.float32),
    }


def test_the_codes_follow_the_runs_people():
    codes = relationship_codes(people(), run())
    assert codes["person.cps_relationship"].tolist() == [1, 4, 5, 2]
    assert codes["person.cps_marital_status"].tolist() == [1, 1, 7, 4]
    assert codes["person.person_id"].tolist() == [1, 2, 3, 4]


def test_people_in_another_order_raise():
    table = people().iloc[[3, 0, 1, 2]]
    with pytest.raises(ValueError, match="another order"):
        relationship_codes(table, run())


def test_two_people_of_one_age_swapped_inside_a_household_raise():
    table = people()
    table["age"] = [40.0, 40.0, 4.0, 70.0]
    lineup = run() | {"person.age": np.array([40, 40, 4, 70], dtype=np.float32)}
    with pytest.raises(ValueError, match="another order"):
        relationship_codes(table.iloc[[1, 0, 2, 3]], lineup)


def test_another_household_for_the_same_person_raises():
    table = people()
    table["person_household_id"] = [10, 10, 20, 20]
    with pytest.raises(ValueError, match="other households"):
        relationship_codes(table, run())


def test_other_ages_raise():
    table = people()
    table["age"] = [40.0, 38.0, 5.0, 70.0]
    with pytest.raises(ValueError, match="ages"):
        relationship_codes(table, run())


@pytest.mark.parametrize(
    ("column", "code", "message"),
    [("A_EXPRRP", 0, "outside 1 to 14"), ("A_MARITL", 8, "outside 1 to 7")],
)
def test_a_code_outside_the_survey_list_raises(column, code, message):
    table = people()
    table.loc[2, column] = code
    with pytest.raises(ValueError, match=message):
        relationship_codes(table, run())
