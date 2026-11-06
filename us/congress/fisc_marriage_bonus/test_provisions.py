"""Tests for provisions.py on small synthetic runs, with no model or microdata.

The arrays below are made up to exercise the checks. No number here reaches
results/.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import provisions
import summarize
from provisions import (
    CHAIN,
    GINIS,
    PROVISION_SCENARIOS,
    SAVED_LINES,
    check_accounts,
    check_against_saved_tables,
    check_tables_hold_the_answer,
    provisions_by_file,
)
from summarize import NET_INCOME, distribution, gini_by_provision
from test_summarize import N, fake_run

# Net income per household that each scenario adds to the same fake return, with the
# bonus and the rest of the credit in the credit arrays.
FAKE_SCENARIOS = {
    "baseline": (0.0, 500.0),
    "fisc": (0.2, 0.0),
    "fisc_no_bonus": (0.0, 0.0),
    "fisc_ctc_repeal_only": (0.0, -100.0),
    "fisc_no_newborn_add_on": (0.2, -100.0),
    "fisc_no_phase_out": (0.2, 100.0),
    "fisc_no_agi_cap": (0.2, 100.0),
}


def with_extra_income(run, extra):
    """Add income to a run, keeping its equivalised income on its definition."""
    income = run[NET_INCOME] + extra
    people = run["household.household_count_people"]
    return run | {
        NET_INCOME: income,
        "household.equiv_household_net_income": income / np.sqrt(people),
    }


def fake_runs(extras=None):
    extras = extras or {}
    return {
        scenario: with_extra_income(
            fake_run(rate, ctc=ctc), extras.get(scenario, np.zeros(N))
        )
        for scenario, (rate, ctc) in FAKE_SCENARIOS.items()
    }


@pytest.fixture
def in_memory(monkeypatch):
    """Serve fake runs from memory, so the tests write nothing to disk."""

    def serve(runs):
        def load(folder, scenario, year):
            return runs[folder][scenario]

        monkeypatch.setattr(summarize, "load", load)
        monkeypatch.setattr(provisions, "load", load)

    return serve


class TestProvisionsByFile:
    def test_every_file_holds_every_provision(self, in_memory):
        in_memory({"a": fake_runs(), "b": fake_runs()})
        table = provisions_by_file({"a": "a", "b": "b"})
        assert table.groupby("file").provision.nunique().eq(7).all()
        assert set(table.provision) >= set(CHAIN) | {"full_fisc"}

    def test_each_scenario_exists_in_the_list_the_workflow_runs(self):
        assert set(PROVISION_SCENARIOS) == set(FAKE_SCENARIOS)

    def test_rows_equal_the_two_tables_they_join(self, in_memory):
        in_memory({"a": fake_runs()})
        table = provisions_by_file({"a": "a"}).set_index("provision")
        gini = gini_by_provision("a").set_index("provision")
        pd.testing.assert_series_equal(
            table.net_income_change, gini.net_income_change, check_names=False
        )
        summary = distribution("a")["component_summary"].set_index(
            ["ranking", "component"]
        )
        assert table.bottom_five_deciles["marriage_bonus"] == pytest.approx(
            summary.bottom_five_deciles["household_net_income", "marriage_bonus"]
        )
        assert table.concentration_equivalised["phase_out"] == pytest.approx(
            summary.concentration["equivalised_household_net_income", "phase_out"]
        )
        assert table.top_three_deciles["full_fisc"] == pytest.approx(
            summary.top_three_deciles["household_net_income", "full_fisc_net"]
        )

    def test_a_run_on_other_weights_fails(self, in_memory):
        runs = fake_runs()
        runs["fisc_no_phase_out"]["household.household_weight"] = np.full(N, 900.0)
        in_memory({"a": runs})
        with pytest.raises(AssertionError, match="household_weight"):
            provisions_by_file({"a": "a"})


class TestAccounts:
    @settings(max_examples=25, deadline=None)
    @given(
        st.lists(
            st.lists(st.floats(0, 40_000), min_size=N, max_size=N),
            min_size=4,
            max_size=4,
        )
    )
    def test_the_chain_adds_to_full_fisc_for_any_incomes(self, draws):
        extras = {
            scenario: np.array(draw)
            for scenario, draw in zip(
                ("baseline", "fisc", "fisc_no_bonus", "fisc_ctc_repeal_only"), draws
            )
        }
        with pytest.MonkeyPatch.context() as patch:
            runs = fake_runs(extras)

            def load(folder, scenario, year):
                return runs[scenario]

            patch.setattr(summarize, "load", load)
            patch.setattr(provisions, "load", load)
            rows = provisions_by_file({"a": "a"}).set_index("provision")
        chain = rows.loc[list(CHAIN)]
        assert chain.net_income_change.sum() == pytest.approx(
            rows.net_income_change["full_fisc"], abs=1e-3
        )
        for gini in GINIS:
            assert chain[f"{gini}_change"].sum() == pytest.approx(
                rows[f"{gini}_change"]["full_fisc"], abs=1e-12
            )

    def test_fake_runs_pass(self, in_memory):
        in_memory({"a": fake_runs()})
        check_accounts(provisions_by_file({"a": "a"}))

    @pytest.mark.parametrize(
        "provision,column,value,message",
        [
            ("marriage_bonus", "net_income_change", 1e12, "net cost"),
            ("marriage_bonus", "household_gini_change", 1.0, "household_gini"),
            ("newborn_add_on", "net_income_change", -1.0, "payment"),
            ("phase_out", "net_income_change", 1.0, "cut"),
        ],
    )
    def test_a_broken_account_fails(self, in_memory, provision, column, value, message):
        in_memory({"a": fake_runs()})
        table = provisions_by_file({"a": "a"})
        table.loc[table.provision == provision, column] = value
        with pytest.raises(AssertionError, match=message):
            check_accounts(table)


def saved_tables(folder, table):
    """Write the three committed tables as these runs would state them."""
    rows = table.set_index(["file", "provision"])
    label = table.file.iloc[0]
    lines = {
        line: rows.loc[(label, provision), column]
        for (provision, column), line in SAVED_LINES.items()
    }
    frame = pd.DataFrame({"line": list(lines), label: list(lines.values())})
    frame.to_csv(folder / "data_comparison_2026.csv", index=False)
    frame.rename(columns={label: "other"}).assign(todays_data=frame[label]).to_csv(
        folder / "reweighted_comparison_2026.csv", index=False
    )
    gini_columns = [
        "provision",
        "net_income_change",
        "household_gini_without",
        "household_gini_with",
        "household_gini_change_per_billion",
        "equivalised_gini_without",
        "equivalised_gini_with",
        "equivalised_gini_change_per_billion",
    ]
    table[table.file == label][gini_columns].to_csv(
        folder / "gini_by_provision_2026.csv", index=False
    )


class TestAgainstSavedTables:
    @pytest.fixture
    def table(self, in_memory):
        in_memory({"todays_data": fake_runs()})
        return provisions_by_file({"todays_data": "todays_data"})

    def test_matching_tables_pass(self, table, tmp_path):
        saved_tables(tmp_path, table)
        gaps = check_against_saved_tables(table, tmp_path)
        assert gaps["todays_data"] == pytest.approx(0, abs=1e-12)

    def test_a_gap_in_a_comparison_line_fails(self, table, tmp_path):
        saved_tables(tmp_path, table)
        rows = table.provision == "marriage_bonus"
        table.loc[rows, "bottom_five_deciles"] += 0.01
        with pytest.raises(AssertionError, match="bottom_five_deciles"):
            check_against_saved_tables(table, tmp_path)

    def test_a_gap_in_a_provision_fails(self, table, tmp_path):
        saved_tables(tmp_path, table)
        table.loc[table.provision == "phase_out", "net_income_change"] *= 1.01
        with pytest.raises(AssertionError, match="phase_out"):
            check_against_saved_tables(table, tmp_path)

    def test_a_blank_saved_line_fails(self, table, tmp_path):
        saved_tables(tmp_path, table)
        path = tmp_path / "data_comparison_2026.csv"
        frame = pd.read_csv(path)
        frame.loc[frame.line == "gini_with_the_bonus", "todays_data"] = np.nan
        frame.to_csv(path, index=False)
        with pytest.raises(AssertionError, match="gini_with_the_bonus"):
            check_against_saved_tables(table, tmp_path)


def answer_table():
    """One file on which the bonus reaches the bottom least and lowers both Ginis."""
    rows = []
    for provision, gini_change, share in (
        ("ctc_repeal", 0.003, 0.5),
        ("credit_without_bonus", -0.007, 0.6),
        ("marriage_bonus", -0.0005, 0.4),
        ("newborn_add_on", -0.0002, 0.62),
        ("phase_out", -0.0008, 0.001),
        ("agi_cap", 0.0005, 0.9),
        ("full_fisc", -0.005, 0.7),
    ):
        rows.append(
            {
                "file": "a",
                "provision": provision,
                "household_gini_change": gini_change,
                "equivalised_gini_change": gini_change,
                "bottom_five_deciles": share,
                "bottom_five_deciles_equivalised": share,
            }
        )
    return pd.DataFrame(rows)


class TestTheAnswer:
    def test_the_answer_holds_on_this_table(self):
        check_tables_hold_the_answer(answer_table())

    @pytest.mark.parametrize(
        "provision,column,value,message",
        [
            ("marriage_bonus", "household_gini_change", 0.001, "bonus does not lower"),
            ("marriage_bonus", "equivalised_gini_change", 0.0, "bonus does not lower"),
            ("ctc_repeal", "household_gini_change", -0.001, "repeal does not raise"),
            ("agi_cap", "equivalised_gini_change", 0.0, "cap does not raise"),
            ("marriage_bonus", "bottom_five_deciles", 0.61, "credit_without_bonus"),
            ("newborn_add_on", "bottom_five_deciles_equivalised", 0.3, "newborn"),
        ],
    )
    def test_a_file_that_breaks_it_fails(self, provision, column, value, message):
        table = answer_table()
        table.loc[table.provision == provision, column] = value
        with pytest.raises(AssertionError, match=message):
            check_tables_hold_the_answer(table)


class TestMain:
    def test_a_failed_check_writes_nothing(self, in_memory, tmp_path, monkeypatch):
        in_memory({"todays_data": fake_runs()})
        table = provisions_by_file({"todays_data": "todays_data"})
        saved_tables(tmp_path, table)
        before = sorted(path.name for path in tmp_path.iterdir())
        monkeypatch.setattr(
            provisions,
            "check_tables_hold_the_answer",
            lambda table: (_ for _ in ()).throw(AssertionError("no")),
        )
        with pytest.raises(AssertionError, match="no"):
            provisions.main({"todays_data": "todays_data"}, tmp_path)
        assert sorted(path.name for path in tmp_path.iterdir()) == before

    def test_a_clean_run_writes_the_table(self, in_memory, tmp_path, monkeypatch):
        in_memory({"todays_data": fake_runs()})
        monkeypatch.setattr(
            provisions, "check_tables_hold_the_answer", lambda table: None
        )
        table = provisions_by_file({"todays_data": "todays_data"})
        saved_tables(tmp_path, table)
        written = provisions.main({"todays_data": "todays_data"}, tmp_path)
        saved = pd.read_csv(tmp_path / "provisions_by_file_2026.csv")
        assert list(saved.columns) == list(written.columns)
        assert len(saved) == 7
