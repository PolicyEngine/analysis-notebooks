"""Tests for recheck_tables.py on small made-up tables, with no model or microdata.

No number here reaches results/.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import recheck_tables
from recheck_tables import RECHECK_TOLERANCE, compare_table

SIZES = st.floats(min_value=1e-300, max_value=1e300)


def table():
    return pd.DataFrame(
        {"line": ["a", "b", "c"], "x": [1.0, np.nan, 3.0], "n": [1, 2, 3]}
    )


class TestCompareTable:
    def test_a_copy_counts_its_filled_numbers(self):
        assert compare_table("t", table(), table()) == (5, 0.0)

    @settings(deadline=None)
    @given(st.lists(st.one_of(SIZES, st.just(np.nan)), min_size=1, max_size=20))
    def test_any_copy_passes_with_no_gap(self, values):
        frame = pd.DataFrame({"x": values})
        numbers, largest = compare_table("t", frame, frame.copy())
        assert numbers == sum(not np.isnan(value) for value in values)
        assert largest == 0.0

    @settings(deadline=None)
    @given(SIZES)
    def test_a_move_within_the_tolerance_reports_its_gap(self, value):
        moved = value * (1 + RECHECK_TOLERANCE / 2)
        _, largest = compare_table(
            "t", pd.DataFrame({"x": [value]}), pd.DataFrame({"x": [moved]})
        )
        assert largest == pytest.approx(RECHECK_TOLERANCE / 2, rel=0.5)

    @settings(deadline=None)
    @given(SIZES, st.sampled_from([1, -1]))
    def test_a_move_past_the_tolerance_raises(self, value, sign):
        moved = value * (1 + sign * 2 * RECHECK_TOLERANCE)
        with pytest.raises(AssertionError, match="t: x moves"):
            compare_table(
                "t", pd.DataFrame({"x": [value]}), pd.DataFrame({"x": [moved]})
            )

    @settings(deadline=None)
    @given(SIZES, st.sampled_from([1, -1]))
    def test_a_hundred_trillionth_raises_and_one_unit_in_the_last_place_passes(
        self, value, sign
    ):
        """Stated apart from RECHECK_TOLERANCE, so loosening it fails here."""
        saved = pd.DataFrame({"x": [value]})
        with pytest.raises(AssertionError, match="t: x moves"):
            compare_table("t", saved, pd.DataFrame({"x": [value * (1 + sign * 1e-14)]}))
        step = np.nextafter(value, sign * np.inf)
        assert compare_table("t", saved, pd.DataFrame({"x": [step]}))[1] < 1e-15

    def test_a_number_against_zero_raises(self):
        with pytest.raises(AssertionError, match="moves"):
            compare_table("t", pd.DataFrame({"x": [0.0]}), pd.DataFrame({"x": [1e-30]}))

    def test_infinity_against_a_number_raises(self):
        with pytest.raises(AssertionError, match="moves"):
            compare_table(
                "t", pd.DataFrame({"x": [np.inf]}), pd.DataFrame({"x": [1.0]})
            )

    def test_a_blank_against_a_number_raises(self):
        fresh = table().assign(x=[1.0, 2.0, 3.0])
        with pytest.raises(AssertionError, match="blank"):
            compare_table("t", table(), fresh)

    def test_a_changed_label_raises(self):
        fresh = table().assign(line=["a", "b", "z"])
        with pytest.raises(AssertionError, match="label"):
            compare_table("t", table(), fresh)

    def test_a_number_against_a_label_raises(self):
        fresh = table().assign(n=["1", "2", "four"])
        with pytest.raises(AssertionError, match="label"):
            compare_table("t", table(), fresh)

    @pytest.mark.parametrize(
        "fresh",
        [
            table().drop(columns="n"),
            table()[["x", "line", "n"]],
            table().iloc[:2],
        ],
    )
    def test_another_shape_raises(self, fresh):
        with pytest.raises(AssertionError, match="shape"):
            compare_table("t", table(), fresh)


class TestMain:
    @pytest.fixture
    def saved(self, tmp_path, monkeypatch):
        """A results folder and the rebuild that matches it."""
        table().to_csv(tmp_path / "one.csv", index=False)
        provisions = pd.DataFrame(
            {"provision": ["agi_cap", "other"], "cost": [5.0, 6.0], "other": [1.0, 2.0]}
        )
        provisions.to_csv(tmp_path / "provisions_2026.csv", index=False)
        monkeypatch.setattr(
            recheck_tables, "rebuilt_tables", lambda runs: {"one": table()}
        )
        monkeypatch.setattr(
            recheck_tables.summarize,
            "agi_cap_provision",
            lambda work, detail: ({"provision": "agi_cap", "cost": 5.0}, {}),
        )
        return tmp_path

    def test_a_matching_rebuild_counts_each_table(self, saved, tmp_path):
        assert recheck_tables.main(tmp_path, saved) == {
            "one": (5, 0.0),
            "provisions_2026": (1, 0.0),
        }

    def test_a_table_that_moves_raises(self, saved, tmp_path, monkeypatch):
        monkeypatch.setattr(
            recheck_tables,
            "rebuilt_tables",
            lambda runs: {"one": table().assign(n=[1, 2, 4])},
        )
        with pytest.raises(AssertionError, match="one: n moves"):
            recheck_tables.main(tmp_path, saved)

    def test_the_provision_row_that_moves_raises(self, saved, tmp_path, monkeypatch):
        monkeypatch.setattr(
            recheck_tables.summarize,
            "agi_cap_provision",
            lambda work, detail: ({"provision": "agi_cap", "cost": 5.5}, {}),
        )
        with pytest.raises(AssertionError, match="provisions_2026: cost moves"):
            recheck_tables.main(tmp_path, saved)

    def test_the_comparison_writes_nothing(self, saved, tmp_path):
        before = sorted(path.name for path in saved.iterdir())
        recheck_tables.main(tmp_path, saved)
        assert sorted(path.name for path in saved.iterdir()) == before
