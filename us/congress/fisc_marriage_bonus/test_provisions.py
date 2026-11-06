"""Tests for provisions.py on small synthetic runs, with no model or microdata.

The arrays below are made up to exercise the checks. No number here reaches
results/.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from hypothesis import assume, given, settings
from hypothesis import strategies as st

import provisions
import summarize
from analysis import SCENARIOS, closed_form_credit, uncapped_credit
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
from summarize import BASE, CREDIT, NET_INCOME, distribution, gini_by_provision
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

    def test_the_bonus_row_reads_the_bonus_alone(self, in_memory):
        runs = fake_runs()
        in_memory({"a": runs})
        summary = distribution("a")["component_summary"]
        for ranking in provisions.RANKINGS:
            rows = summary[summary.ranking == ranking].set_index("component")
            weight = runs["fisc"]["household.household_weight"]
            with_bonus = runs["fisc"][summarize.HOUSEHOLD_CREDIT]
            without_bonus = runs["fisc_no_bonus"][summarize.HOUSEHOLD_CREDIT]
            assert rows.loc["marriage_bonus", "dollars"] == pytest.approx(
                ((with_bonus - without_bonus) * weight).sum()
            )
            assert rows.loc["credit_without_bonus", "dollars"] == pytest.approx(
                (without_bonus * weight).sum()
            )

    def test_each_scenario_exists_in_the_list_the_workflow_runs(self):
        workflow = Path(provisions.__file__).with_name("github_provision_runs.yml")
        matrix = yaml.safe_load(workflow.read_text())["jobs"]["run"]["strategy"][
            "matrix"
        ]
        assert set(matrix["scenario"]) == set(PROVISION_SCENARIOS)
        assert len(matrix["set"]) == len(provisions.FILES)

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
        for name in GINIS:
            assert table[f"{name}_change"]["marriage_bonus"] == pytest.approx(
                gini[f"{name}_with"]["marriage_bonus"]
                - gini[f"{name}_without"]["marriage_bonus"]
            )

    @pytest.mark.parametrize("scenario", PROVISION_SCENARIOS[1:])
    def test_a_run_on_other_weights_fails(self, in_memory, scenario):
        runs = fake_runs()
        runs[scenario]["household.household_weight"] = np.full(N, 900.0)
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
            try:
                rows = provisions_by_file({"a": "a"}).set_index("provision")
            except AssertionError as error:
                # A provision that moves no dollars has no Gini change per dollar.
                assume("moves no dollars" not in str(error))
                raise
        chain = rows.loc[list(CHAIN)]
        assert chain.net_income_change.sum() == pytest.approx(
            rows.net_income_change["full_fisc"], abs=1e-3
        )
        for gini in GINIS:
            assert chain[f"{gini}_change"].sum() == pytest.approx(
                rows[f"{gini}_change"]["full_fisc"], abs=1e-12
            )

    def test_a_provision_that_moves_no_dollars_raises(self, in_memory):
        runs = fake_runs()
        runs["fisc_no_agi_cap"] = runs["fisc"]
        in_memory({"a": runs})
        with pytest.raises(AssertionError, match="agi_cap moves no dollars"):
            provisions_by_file({"a": "a"})

    def test_fake_runs_pass(self, in_memory):
        in_memory({"a": fake_runs()})
        check_accounts(provisions_by_file({"a": "a"}))

    @pytest.mark.parametrize(
        "provision,column,value,message",
        [
            ("marriage_bonus", "net_income_change", 1e12, "net cost"),
            ("marriage_bonus", "household_gini_change", 1.0, "household_gini"),
            ("marriage_bonus", "equivalised_gini_change", 1.0, "equivalised_gini"),
            ("agi_cap", "net_income_change", 1.0, "cut"),
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

    def test_a_break_on_the_second_file_fails(self, in_memory):
        in_memory({"a": fake_runs(), "b": fake_runs()})
        table = provisions_by_file({"a": "a", "b": "b"})
        check_accounts(table)
        rows = (table.file == "b") & (table.provision == "marriage_bonus")
        table.loc[rows, "net_income_change"] = 1e12
        with pytest.raises(AssertionError, match="b: the chain"):
            check_accounts(table)

    def test_a_repeal_that_raises_income_fails(self, in_memory):
        """The chain still adds, so only the cut's own sign can catch this."""
        in_memory({"a": fake_runs()})
        table = provisions_by_file({"a": "a"})
        table.loc[table.provision == "ctc_repeal", "net_income_change"] = 1.0
        chain = table[table.provision.isin(CHAIN)].net_income_change.sum()
        table.loc[table.provision == "full_fisc", "net_income_change"] = chain
        with pytest.raises(AssertionError, match="a cut raises"):
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

    def test_a_gap_past_the_tolerance_fails(self, table, tmp_path):
        saved_tables(tmp_path, table)
        table.loc[table.provision == "marriage_bonus", "bottom_five_deciles"] += 1e-11
        with pytest.raises(AssertionError, match="bottom_five_deciles"):
            check_against_saved_tables(table, tmp_path)

    def test_a_single_precision_line_gets_its_own_tolerance(self, table, tmp_path):
        saved_tables(tmp_path, table)
        rows = table.provision == "marriage_bonus"
        table.loc[rows, "concentration_equivalised"] += 5e-7
        check_against_saved_tables(table, tmp_path)
        table.loc[rows, "concentration_equivalised"] += 2e-6
        with pytest.raises(AssertionError, match="concentration_equivalised"):
            check_against_saved_tables(table, tmp_path)

    def test_a_gap_on_the_second_file_fails(self, in_memory, tmp_path):
        in_memory({"todays_data": fake_runs(), "other": fake_runs()})
        table = provisions_by_file({"todays_data": "todays_data", "other": "other"})
        saved_tables(tmp_path, table)
        check_against_saved_tables(table, tmp_path)
        rows = (table.file == "other") & (table.provision == "marriage_bonus")
        table.loc[rows, "bottom_five_deciles"] += 0.01
        with pytest.raises(AssertionError, match="other: marriage_bonus"):
            check_against_saved_tables(table, tmp_path)

    def test_a_blank_cell_in_the_saved_gini_table_fails(self, table, tmp_path):
        saved_tables(tmp_path, table)
        path = tmp_path / "gini_by_provision_2026.csv"
        frame = pd.read_csv(path)
        frame.loc[frame.provision == "phase_out", "household_gini_with"] = np.nan
        frame.to_csv(path, index=False)
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
    for provision, gini_change, per_billion, share in (
        ("ctc_repeal", 0.003, 2e-5, 0.5),
        ("credit_without_bonus", -0.007, -3e-5, 0.6),
        ("marriage_bonus", -0.0005, -2e-5, 0.4),
        ("newborn_add_on", -0.0002, -2.5e-5, 0.62),
        ("phase_out", -0.0008, -2e-5, 0.001),
        ("agi_cap", 0.0005, 6e-5, 0.9),
        ("full_fisc", -0.005, -3.6e-5, 0.7),
    ):
        rows.append(
            {
                "file": "a",
                "provision": provision,
                "household_gini_change": gini_change,
                "equivalised_gini_change": gini_change,
                "household_gini_change_per_billion": per_billion,
                "equivalised_gini_change_per_billion": per_billion,
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
            ("phase_out", "equivalised_gini_change", 0.0005, "two Ginis apart"),
            ("phase_out", "equivalised_gini_change", 0.0, "two Ginis apart"),
            (
                "credit_without_bonus",
                "household_gini_change_per_billion",
                -1e-5,
                "credit_without_bonus",
            ),
            ("agi_cap", "household_gini_change_per_billion", 1e-5, "repeal raises"),
            ("agi_cap", "equivalised_gini_change_per_billion", 2e-5, "repeal raises"),
            ("marriage_bonus", "household_gini_change_per_billion", -4e-5, "beats"),
            ("newborn_add_on", "household_gini_change_per_billion", -1e-5, "beats"),
        ],
    )
    def test_a_file_that_breaks_it_fails(self, provision, column, value, message):
        table = answer_table()
        table.loc[table.provision == provision, column] = value
        with pytest.raises(AssertionError, match=message):
            check_tables_hold_the_answer(table)

    def test_a_break_on_the_second_file_fails(self):
        table = pd.concat([answer_table(), answer_table().assign(file="b")])
        check_tables_hold_the_answer(table)
        rows = (table.file == "b") & (table.provision == "marriage_bonus")
        table.loc[rows, "household_gini_change"] = 0.001
        with pytest.raises(AssertionError, match="b: the bonus does not lower"):
            check_tables_hold_the_answer(table)

    def test_the_bonus_may_beat_the_add_on_per_dollar_when_equivalised(self):
        """Intended: the per-dollar claim covers household net income alone. On five of
        the seven files the bonus lowers the equivalised Gini more per dollar than the
        add-on does, and the check must not claim otherwise."""
        table = answer_table()
        bonus = table.provision == "marriage_bonus"
        table.loc[bonus, "equivalised_gini_change_per_billion"] = -4e-5
        check_tables_hold_the_answer(table)


class TestRuns:
    """check_runs on runs that hold their scenarios, by sidecar and by the law."""

    @staticmethod
    def with_credit(run, credit):
        change = credit - run[CREDIT]
        income = run[NET_INCOME] + change
        people = run["household.household_count_people"]
        return run | {
            CREDIT: credit,
            summarize.HOUSEHOLD_CREDIT: credit,
            "tax_unit.income_tax": run["tax_unit.income_tax"] - change,
            "household.household_tax": run["household.household_tax"] - change,
            NET_INCOME: income,
            "household.equiv_household_net_income": income / np.sqrt(people),
        }

    @pytest.fixture
    def lawful(self, tmp_path):
        fisc = fake_run(0.2)
        base, joint = fisc[BASE], fisc["tax_unit.joint"].astype(bool)
        agi = fisc["tax_unit.adjusted_gross_income"]
        caregiver = summarize.has_caregiver(fisc)
        runs = {
            "baseline": self.with_credit(fisc, np.zeros(N)),
            "fisc": self.with_credit(
                fisc, closed_form_credit(base, joint, agi, 0.2) * caregiver
            ),
            "fisc_no_bonus": self.with_credit(
                fisc, closed_form_credit(base, joint, agi, 0.0) * caregiver
            ),
            "fisc_ctc_repeal_only": self.with_credit(fisc, np.zeros(N)),
            "fisc_no_newborn_add_on": self.with_credit(
                fisc, closed_form_credit(base, joint, agi, 0.2) * caregiver
            ),
            "fisc_no_phase_out": self.with_credit(
                fisc,
                np.minimum(base * (1 + 0.2 * joint), np.maximum(agi, 0)) * caregiver,
            ),
            "fisc_no_agi_cap": self.with_credit(
                fisc, uncapped_credit(base, joint, agi) * caregiver
            ),
        }
        for name in PROVISION_SCENARIOS:
            sidecar = {
                "scenario": name,
                "year": summarize.PRIMARY_YEAR,
                "policy": json.loads(json.dumps(SCENARIOS[name], default=str)),
            }
            (tmp_path / f"{name}_{summarize.PRIMARY_YEAR}.json").write_text(
                json.dumps(sidecar)
            )
        return runs, tmp_path

    def test_lawful_runs_pass(self, lawful, in_memory):
        runs, folder = lawful
        in_memory({folder: runs})
        provisions.check_runs(folder, "a")

    @pytest.mark.parametrize("scenario", PROVISION_SCENARIOS[1:])
    def test_income_with_nothing_behind_it_fails(self, lawful, in_memory, scenario):
        runs, folder = lawful
        runs[scenario] = with_extra_income(runs[scenario], np.full(N, 5.0))
        in_memory({folder: runs})
        with pytest.raises(AssertionError, match="net income misses"):
            provisions.check_runs(folder, "a")

    @pytest.mark.parametrize(
        "scenario,other",
        [
            ("fisc_no_phase_out", "fisc_no_agi_cap"),
            ("fisc_no_agi_cap", "fisc_no_bonus"),
            ("fisc_no_newborn_add_on", "fisc_no_bonus"),
            ("fisc_ctc_repeal_only", "fisc"),
        ],
    )
    def test_another_scenarios_arrays_fail(self, lawful, in_memory, scenario, other):
        runs, folder = lawful
        runs[scenario] = runs[other]
        in_memory({folder: runs})
        with pytest.raises(AssertionError, match="misses the law"):
            provisions.check_runs(folder, "a")

    @pytest.mark.parametrize(
        "scenario", ["fisc_no_bonus", "fisc_no_newborn_add_on", "fisc_no_agi_cap"]
    )
    def test_income_tax_that_misses_the_credit_fails(self, lawful, in_memory, scenario):
        runs, folder = lawful
        tax = runs[scenario]["tax_unit.income_tax"] + 5.0
        runs[scenario] = runs[scenario] | {"tax_unit.income_tax": tax}
        in_memory({folder: runs})
        with pytest.raises(AssertionError, match="income tax misses"):
            provisions.check_runs(folder, "a")

    def test_another_scenarios_sidecar_fails(self, lawful, in_memory):
        runs, folder = lawful
        in_memory({folder: runs})
        path = folder / f"fisc_no_agi_cap_{summarize.PRIMARY_YEAR}.json"
        sidecar = json.loads(path.read_text()) | {"scenario": "fisc"}
        path.write_text(json.dumps(sidecar))
        with pytest.raises(AssertionError, match="another scenario"):
            provisions.check_runs(folder, "a")


class TestMain:
    @pytest.fixture(autouse=True)
    def one_file(self, monkeypatch):
        monkeypatch.setattr(provisions, "FILES", ("todays_data",))
        monkeypatch.setattr(provisions, "check_runs", lambda folder, label: None)

    def test_a_missing_file_raises(self, in_memory, tmp_path, monkeypatch):
        monkeypatch.setattr(provisions, "FILES", ("todays_data", "other"))
        in_memory({"todays_data": fake_runs()})
        with pytest.raises(ValueError, match="one folder for each"):
            provisions.main({"todays_data": "todays_data"}, tmp_path)
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize(
        "check",
        [
            "check_runs",
            "check_accounts",
            "check_against_saved_tables",
            "check_tables_hold_the_answer",
            "check_tables_are_finite",
        ],
    )
    def test_a_failed_check_writes_nothing(
        self, in_memory, tmp_path, monkeypatch, check
    ):
        in_memory({"todays_data": fake_runs()})
        table = provisions_by_file({"todays_data": "todays_data"})
        saved_tables(tmp_path, table)
        before = sorted(path.name for path in tmp_path.iterdir())
        monkeypatch.setattr(
            provisions, "check_tables_hold_the_answer", lambda table: None
        )

        def fail(*args):
            raise AssertionError("no")

        monkeypatch.setattr(provisions, check, fail)
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
