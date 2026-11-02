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
            "person_household_id": [10, 10, 10, 20],
            "age": [40.0, 38.0, 4.0, 70.0],
            "A_EXPRRP": [1, 4, 5, 2],
        }
    )


def run() -> dict[str, np.ndarray]:
    return {
        "person.person_household_id": np.array([10, 10, 10, 20]),
        "person.age": np.array([40, 38, 4, 70], dtype=np.float32),
    }


def test_the_codes_follow_the_runs_people():
    codes = relationship_codes(people(), run())
    assert codes["person.cps_relationship"].tolist() == [1, 4, 5, 2]
    assert codes["person.person_household_id"].tolist() == [10, 10, 10, 20]


def test_people_in_another_order_raise():
    table = people().iloc[[3, 0, 1, 2]]
    with pytest.raises(ValueError, match="another order"):
        relationship_codes(table, run())


def test_people_swapped_inside_a_household_raise():
    table = people().iloc[[0, 2, 1, 3]]
    with pytest.raises(ValueError, match="ages"):
        relationship_codes(table, run())


def test_a_code_outside_the_survey_list_raises():
    table = people()
    table.loc[2, "A_EXPRRP"] = 0
    with pytest.raises(ValueError, match="outside 1 to 14"):
        relationship_codes(table, run())
