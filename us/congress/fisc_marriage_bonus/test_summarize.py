"""Tests for summarize.py on small synthetic runs, with no model or microdata.

The arrays below are made up to exercise the checks. No number here reaches
results/.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

import summarize
from analysis import closed_form_credit, weighted_decile
from summarize import (
    BASE,
    CREDIT,
    HOUSEHOLD_CREDIT,
    INCOME_TAX,
    NET_INCOME,
    PRIMARY_YEAR,
    REWEIGHTED_SCENARIOS,
    bonus_gap_from_api,
    bonus_reach,
    check_comparison_file,
    check_detail_runs,
    check_invariants,
    check_poverty_run,
    check_reweighted_run,
    check_state_tax_against_api,
    check_tables_are_finite,
    check_the_answer_on_every_file,
    check_the_decade,
    data_comparison,
    deciles_by_data_file,
    distribution,
    equivalised_gini,
    gini_by_provision,
    household_totals,
    income_tolerance,
    load,
    main,
    reweighted_decade,
    rescaled_draws,
    sampling_spread,
    spm_unit_totals,
    versus_reeves,
    weight_factor_summary,
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
        "household.household_income_decile": weighted_decile(
            0.9 * agi + credit + ctc, np.full(N, 1_000.0), 2 + index % 3
        ),
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
        "is_tax_unit_head": np.ones(N, dtype=bool),
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
        without_cap[INCOME_TAX][0] -= 13_000
        return (
            with_cap,
            without_cap,
            fake_detail(with_cap),
            fake_detail(without_cap),
        )

    def test_a_lift_the_income_explains_passes(self):
        results = check_poverty_run(*self.runs())
        assert results["agi_cap_largest_spm_unit_gap_from_taxes"] == 0

    def test_a_flag_the_income_does_not_explain_fails(self):
        with_cap, without_cap, detail, detail_without = self.runs()
        detail_without["person_in_poverty"] = np.zeros(N, dtype=bool)
        with pytest.raises(AssertionError, match="misses its income"):
            check_poverty_run(with_cap, without_cap, detail, detail_without)

    def test_income_with_no_tax_cut_behind_it_fails(self):
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
        without_cap[INCOME_TAX][above] += (
            without_cap[NET_INCOME][above] - FAKE_POVERTY_THRESHOLD + 1
        )
        without_cap[NET_INCOME][above] = FAKE_POVERTY_THRESHOLD - 1
        with pytest.raises(AssertionError, match="into poverty"):
            check_poverty_run(with_cap, without_cap, detail, fake_detail(without_cap))

    def test_income_moved_between_spm_units_in_one_household_fails(self):
        with_cap, without_cap, detail, detail_without = self.runs()
        for run in (with_cap, without_cap):
            run["person.person_household_id"][2] = 1
        detail_without["spm_unit_net_income"][1] += 500
        detail_without["spm_unit_net_income"][2] -= 500
        with pytest.raises(AssertionError, match="SPM income moved apart"):
            check_poverty_run(with_cap, without_cap, detail, detail_without)

    def test_a_person_with_no_tax_unit_fails(self):
        run = {
            "tax_unit.tax_unit_id": np.array([7]),
            "person.person_tax_unit_id": np.array([7, 9]),
        }
        detail = {
            "is_tax_unit_head": np.array([True, True]),
            "person_spm_unit_id": np.array([1, 1]),
            "spm_unit_id": np.array([1]),
        }
        with pytest.raises(AssertionError, match="no tax unit"):
            spm_unit_totals(run, detail, np.array([100.0]))

    def test_a_tax_unit_counts_in_its_heads_spm_unit(self):
        run = {
            "tax_unit.tax_unit_id": np.array([7, 8]),
            "person.person_tax_unit_id": np.array([7, 7, 8]),
        }
        detail = {
            "is_tax_unit_head": np.array([False, True, True]),
            "person_spm_unit_id": np.array([1, 2, 2]),
            "spm_unit_id": np.array([1, 2]),
        }
        assert spm_unit_totals(run, detail, np.array([100.0, 5.0])).tolist() == [
            0.0,
            105.0,
        ]

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

    def test_a_blank_outside_its_cell_fails(self):
        ladder = pd.DataFrame({"rung": list("abc"), "step": [np.nan, np.nan, np.nan]})
        with pytest.raises(AssertionError, match="a cell in step"):
            check_tables_are_finite({"march_2025_ladder": ladder})

    def test_a_number_in_a_blank_cell_fails(self):
        ladder = pd.DataFrame({"rung": ["start"], "step": [1.0]})
        with pytest.raises(AssertionError, match="a cell in step"):
            check_tables_are_finite({"march_2025_ladder": ladder})

    def test_infinity_in_a_column_with_blanks_fails(self):
        ladder = pd.DataFrame({"rung": list("abc"), "step": [np.nan, np.nan, np.inf]})
        with pytest.raises(AssertionError, match="a cell in step"):
            check_tables_are_finite({"march_2025_ladder": ladder})

    def test_a_column_of_nones_fails(self):
        table = pd.DataFrame({"a": [None, None]}, dtype=object)
        with pytest.raises(AssertionError, match="not a number"):
            check_tables_are_finite({"table": table})

    def test_a_number_saved_as_text_fails(self):
        table = pd.DataFrame({"a": ["1.0", "inf"]})
        with pytest.raises(AssertionError, match="not a number"):
            check_tables_are_finite({"table": table})

    def test_a_number_in_a_text_column_fails(self):
        table = pd.DataFrame({"rung": ["start", 1.0]})
        with pytest.raises(AssertionError, match="rung is not text"):
            check_tables_are_finite({"march_2025_ladder": table})

    def test_a_decile_row_blanks_only_what_it_cannot_divide(self):
        table = pd.DataFrame(
            {
                "income_dollars": [-5.0, 5.0],
                "households_receiving": [1.0, 0.0],
                "percent_of_income": [np.nan, 1.0],
                "mean_per_receiving_household": [1.0, np.nan],
            }
        )
        check_tables_are_finite({"deciles_by_data_file_2026": table})
        table.loc[1, "percent_of_income"] = np.nan
        with pytest.raises(AssertionError, match="percent_of_income"):
            check_tables_are_finite({"deciles_by_data_file_2026": table})

    def test_a_census_cell_outside_the_census_lines_fails(self):
        table = pd.DataFrame(
            {"line": ["children_under_18", "bonus"], "census_2023": [1.0, 2.0]}
        )
        with pytest.raises(AssertionError, match="census_2023"):
            check_tables_are_finite({"data_comparison_2026": table})


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

    def test_reordered_tax_units_fail(self, runs):
        work, _ = runs
        run = self.grown()
        run["tax_unit.tax_unit_id"] = run["tax_unit.tax_unit_id"][::-1]
        self.later(work, run)
        with pytest.raises(AssertionError, match="changed tax_unit.tax_unit_id"):
            check_the_decade(work)

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


class TestComparisonFile:
    def test_a_zeroed_baseline_income_tax_raises(self, runs):
        work, _ = runs
        run = load(work, "baseline", PRIMARY_YEAR)
        # Household tax falls under FISC, as it does in the real runs.
        run["household.household_tax"] = (
            load(work, "fisc", PRIMARY_YEAR)["household.household_tax"] + 1_000.0
        )
        run[INCOME_TAX] = np.zeros(N)
        save(work, "baseline", run)
        with pytest.raises(AssertionError, match="moved apart"):
            check_comparison_file(work, "file")

    def test_consistent_runs_pass(self, runs):
        work, _ = runs
        result = check_comparison_file(work, "file")
        assert result["file_bonus_measured_by_the_credit"] > 0

    def test_a_household_bonus_missing_its_tax_units_fails(self, runs):
        work, _ = runs
        fisc = fake_run(0.2)
        fisc[HOUSEHOLD_CREDIT] = fisc[HOUSEHOLD_CREDIT] * 1.5
        save(work, "fisc", fisc)
        with pytest.raises(AssertionError, match="misses its tax units"):
            check_comparison_file(work, "file")

    def test_a_credit_off_the_closed_form_fails(self, runs):
        work, _ = runs
        fisc = fake_run(0.2)
        married = np.flatnonzero(fisc["tax_unit.joint"] & (fisc[BASE] > 0))[0]
        fisc[CREDIT][married] += 100
        save(work, "fisc", fisc)
        with pytest.raises(AssertionError, match="closed form"):
            check_comparison_file(work, "file")

    def test_a_baseline_with_other_weights_fails(self, runs):
        work, _ = runs
        current = fake_run(0.0, ctc=500.0)
        current["household.household_weight"] = np.full(N, 2_000.0)
        save(work, "baseline", current)
        with pytest.raises(AssertionError, match="differs between runs"):
            check_comparison_file(work, "file")

    def test_a_swapped_baseline_decile_fails(self, runs):
        work, _ = runs
        current = fake_run(0.0, ctc=500.0)
        deciles = current["household.household_income_decile"]
        low, high = deciles.argmin(), deciles.argmax()
        deciles[[low, high]] = deciles[[high, low]]
        save(work, "baseline", current)
        with pytest.raises(AssertionError, match="a saved decile misses its income"):
            check_comparison_file(work, "file")

    def test_a_baseline_equivalised_income_off_its_definition_fails(self, runs):
        work, _ = runs
        current = fake_run(0.0, ctc=500.0)
        current["household.equiv_household_net_income"] = (
            current["household.equiv_household_net_income"] + 10
        )
        save(work, "baseline", current)
        with pytest.raises(AssertionError, match="equivalised income misses"):
            check_comparison_file(work, "file")

    def test_net_income_with_no_credit_behind_it_fails(self, runs):
        work, _ = runs
        fisc = fake_run(0.2)
        fisc[NET_INCOME] = fisc[NET_INCOME] + 1_000
        fisc["household.household_benefits"] = (
            fisc["household.household_benefits"] + 1_000
        )
        save(work, "fisc", fisc)
        with pytest.raises(AssertionError, match="disagree"):
            check_comparison_file(work, "file")


class TestIncomeTolerance:
    @staticmethod
    def save_a_rich_household(work, gap):
        """Household 0 holds $148 million and almost no weight, as in the March file."""
        for scenario, rate, ctc, income in (
            ("baseline", 0.0, 500.0, 148_000_000.0),
            ("fisc", 0.2, 0.0, 148_000_000.0),
            ("fisc_no_bonus", 0.0, 0.0, 148_000_000.0 + gap),
        ):
            run = fake_run(rate, ctc=ctc)
            run[NET_INCOME][0] = income
            run["household.household_weight"][0] = 0.001
            people = run["household.household_count_people"]
            run["household.equiv_household_net_income"] = run[NET_INCOME] / np.sqrt(
                people
            )
            run["household.household_income_decile"] = weighted_decile(
                run[NET_INCOME], run["household.household_weight"], people
            )
            save(work, scenario, run)

    def test_a_rounding_step_at_a_very_large_income_passes(self, runs):
        work, _ = runs
        self.save_a_rich_household(work, 24.0)
        check_comparison_file(work, "file")

    def test_a_larger_gap_at_that_income_fails(self, runs):
        work, _ = runs
        self.save_a_rich_household(work, 40.0)
        with pytest.raises(AssertionError, match="tax and benefits"):
            check_comparison_file(work, "file")

    def test_a_saved_equivalised_income_may_round_at_a_very_large_income(self, runs):
        work, _ = runs
        self.save_a_rich_household(work, 24.0)
        current = load(work, "baseline", PRIMARY_YEAR)
        current["household.equiv_household_net_income"][0] += 8.0
        save(work, "baseline", current)
        check_comparison_file(work, "file")

    def test_a_dollar_holds_at_ordinary_incomes(self):
        run = fake_run(0.2)
        assert income_tolerance(run).max() < 1.1


class TestRecords:
    def test_changed_person_links_fail(self, runs):
        work, _ = runs
        fisc = fake_run(0.2)
        fisc["person.person_household_id"] = fisc["person.person_household_id"][::-1]
        save(work, "fisc", fisc)
        with pytest.raises(AssertionError, match="person_household_id"):
            check_comparison_file(work, "file")

    def test_a_tax_unit_with_no_person_fails(self):
        run = fake_run(0.2)
        run["person.person_tax_unit_id"] = np.zeros(N, dtype=int)
        run["person.person_household_id"] = np.zeros(N, dtype=int)
        with pytest.raises(AssertionError, match="no person link"):
            household_totals(run, run[CREDIT])


class TestDetailRuns:
    def test_a_detail_run_that_differs_fails(self, runs, tmp_path):
        work, _ = runs
        detail = tmp_path / "detail"
        detail.mkdir()
        for scenario in ("fisc", "fisc_no_bonus", "fisc_no_agi_cap"):
            save(detail, scenario, load(work, scenario, PRIMARY_YEAR))
        check_detail_runs(work, detail)
        broken = load(work, "fisc", PRIMARY_YEAR)
        broken["tax_unit.tax_unit_weight"][0] += 1
        save(detail, "fisc", broken)
        with pytest.raises(AssertionError, match="detail run of fisc"):
            check_detail_runs(work, detail)


class TestStateTaxAgainstApi:
    def test_a_nan_weight_fails(self, runs):
        work, _ = runs
        fisc = fake_run(0.2)
        fisc["tax_unit.tax_unit_weight"][0] = np.nan
        save(work, "fisc", fisc)
        with pytest.raises(AssertionError, match="not finite"):
            check_state_tax_against_api(work, work)


class TestRescaledDraws:
    def test_person_rows_reach_the_original_total(self):
        counts = np.array([2.0, 0.0, 1.0])
        people = np.array([1.0, 4.0, 3.0])
        weights = rescaled_draws(counts, people, 100.0)
        assert (weights * people).sum() == pytest.approx(100.0)
        assert weights.tolist() == pytest.approx([40.0, 0.0, 20.0])


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
            main(
                work,
                rerun,
                work,
                work,
                work,
                work,
                {"set": work},
                {"set": work},
                {"set": work},
            )
        assert list(results.iterdir()) == []

    def test_a_nan_invariant_writes_nothing(self, runs, tmp_path, monkeypatch):
        work, rerun = runs
        results = tmp_path / "results"
        results.mkdir()
        monkeypatch.setattr(summarize, "RESULTS", results)
        for name in (
            "check_detail_runs",
            "check_invariants",
            "check_agi_cap_run",
            "check_against_api",
            "check_state_tax_against_api",
            "check_comparison_file",
            "check_reweighted_run",
            "check_the_answer_on_every_file",
            "check_tables_are_finite",
        ):
            monkeypatch.setattr(summarize, name, lambda *args: {})
        monkeypatch.setattr(
            summarize, "check_the_decade", lambda folder: {"bad": float("nan")}
        )
        empty = pd.DataFrame()
        for name in (
            "budget_by_year",
            "poverty_effects",
            "provision_comparison",
            "gini_by_provision",
            "bonus_reach",
            "versus_reeves",
            "data_comparison",
            "reweighted_comparison",
            "reweighted_decades",
            "deciles_by_data_file",
            "deciles_by_weights",
            "sampling_spread",
            "weight_factor_summary",
        ):
            monkeypatch.setattr(summarize, name, lambda *args: empty)
        monkeypatch.setattr(
            summarize, "budget_by_year", lambda: pd.DataFrame({"bonus_income_tax": []})
        )
        monkeypatch.setattr(summarize, "distribution", lambda folder: {})
        monkeypatch.setattr(
            summarize, "reconciliation", lambda *args: (empty, empty, empty)
        )
        monkeypatch.setattr(summarize, "agi_cap_provision", lambda *args: ({}, {}))
        with pytest.raises(ValueError, match="not JSON compliant"):
            main(
                work,
                rerun,
                work,
                work,
                work,
                work,
                {"set": work},
                {"set": work},
                {"set": work},
            )
        assert list(results.iterdir()) == []


FACTOR = 1.5
BUNDLE = {"model_version": "2.2.1"}


def at_factor(run, factor=FACTOR):
    """A run whose household and tax unit weights moved by one factor."""
    return run | {
        "household.household_weight": run["household.household_weight"] * factor,
        "tax_unit.tax_unit_weight": run["tax_unit.tax_unit_weight"] * factor,
    }


@pytest.fixture
def reweighted_run(runs, tmp_path):
    work, _ = runs
    folder = tmp_path / "reweighted"
    folder.mkdir()
    for scenario in REWEIGHTED_SCENARIOS:
        save(folder, scenario, at_factor(load(work, scenario, PRIMARY_YEAR)))
    factors = tmp_path / "factors.npz"
    np.savez(
        factors,
        household_id=load(work, "fisc", PRIMARY_YEAR)["household.household_id"],
        factor=np.full(N, FACTOR),
    )
    return work, folder, factors


class TestReweightedRun:
    def test_the_current_run_at_its_factors_passes(self, reweighted_run):
        check_reweighted_run(*reweighted_run, "set")

    def test_a_decile_may_move_with_the_weights(self, reweighted_run):
        work, folder, factors = reweighted_run
        run = load(folder, "fisc", PRIMARY_YEAR)
        run["household.household_income_decile"] = np.roll(
            run["household.household_income_decile"], 1
        )
        save(folder, "fisc", run)
        check_reweighted_run(work, folder, factors, "set")

    def test_an_income_that_moved_raises(self, reweighted_run):
        work, folder, factors = reweighted_run
        run = load(folder, "fisc", PRIMARY_YEAR)
        run[NET_INCOME] = run[NET_INCOME] + 1.0
        save(folder, "fisc", run)
        with pytest.raises(AssertionError, match="differs in"):
            check_reweighted_run(work, folder, factors, "set")

    def test_a_zeroed_baseline_raises(self, reweighted_run):
        work, folder, factors = reweighted_run
        run = load(folder, "baseline", PRIMARY_YEAR)
        run[INCOME_TAX] = np.zeros(N)
        save(folder, "baseline", run)
        with pytest.raises(AssertionError, match="differs in"):
            check_reweighted_run(work, folder, factors, "set")

    def test_another_sets_weights_raise(self, reweighted_run):
        work, folder, factors = reweighted_run
        current = load(work, "fisc_no_bonus", PRIMARY_YEAR)
        save(folder, "fisc_no_bonus", at_factor(current, 1.25))
        with pytest.raises(AssertionError, match="missed the factors"):
            check_reweighted_run(work, folder, factors, "set")

    def test_a_tax_unit_weight_left_behind_raises(self, reweighted_run):
        work, folder, factors = reweighted_run
        run = load(folder, "fisc", PRIMARY_YEAR)
        run["tax_unit.tax_unit_weight"] = run["tax_unit.tax_unit_weight"] / FACTOR
        save(folder, "fisc", run)
        with pytest.raises(AssertionError, match="tax_unit_weight"):
            check_reweighted_run(work, folder, factors, "set")

    def test_factors_for_other_households_raise(self, reweighted_run):
        work, folder, factors = reweighted_run
        np.savez(
            factors,
            household_id=np.arange(N)[::-1],
            factor=np.full(N, FACTOR),
        )
        with pytest.raises(AssertionError, match="other households"):
            check_reweighted_run(work, folder, factors, "set")

    def test_a_run_that_dropped_an_array_raises(self, reweighted_run):
        work, folder, factors = reweighted_run
        run = load(folder, "fisc", PRIMARY_YEAR)
        del run["tax_unit.age_head"]
        save(folder, "fisc", run)
        with pytest.raises(AssertionError, match="dropped an array"):
            check_reweighted_run(work, folder, factors, "set")


class TestWeightFactors:
    def test_a_uniform_factor_keeps_the_effective_sample(self, reweighted_run):
        work, _, factors = reweighted_run
        table = weight_factor_summary(work, {"set": factors}).set_index("weights")
        assert table.loc["set", "largest_factor"] == FACTOR
        assert table.loc["set", "smallest_factor"] == FACTOR
        assert table.loc["set", "effective_sample_of_households"] == pytest.approx(
            table.loc["todays_data", "effective_sample_of_households"]
        )

    def test_one_heavy_household_shrinks_the_effective_sample(self, reweighted_run):
        work, _, factors = reweighted_run
        household_ids = load(work, "fisc", PRIMARY_YEAR)["household.household_id"]
        heavy = np.ones(N)
        heavy[0] = 50.0
        np.savez(factors, household_id=household_ids, factor=heavy)
        table = weight_factor_summary(work, {"set": factors}).set_index("weights")
        assert table.loc["set", "largest_factor"] == 50
        assert (
            table.loc["set", "effective_sample_of_households"]
            < (table.loc["todays_data", "effective_sample_of_households"])
        )

    def test_factors_for_other_households_raise(self, reweighted_run):
        work, _, factors = reweighted_run
        np.savez(factors, household_id=np.arange(N)[::-1], factor=np.ones(N))
        with pytest.raises(AssertionError, match="other households"):
            weight_factor_summary(work, {"set": factors})


class TestReweightedDecade:
    @pytest.fixture
    def decade(self, reweighted_run, tmp_path):
        work, full, factors = reweighted_run
        (work / f"fisc_{PRIMARY_YEAR}.json").write_text(json.dumps({"bundle": BUNDLE}))
        for scenario in ("fisc", "fisc_no_bonus"):
            arrays = load(work, scenario, PRIMARY_YEAR)
            np.savez(work / f"{scenario}_{summarize.LAST_YEAR}.npz", **arrays)
        folder = tmp_path / "decade"
        folder.mkdir()

        def totals(scenario, scale=FACTOR):
            run = load(work, scenario, PRIMARY_YEAR)
            weight = run["tax_unit.tax_unit_weight"] * scale
            return {
                "family_income_supplement_credit": float(run[CREDIT] @ weight),
                "income_tax": float(run[INCOME_TAX] @ weight),
            }

        def save_year(file_year, **changes):
            record = {
                "year": file_year,
                "bundle": BUNDLE,
                "factors_sha256": hashlib.sha256(factors.read_bytes()).hexdigest(),
                "totals": {
                    "fisc": totals("fisc"),
                    "fisc_no_bonus": totals("fisc_no_bonus"),
                },
            }
            (folder / f"decade_{file_year}.json").write_text(
                json.dumps(record | changes)
            )

        for year in summarize.YEARS:
            save_year(year)
        bonus = (
            totals("fisc")["family_income_supplement_credit"]
            - totals("fisc_no_bonus")["family_income_supplement_credit"]
        )
        return work, full, folder, factors, bonus, totals, save_year

    @staticmethod
    def current_bonus(bonus):
        return pd.Series(bonus / FACTOR, index=summarize.YEARS)

    def table(self, decade):
        work, full, folder, factors, bonus, *_ = decade
        return reweighted_decade(folder, full, work, factors, self.current_bonus(bonus))

    def test_the_window_sums_each_year_and_starts_at_the_full_run(self, decade):
        bonus = decade[4]
        table = self.table(decade)
        assert table.loc[PRIMARY_YEAR, "bonus"] == pytest.approx(bonus)
        assert table.loc["2026-2035", "bonus"] == pytest.approx(10 * bonus)
        assert table.loc["2026-2035", "income_tax_change"] == pytest.approx(-10 * bonus)

    def test_a_first_year_off_the_full_run_raises(self, decade):
        full = decade[1]
        run = load(full, "fisc", PRIMARY_YEAR)
        run[CREDIT] = run[CREDIT] * 1.01
        save(full, "fisc", run)
        with pytest.raises(AssertionError, match="disagree on 2026"):
            self.table(decade)

    def test_income_tax_that_misses_the_credit_raises(self, decade):
        *_, totals, save_year = decade
        fisc = totals("fisc")
        fisc["income_tax"] += 0.1 * decade[4]
        save_year(2030, totals={"fisc": fisc, "fisc_no_bonus": totals("fisc_no_bonus")})
        with pytest.raises(AssertionError, match="income tax disagree"):
            self.table(decade)

    def test_a_file_that_holds_another_year_raises(self, decade):
        decade[-1](2031, year=2030)
        with pytest.raises(AssertionError, match="holds 2030"):
            self.table(decade)

    def test_a_year_from_another_bundle_raises(self, decade):
        decade[-1](2031, bundle={"model_version": "2.2.0"})
        with pytest.raises(AssertionError, match="another bundle"):
            self.table(decade)

    @pytest.mark.parametrize("scale", [1.0, 1.25, 0.0])
    @pytest.mark.parametrize(
        ("year", "message"),
        [(2033, "strays from"), (2035, "misses the current run")],
    )
    def test_a_year_at_other_weights_raises(self, decade, scale, year, message):
        *_, totals, save_year = decade
        save_year(
            year,
            totals={
                "fisc": totals("fisc", scale),
                "fisc_no_bonus": totals("fisc_no_bonus", scale),
            },
        )
        with pytest.raises(AssertionError, match=message):
            self.table(decade)

    @pytest.mark.parametrize(
        ("year", "message"),
        [(2033, "strays from"), (2035, "misses the current run")],
    )
    def test_a_year_with_its_two_runs_swapped_raises(self, decade, year, message):
        *_, totals, save_year = decade
        save_year(
            year,
            totals={
                "fisc": totals("fisc_no_bonus"),
                "fisc_no_bonus": totals("fisc"),
            },
        )
        with pytest.raises(AssertionError, match=message):
            self.table(decade)

    def test_a_year_a_little_past_the_margin_raises(self, decade):
        save_year = decade[-1]
        run_fisc = decade[5]("fisc")
        run_fisc["family_income_supplement_credit"] += 0.01 * decade[4]
        run_fisc["income_tax"] -= 0.01 * decade[4]
        save_year(
            2033,
            totals={"fisc": run_fisc, "fisc_no_bonus": decade[5]("fisc_no_bonus")},
        )
        with pytest.raises(AssertionError, match="strays from"):
            self.table(decade)

    def test_factors_for_other_households_raise(self, decade):
        factors, save_year = decade[3], decade[-1]
        np.savez(factors, household_id=np.arange(N)[::-1], factor=np.full(N, FACTOR))
        for year in summarize.YEARS:
            save_year(year)
        with pytest.raises(AssertionError, match="other households"):
            self.table(decade)

    @pytest.mark.parametrize("recorded", ["0" * 64, None])
    def test_a_year_run_on_other_factors_raises(self, decade, recorded):
        # Another set's factors can give a ratio inside the margin, so only the
        # file's hash tells the years apart.
        decade[-1](2031, factors_sha256=recorded)
        with pytest.raises(AssertionError, match="other factors"):
            self.table(decade)

    def test_a_nan_factor_raises_before_any_comparison(self, decade):
        factors, save_year = decade[3], decade[-1]
        factor = np.full(N, FACTOR)
        factor[0] = np.nan
        np.savez(factors, household_id=np.arange(N), factor=factor)
        for year in summarize.YEARS:
            save_year(year)
        with pytest.raises(ValueError, match="finite and positive"):
            self.table(decade)

    def test_an_end_year_bonus_off_by_under_one_percent_raises(self, decade):
        # Moving the credit and income tax together leaves each scenario's
        # totals inside the tolerance while the bonus moves 0.8%.
        *_, totals, save_year = decade
        fisc = totals("fisc")
        shift = 0.008 * decade[4]
        assert shift < summarize.RELATIVE_TOLERANCE * min(
            abs(fisc["family_income_supplement_credit"]), abs(fisc["income_tax"])
        )
        fisc["family_income_supplement_credit"] += shift
        fisc["income_tax"] -= shift
        save_year(2035, totals={"fisc": fisc, "fisc_no_bonus": totals("fisc_no_bonus")})
        with pytest.raises(AssertionError, match="bonus misses"):
            self.table(decade)

    def test_each_set_keeps_its_own_rows_and_text_years(self, decade):
        work, full, folder, factors, bonus, *_ = decade
        table = summarize.reweighted_decades(
            {"one": folder, "two": folder},
            {"one": full, "two": full},
            work,
            {"one": factors, "two": factors},
            self.current_bonus(bonus),
        )
        assert set(table.weights) == {"one", "two"}
        assert (table.year == "2026-2035").sum() == 2
        assert table.year.map(type).eq(str).all()
        summed = table[(table.weights == "two") & (table.year == "2026-2035")]
        assert summed.bonus.item() == pytest.approx(10 * bonus)

    def test_a_label_with_no_weights_raises(self, decade):
        work, full, folder, factors, bonus, *_ = decade
        with pytest.raises(KeyError):
            summarize.reweighted_decades(
                {"one": folder},
                {"two": full},
                work,
                {"one": factors},
                self.current_bonus(bonus),
            )

    def test_a_missing_year_raises(self, decade):
        folder = decade[2]
        (folder / "decade_2031.json").unlink()
        with pytest.raises(FileNotFoundError):
            self.table(decade)


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

    def test_only_units_the_bonus_pays_count_as_receiving(self, runs):
        work, _ = runs
        table = bonus_reach(work)
        assert (table.units_receiving_the_bonus <= table.joint_units_with_a_child).all()
        assert ((table.bonus > 0) <= (table.units_receiving_the_bonus > 0)).all()

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

    def test_each_file_reports_the_income_tax_full_fisc_gives_up(self, table, runs):
        work, _ = runs
        baseline = load(work, "baseline", PRIMARY_YEAR)
        fisc = load(work, "fisc", PRIMARY_YEAR)
        given_up = baseline["tax_unit.income_tax"] - fisc["tax_unit.income_tax"]
        expected = float((fisc["tax_unit.tax_unit_weight"] * given_up).sum())
        assert expected != 0
        for column in ("march_2025_data", "cps_2024_data", "todays_data"):
            assert table[column]["full_fisc_income_tax"] == pytest.approx(expected)

    def test_the_child_share_counts_children_in_joint_units(self, table):
        share = table["todays_data"]["share_of_children_in_joint_tax_units"]
        assert share == pytest.approx(1.0)

    @staticmethod
    def answer(**changes):
        lines = {
            "gini_with_the_bonus": 0.46,
            "gini_without_the_bonus": 0.47,
            "equivalised_gini_with_the_bonus": 0.44,
            "equivalised_gini_without_the_bonus": 0.45,
            "bonus_concentration": 0.1,
            "household_income_gini": 0.47,
            "equivalised_income_gini": 0.45,
            "rest_of_credit_concentration": 0.0,
            "bonus_concentration_equivalised": -0.1,
            "rest_of_credit_concentration_equivalised": -0.2,
            "bonus_share_of_bottom_five_deciles": 0.4,
            "rest_of_credit_share_of_bottom_five_deciles": 0.5,
            "bonus_share_of_bottom_five_deciles_equivalised": 0.55,
            "rest_of_credit_share_of_bottom_five_deciles_equivalised": 0.65,
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
            {"bonus_share_of_bottom_five_deciles_equivalised": 0.7},
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
