"""Tests for summarize.py on small synthetic runs, with no model or microdata.

The arrays below are made up to exercise the checks. No number here reaches
results/.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import summarize
from analysis import closed_form_credit
from summarize import (
    BASE,
    CREDIT,
    HOUSEHOLD_CREDIT,
    INCOME_TAX,
    NET_INCOME,
    PRIMARY_YEAR,
    bonus_gap_from_api,
    bonus_reach,
    check_invariants,
    check_poverty_run,
    check_the_answer_on_every_file,
    data_comparison,
    deciles_by_data_file,
    distribution,
    equivalised_gini,
    gini_by_provision,
    main,
    versus_reeves,
)

N = 60
FAKE_BASE_AMOUNTS = (0.0, 3_000.0, 4_800.0, 8_000.0)
FAKE_INCOMES = (20_000.0, 60_000.0, 140_000.0, 270_000.0, 400_000.0)


def fake_run(rate: float, *, ctc: float = 0.0) -> dict[str, np.ndarray]:
    index = np.arange(N)
    base = np.array(FAKE_BASE_AMOUNTS)[index % 4]
    joint = index % 2 == 0
    agi = np.array(FAKE_INCOMES)[index % 5]
    credit = closed_form_credit(base, joint, agi, rate)
    # One tax unit per household, so the two entities share these arrays.
    arrays = {
        "tax_unit.tax_unit_id": index,
        "tax_unit.tax_unit_weight": np.full(N, 1_000.0),
        "tax_unit.income_tax": 0.1 * agi - credit - ctc,
        "tax_unit.adjusted_gross_income": agi,
        "tax_unit.age_head": np.full(N, 35),
        "tax_unit.age_spouse": np.where(joint, 35, 0),
        "tax_unit.joint": joint,
        CREDIT: credit,
        BASE: base,
        HOUSEHOLD_CREDIT: credit,
        "household.household_id": index,
        "household.household_weight": np.full(N, 1_000.0),
        "household.household_count_people": 2 + index % 3,
        "household.household_tax": 0.1 * agi - credit - ctc,
        "household.household_benefits": np.zeros(N),
        NET_INCOME: 0.9 * agi + credit + ctc,
        "household.equiv_household_net_income": (0.9 * agi + credit + ctc)
        / np.sqrt(2 + index % 3),
        "household.household_income_decile": 1 + index % 10,
        "person.person_tax_unit_id": index,
        "person.person_household_id": index,
    }
    return arrays


def save(folder, scenario, arrays):
    np.savez(folder / f"{scenario}_{PRIMARY_YEAR}.npz", **arrays)


def fake_people(in_poverty=None):
    return {
        "person_in_poverty": np.zeros(N, dtype=bool)
        if in_poverty is None
        else in_poverty,
        "age": np.where(np.arange(N) % 2 == 0, 10.0, 40.0),
        "person_weight": np.full(N, 3_000.0, dtype=np.float32),
    }


@pytest.fixture
def runs(tmp_path):
    work, rerun = tmp_path / "work", tmp_path / "rerun"
    work.mkdir()
    rerun.mkdir()
    save(work, "baseline", fake_run(0.0, ctc=500.0))
    for scenario in ("fisc", "fisc_restored_bonus"):
        save(work, scenario, fake_run(0.2))
    for scenario in (
        "fisc_no_newborn_add_on",
        "fisc_no_phase_out",
        "fisc_no_agi_cap",
    ):
        save(work, scenario, fake_run(0.2, ctc=100.0))
    save(work, "fisc_no_bonus", fake_run(0.0))
    save(rerun, "fisc_no_bonus", fake_run(0.0))
    save(work, "fisc_ctc_repeal_only", fake_run(0.0, ctc=-100.0))
    return work, rerun


class TestInvariants:
    def test_consistent_runs_pass(self, runs):
        results = check_invariants(*runs)
        assert results["restoring_the_bonus_reproduces_full_fisc"]
        assert results["bonus_measured_by_the_credit"] == pytest.approx(
            results["bonus_measured_by_income_tax"]
        )
        assert results["bonus_measured_by_the_credit"] == pytest.approx(
            results["bonus_measured_by_net_income"]
        )

    def test_a_restored_run_that_differs_fails(self, runs):
        work, rerun = runs
        restored = fake_run(0.2)
        restored[CREDIT][1] += 1
        save(work, "fisc_restored_bonus", restored)
        with pytest.raises(AssertionError, match="restoring"):
            check_invariants(work, rerun)

    def test_a_rerun_that_differs_fails(self, runs):
        work, rerun = runs
        repeat = fake_run(0.0)
        repeat[NET_INCOME][1] += 1
        save(rerun, "fisc_no_bonus", repeat)
        with pytest.raises(AssertionError, match="rerun"):
            check_invariants(work, rerun)

    @pytest.mark.parametrize("scenario", ["fisc", "fisc_restored_bonus"])
    def test_a_bonus_for_an_unmarried_unit_fails(self, runs, scenario):
        work, rerun = runs
        fisc = fake_run(0.2)
        unmarried = np.flatnonzero(~fisc["tax_unit.joint"] & (fisc[BASE] > 0))[0]
        fisc[CREDIT][unmarried] += 100
        save(work, "fisc", fisc)
        save(work, "fisc_restored_bonus", fisc)
        with pytest.raises(AssertionError, match="unmarried"):
            check_invariants(work, rerun)

    def test_a_credit_off_the_closed_form_fails(self, runs):
        work, rerun = runs
        fisc = fake_run(0.2)
        married = np.flatnonzero(fisc["tax_unit.joint"] & (fisc[BASE] > 0))[0]
        fisc[CREDIT][married] += 100
        save(work, "fisc", fisc)
        save(work, "fisc_restored_bonus", fisc)
        with pytest.raises(AssertionError, match="closed form"):
            check_invariants(work, rerun)

    def test_a_unit_with_no_adult_loses_the_credit(self, runs):
        work, rerun = runs
        for scenario, rate in (
            ("fisc", 0.2),
            ("fisc_restored_bonus", 0.2),
            ("fisc_no_bonus", 0.0),
        ):
            run = fake_run(rate)
            unit = np.flatnonzero(~run["tax_unit.joint"] & (run[BASE] > 0))[0]
            run["tax_unit.age_head"][unit] = 17
            run[CREDIT][unit] = 0
            run[HOUSEHOLD_CREDIT][unit] = 0
            save(work, scenario, run)
            if scenario == "fisc_no_bonus":
                save(rerun, scenario, run)
        results = check_invariants(work, rerun)
        assert results["tax_units_with_a_child_and_no_adult_caregiver"] == 1_000

    def test_offsetting_tax_errors_fail(self, runs):
        work, rerun = runs
        fisc = fake_run(0.2)
        fisc[INCOME_TAX][0] += 10_000
        fisc[INCOME_TAX][1] -= 10_000
        save(work, "fisc", fisc)
        save(work, "fisc_restored_bonus", fisc)
        with pytest.raises(AssertionError, match="income tax moved apart"):
            check_invariants(work, rerun)

    def test_a_net_income_gain_with_no_tax_or_benefit_behind_it_fails(self, runs):
        work, rerun = runs
        fisc = fake_run(0.2)
        fisc[NET_INCOME] = fisc[NET_INCOME] + 50_000
        save(work, "fisc", fisc)
        save(work, "fisc_restored_bonus", fisc)
        with pytest.raises(AssertionError, match="net income moved apart"):
            check_invariants(work, rerun)

    def test_a_household_shift_hidden_behind_household_tax_fails(self, runs):
        work, rerun = runs
        fisc = fake_run(0.2)
        fisc[NET_INCOME][0] += 100_000
        fisc["household.household_tax"][0] -= 100_000
        fisc["household.equiv_household_net_income"] = fisc[NET_INCOME] / np.sqrt(
            fisc["household.household_count_people"]
        )
        save(work, "fisc", fisc)
        save(work, "fisc_restored_bonus", fisc)
        with pytest.raises(AssertionError, match="apart from the credit"):
            check_invariants(work, rerun)

    def test_a_household_bonus_missing_its_tax_units_fails(self, runs):
        work, rerun = runs
        fisc = fake_run(0.2)
        fisc[HOUSEHOLD_CREDIT] = fake_run(0.0)[HOUSEHOLD_CREDIT]
        save(work, "fisc", fisc)
        save(work, "fisc_restored_bonus", fisc)
        with pytest.raises(AssertionError, match="misses its tax units"):
            check_invariants(work, rerun)


class TestEquivalisedIncome:
    def test_an_income_off_its_definition_fails(self):
        run = fake_run(0.2)
        run["household.equiv_household_net_income"] = np.full(N, 100_000.0)
        with pytest.raises(AssertionError, match="equivalised income"):
            equivalised_gini(run)


class TestPovertyRun:
    @staticmethod
    def runs():
        with_cap, without_cap = fake_run(0.2), fake_run(0.2)
        without_cap[NET_INCOME][0] += 500
        poor = np.zeros(N, dtype=bool)
        poor[0] = True
        return with_cap, without_cap, fake_people(poor), fake_people()

    def test_a_lift_in_a_household_that_gains_passes(self):
        check_poverty_run(*self.runs())

    def test_the_same_file_twice_fails(self):
        with_cap, without_cap, people, _ = self.runs()
        with pytest.raises(AssertionError, match="lifted no one"):
            check_poverty_run(with_cap, without_cap, people, people)

    def test_someone_moved_into_poverty_fails(self):
        with_cap, without_cap, people, _ = self.runs()
        worse = fake_people(np.array([True, True] + [False] * (N - 2)))
        with pytest.raises(AssertionError, match="into poverty"):
            check_poverty_run(with_cap, without_cap, people, worse)

    def test_a_lift_with_no_gain_fails(self):
        with_cap, _, people, people_without = self.runs()
        with pytest.raises(AssertionError, match="no gain"):
            check_poverty_run(with_cap, with_cap, people, people_without)

    def test_different_people_fail(self):
        with_cap, without_cap, people, people_without = self.runs()
        people_without["age"] = people_without["age"] + 1
        with pytest.raises(AssertionError, match="different people"):
            check_poverty_run(with_cap, without_cap, people, people_without)


class TestMain:
    def test_a_failed_check_removes_the_marker_and_writes_nothing(
        self, runs, tmp_path, monkeypatch
    ):
        work, rerun = runs
        results = tmp_path / "results"
        results.mkdir()
        (results / "invariants.json").write_text("{}")
        monkeypatch.setattr(summarize, "RESULTS", results)
        broken = fake_run(0.2)
        broken[CREDIT][1] += 1
        save(work, "fisc_restored_bonus", broken)
        with pytest.raises(AssertionError, match="restoring"):
            main(work, rerun, work, work, work, work)
        assert list(results.iterdir()) == []


class TestBonusGapFromApi:
    @pytest.fixture
    def api(self, runs, monkeypatch):
        work, _ = runs
        bonus = sum(
            1_000 * (fake_run(0.2)[CREDIT][i] - fake_run(0.0)[CREDIT][i])
            for i in range(N)
        )
        monkeypatch.setattr(
            summarize,
            "api_result",
            lambda *_: {"detailed_budget": {"income_tax": {"difference": -bonus}}},
        )
        return work, bonus

    def test_matching_runs_pass(self, api):
        work, bonus = api
        result = bonus_gap_from_api(work, PRIMARY_YEAR)
        assert result[f"bonus_local_{PRIMARY_YEAR}"] == pytest.approx(bonus)

    def test_a_bonus_off_the_api_fails(self, api):
        work, _ = api
        run = fake_run(0.0)
        run["tax_unit.income_tax"] = run["tax_unit.income_tax"] + 1_000
        save(work, "fisc_no_bonus", run)
        with pytest.raises(AssertionError, match="disagree"):
            bonus_gap_from_api(work, PRIMARY_YEAR)

    def test_a_bonus_for_an_unmarried_unit_fails(self, api):
        work, _ = api
        fisc = fake_run(0.2)
        unmarried = np.flatnonzero(~fisc["tax_unit.joint"] & (fisc[BASE] > 0))[0]
        fisc[CREDIT][unmarried] += 100
        save(work, "fisc", fisc)
        with pytest.raises(AssertionError, match="unmarried"):
            bonus_gap_from_api(work, PRIMARY_YEAR)


class TestDistribution:
    def test_every_component_sums_across_groups(self, runs):
        work, _ = runs
        tables = distribution(work)
        summary = tables["component_summary"]
        deciles = tables["deciles_by_component"]
        totals = deciles.groupby(["ranking", "component"]).dollars.sum()
        for row in summary.itertuples():
            assert totals[row.ranking, row.component] == pytest.approx(
                row.dollars, abs=1
            )

    def test_both_rankings_cover_every_component(self, runs):
        work, _ = runs
        summary = distribution(work)["component_summary"]
        assert summary.groupby("ranking").component.nunique().eq(7).all()


class TestBonusReach:
    def test_rows_sum_to_the_bonus(self, runs):
        work, _ = runs
        lines = versus_reeves(work).set_index("line").value
        assert bonus_reach(work).bonus.sum() == pytest.approx(lines["modelled_bonus"])

    def test_a_tax_unit_across_two_households_fails(self, runs):
        work, _ = runs
        no_bonus = fake_run(0.0)
        moved = no_bonus["person.person_tax_unit_id"].copy()
        moved[1] = 0
        no_bonus["person.person_tax_unit_id"] = moved
        save(work, "fisc_no_bonus", no_bonus)
        with pytest.raises(AssertionError, match="spans"):
            bonus_reach(work)


class TestGiniByProvision:
    def test_every_provision_has_a_row(self, runs):
        work, _ = runs
        table = gini_by_provision(work).set_index("provision")
        assert len(table) == 7
        assert table.net_income_change["marriage_bonus"] > 0


class TestDataComparison:
    @pytest.fixture
    def table(self, runs):
        work, _ = runs
        np.savez(work / f"fisc_{PRIMARY_YEAR}_poverty.npz", **fake_people())
        np.savez(work / f"fisc_{PRIMARY_YEAR}_people.npz", **fake_people())
        return data_comparison(work, work, work, work).set_index("line")

    def test_each_file_reports_the_bonus_within_its_statutory_bound(self, table):
        for column in ("march_2025_data", "cps_2024_data", "todays_data"):
            assert table[column]["bonus"] <= table[column]["statutory_bonus"] + 1
            assert 0 < table[column]["joint_share_of_base_amount"] < 1

    def test_the_child_share_counts_children_in_joint_units(self, table):
        share = table["todays_data"]["share_of_children_in_joint_tax_units"]
        assert share == pytest.approx(1.0)

    @staticmethod
    def answer(**changes):
        lines = {
            "gini_with_the_bonus": 0.46,
            "gini_without_the_bonus": 0.47,
            "bonus_concentration": 0.1,
            "household_income_gini": 0.47,
            "rest_of_credit_concentration": 0.0,
            "bonus_share_of_bottom_five_deciles": 0.4,
            "rest_of_credit_share_of_bottom_five_deciles": 0.5,
        }
        rows = {"line": list(lines), "cps_2024_data": list(lines.values())}
        rows["todays_data"] = rows["march_2025_data"] = rows["cps_2024_data"]
        table = pd.DataFrame(rows).set_index("line")
        for name, value in changes.items():
            table.loc[name, "cps_2024_data"] = value
        return table.reset_index()

    def test_the_answer_passes_when_it_holds_on_every_file(self):
        assert check_the_answer_on_every_file(self.answer())

    @pytest.mark.parametrize(
        "change",
        [
            {"gini_with_the_bonus": 0.48},
            {"bonus_concentration": 0.5},
            {"bonus_concentration": -0.1},
            {"bonus_share_of_bottom_five_deciles": 0.6},
        ],
    )
    def test_the_answer_fails_when_one_file_breaks_it(self, change):
        with pytest.raises(AssertionError, match="cps_2024_data"):
            check_the_answer_on_every_file(self.answer(**change))

    def test_decile_rows_sum_to_the_bonus_on_each_file(self, table, runs):
        work, _ = runs
        deciles = deciles_by_data_file(work, work, work)
        for label, rows in deciles.groupby("data_file"):
            assert rows.dollars.sum() == pytest.approx(table[label]["bonus"], abs=1)

    def test_the_census_column_holds_the_published_share(self, table):
        share = table["census_2023"]["share_of_children_in_joint_tax_units"]
        assert share == pytest.approx(48_228 / 72_296)


class TestVersusReeves:
    def test_twenty_percent_of_the_joint_base_amount_bounds_the_bonus(self, runs):
        work, _ = runs
        lines = versus_reeves(work).set_index("line").value
        assert (
            lines["modelled_bonus"] <= lines["twenty_percent_of_joint_base_amount"] + 1
        )
