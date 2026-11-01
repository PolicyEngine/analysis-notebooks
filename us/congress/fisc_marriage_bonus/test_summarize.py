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
    check_tables_are_finite,
    check_the_answer_on_every_file,
    check_the_decade,
    data_comparison,
    deciles_by_data_file,
    distribution,
    equivalised_gini,
    gini_by_provision,
    load,
    main,
    sampling_spread,
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


FAKE_POVERTY_THRESHOLD = 30_000.0


def fake_people():
    return {
        "person_in_poverty": np.zeros(N, dtype=bool),
        "age": np.where(np.arange(N) % 2 == 0, 10.0, 40.0),
        "person_weight": np.full(N, 3_000.0, dtype=np.float32),
    }


def fake_detail(run, state_tax=None):
    """Each household is one SPM unit, so SPM income follows household net income."""
    income = run[NET_INCOME].copy()
    threshold = np.full(N, FAKE_POVERTY_THRESHOLD)
    return fake_people() | {
        "person_in_poverty": income < threshold,
        "person_spm_unit_id": np.arange(N),
        "spm_unit_id": np.arange(N),
        "spm_unit_net_income": income,
        "spm_unit_spm_threshold": threshold,
        "state_income_tax": np.zeros(N) if state_tax is None else state_tax,
    }


def save_detail(folder, scenario, arrays):
    np.savez(folder / f"{scenario}_{PRIMARY_YEAR}_detail.npz", **arrays)


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
    save_detail(work, "fisc", fake_detail(fake_run(0.2)))
    save_detail(work, "fisc_no_bonus", fake_detail(fake_run(0.0)))
    save_detail(work, "fisc_no_agi_cap", fake_detail(fake_run(0.2, ctc=100.0)))
    return work, rerun


class TestInvariants:
    def test_consistent_runs_pass(self, runs):
        results = check_invariants(*runs, runs[0])
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
            check_invariants(work, rerun, work)

    def test_a_rerun_that_differs_fails(self, runs):
        work, rerun = runs
        repeat = fake_run(0.0)
        repeat[NET_INCOME][1] += 1
        save(rerun, "fisc_no_bonus", repeat)
        with pytest.raises(AssertionError, match="rerun"):
            check_invariants(work, rerun, work)

    @pytest.mark.parametrize("scenario", ["fisc", "fisc_restored_bonus"])
    def test_a_bonus_for_an_unmarried_unit_fails(self, runs, scenario):
        work, rerun = runs
        fisc = fake_run(0.2)
        unmarried = np.flatnonzero(~fisc["tax_unit.joint"] & (fisc[BASE] > 0))[0]
        fisc[CREDIT][unmarried] += 100
        save(work, "fisc", fisc)
        save(work, "fisc_restored_bonus", fisc)
        with pytest.raises(AssertionError, match="unmarried"):
            check_invariants(work, rerun, work)

    def test_a_credit_off_the_closed_form_fails(self, runs):
        work, rerun = runs
        fisc = fake_run(0.2)
        married = np.flatnonzero(fisc["tax_unit.joint"] & (fisc[BASE] > 0))[0]
        fisc[CREDIT][married] += 100
        save(work, "fisc", fisc)
        save(work, "fisc_restored_bonus", fisc)
        with pytest.raises(AssertionError, match="closed form"):
            check_invariants(work, rerun, work)

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
        results = check_invariants(work, rerun, work)
        assert results["tax_units_with_a_child_and_no_adult_caregiver"] == 1_000

    def test_offsetting_tax_errors_fail(self, runs):
        work, rerun = runs
        fisc = fake_run(0.2)
        fisc[INCOME_TAX][0] += 10_000
        fisc[INCOME_TAX][1] -= 10_000
        save(work, "fisc", fisc)
        save(work, "fisc_restored_bonus", fisc)
        with pytest.raises(AssertionError, match="income tax moved apart"):
            check_invariants(work, rerun, work)

    def test_a_net_income_gain_with_no_tax_or_benefit_behind_it_fails(self, runs):
        work, rerun = runs
        fisc = fake_run(0.2)
        fisc[NET_INCOME] = fisc[NET_INCOME] + 50_000
        save(work, "fisc", fisc)
        save(work, "fisc_restored_bonus", fisc)
        with pytest.raises(AssertionError, match="net income moved apart"):
            check_invariants(work, rerun, work)

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
            check_invariants(work, rerun, work)

    def test_a_small_shift_between_households_fails(self, runs):
        work, rerun = runs
        fisc = fake_run(0.2)
        receiving = np.flatnonzero(fisc[CREDIT] > fake_run(0.0)[CREDIT])[:2]
        fisc[NET_INCOME][receiving[0]] += 50
        fisc[NET_INCOME][receiving[1]] -= 50
        fisc["household.household_tax"][receiving[0]] -= 50
        fisc["household.household_tax"][receiving[1]] += 50
        fisc["household.equiv_household_net_income"] = fisc[NET_INCOME] / np.sqrt(
            fisc["household.household_count_people"]
        )
        save(work, "fisc", fisc)
        save(work, "fisc_restored_bonus", fisc)
        with pytest.raises(AssertionError, match="apart from the credit"):
            check_invariants(work, rerun, work)

    def test_state_tax_explains_a_household_change(self, runs):
        work, rerun = runs
        fisc, no_bonus = fake_run(0.2), fake_run(0.0)
        state_tax = 0.0005 * (fisc[CREDIT] - no_bonus[CREDIT])
        fisc[NET_INCOME] = fisc[NET_INCOME] - state_tax
        fisc["household.household_tax"] = fisc["household.household_tax"] + state_tax
        fisc["household.equiv_household_net_income"] = fisc[NET_INCOME] / np.sqrt(
            fisc["household.household_count_people"]
        )
        save(work, "fisc", fisc)
        save(work, "fisc_restored_bonus", fisc)
        save_detail(work, "fisc", fake_detail(fisc, state_tax))
        results = check_invariants(work, rerun, work)
        assert results["bonus_state_income_tax_change"] == pytest.approx(
            (state_tax * 1_000).sum()
        )

    def test_state_tax_with_no_credit_behind_it_fails(self, runs):
        work, rerun = runs
        fisc, no_bonus = fake_run(0.2), fake_run(0.0)
        unchanged = np.flatnonzero(fisc[CREDIT] == no_bonus[CREDIT])[0]
        state_tax = np.zeros(N)
        state_tax[unchanged] = 10
        save_detail(work, "fisc", fake_detail(fisc, state_tax))
        with pytest.raises(AssertionError, match="no credit behind it"):
            check_invariants(work, rerun, work)

    def test_a_household_bonus_missing_its_tax_units_fails(self, runs):
        work, rerun = runs
        fisc = fake_run(0.2)
        fisc[HOUSEHOLD_CREDIT] = fake_run(0.0)[HOUSEHOLD_CREDIT]
        save(work, "fisc", fisc)
        save(work, "fisc_restored_bonus", fisc)
        with pytest.raises(AssertionError, match="misses its tax units"):
            check_invariants(work, rerun, work)


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
        without_cap[NET_INCOME][0] += 13_000
        return (
            with_cap,
            without_cap,
            fake_detail(with_cap),
            fake_detail(without_cap),
        )

    def test_a_lift_the_income_explains_passes(self):
        results = check_poverty_run(*self.runs())
        assert results["agi_cap_largest_household_gap_from_spm_income"] == 0

    def test_a_flag_the_income_does_not_explain_fails(self):
        with_cap, without_cap, detail, detail_without = self.runs()
        detail_without["person_in_poverty"] = np.zeros(N, dtype=bool)
        with pytest.raises(AssertionError, match="misses its income"):
            check_poverty_run(with_cap, without_cap, detail, detail_without)

    def test_income_with_no_household_gain_behind_it_fails(self):
        with_cap, without_cap, detail, detail_without = self.runs()
        poor = np.flatnonzero(detail_without["person_in_poverty"])[0]
        detail_without["spm_unit_net_income"][poor] += 50_000
        detail_without["person_in_poverty"][poor] = False
        with pytest.raises(AssertionError, match="SPM income moved apart"):
            check_poverty_run(with_cap, without_cap, detail, detail_without)

    def test_a_moved_threshold_fails(self):
        with_cap, without_cap, detail, detail_without = self.runs()
        detail_without["spm_unit_spm_threshold"][0] = 1.0
        with pytest.raises(AssertionError, match="threshold"):
            check_poverty_run(with_cap, without_cap, detail, detail_without)

    def test_the_same_file_twice_fails(self):
        with_cap, _, detail, _ = self.runs()
        with pytest.raises(AssertionError, match="lifted no one"):
            check_poverty_run(with_cap, with_cap, detail, detail)

    def test_someone_moved_into_poverty_fails(self):
        with_cap, without_cap, detail, _ = self.runs()
        above = np.flatnonzero(~detail["person_in_poverty"])[0]
        without_cap[NET_INCOME][above] = FAKE_POVERTY_THRESHOLD - 1
        with pytest.raises(AssertionError, match="into poverty"):
            check_poverty_run(with_cap, without_cap, detail, fake_detail(without_cap))

    def test_an_spm_unit_across_two_households_fails(self):
        with_cap, without_cap, detail, detail_without = self.runs()
        for arrays in (detail, detail_without):
            arrays["person_spm_unit_id"][1] = 0
            arrays["person_in_poverty"][1] = arrays["person_in_poverty"][0]
        with pytest.raises(AssertionError, match="spans two households"):
            check_poverty_run(with_cap, without_cap, detail, detail_without)

    def test_different_people_fail(self):
        with_cap, without_cap, detail, detail_without = self.runs()
        detail_without["age"] = detail_without["age"] + 1
        with pytest.raises(AssertionError, match="different people"):
            check_poverty_run(with_cap, without_cap, detail, detail_without)


class TestLoad:
    def test_a_saved_nan_fails(self, runs):
        work, _ = runs
        fisc = fake_run(0.2)
        fisc[CREDIT][0] = np.nan
        save(work, "fisc", fisc)
        with pytest.raises(AssertionError, match="not finite"):
            load(work, "fisc", PRIMARY_YEAR)


class TestTablesAreFinite:
    def test_a_nan_cell_fails(self):
        with pytest.raises(AssertionError, match="a cell"):
            check_tables_are_finite({"table": pd.DataFrame({"a": [1.0, np.nan]})})

    def test_a_cell_left_blank_on_purpose_passes(self):
        ladder = pd.DataFrame({"rung": ["start"], "step": [np.nan]})
        check_tables_are_finite({"march_2025_ladder": ladder})


class TestTheDecade:
    def later(self, work, run):
        np.savez(work / "fisc_2035.npz", **run)

    def grown(self):
        run = fake_run(0.2)
        for name in ("household.household_weight", "tax_unit.tax_unit_weight"):
            run[name] = run[name] * 1.03
        return run

    def test_families_as_they_stand_with_common_weight_growth_pass(self, runs):
        work, _ = runs
        self.later(work, self.grown())
        assert check_the_decade(work)[
            "weight_growth_from_2026_to_2035"
        ] == pytest.approx(1.03)

    def test_a_family_that_changes_fails(self, runs):
        work, _ = runs
        run = self.grown()
        run["tax_unit.joint"] = ~run["tax_unit.joint"]
        self.later(work, run)
        with pytest.raises(AssertionError, match="changed tax_unit.joint"):
            check_the_decade(work)

    def test_uneven_weight_growth_fails(self, runs):
        work, _ = runs
        run = self.grown()
        run["household.household_weight"][0] *= 1.01
        self.later(work, run)
        with pytest.raises(AssertionError, match="unevenly"):
            check_the_decade(work)


class TestSamplingSpread:
    @pytest.fixture
    def folder(self, runs):
        work, _ = runs
        for scenario in ("baseline", "fisc", "fisc_no_bonus"):
            run = np.load(work / f"{scenario}_{PRIMARY_YEAR}.npz")
            arrays = {name: run[name] for name in run}
            arrays["household.household_weight"] = 1_000.0 * (1 + np.arange(N) % 3)
            save(work, scenario, arrays)
        return work

    def test_the_saved_file_sits_within_its_redraws(self, folder):
        table = sampling_spread(folder).set_index("line")
        bonus = table.loc["bonus"]
        assert bonus.standard_deviation > 0
        assert bonus.lowest_redraw < bonus.saved_file < bonus.highest_redraw

    def test_the_redraws_repeat(self, folder):
        pd.testing.assert_frame_equal(sampling_spread(folder), sampling_spread(folder))

    def test_weights_that_do_not_count_draws_fail(self, folder):
        arrays = load(folder, "baseline", PRIMARY_YEAR)
        arrays["household.household_weight"][0] = 1_500.0
        save(folder, "baseline", arrays)
        with pytest.raises(AssertionError, match="count draws"):
            sampling_spread(folder)


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
            "equivalised_income_gini": 0.45,
            "rest_of_credit_concentration": 0.0,
            "bonus_concentration_equivalised": -0.1,
            "rest_of_credit_concentration_equivalised": -0.2,
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
            {"bonus_concentration_equivalised": 0.9},
            {"bonus_concentration_equivalised": -0.3},
            {"bonus_concentration": np.nan},
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
