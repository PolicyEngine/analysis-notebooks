"""Turn the local runs and API results into the tables in results/.

    uv run python us/congress/fisc_marriage_bonus/summarize.py \
        --work <work-dir> --rerun <rerun-dir> --march <march-dir> --ecps <ecps-dir>

A failed invariant raises before results/invariants.json lands, so that file
exists only when the runs passed every check.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import (
    STATUTORY_BONUS_RATE,
    YEARS,
    bonus_lost_to_limits,
    closed_form_credit,
    concentration_coefficient,
    decile_table,
    group_shares,
    weighted_decile,
    weighted_gini,
)

HERE = Path(__file__).parent
RESULTS = HERE / "results"
API = RESULTS / "api"
MARCH_2025_CSV = HERE.parent / "fisc_act_10_year_impact.csv"
FISC = 76612
NO_BONUS = 99021
NO_NEWBORN_ADD_ON = 99022
NO_PHASE_OUT = 99023
NO_AGI_CAP = 99024
FISC_CTC_REPEAL_ONLY = 99025
CURRENT_LAW = 2
REEVES_ESTIMATE = 30e9
DOLLAR_TOLERANCE = 1.0
RELATIVE_TOLERANCE = 1e-3
GINI_TOLERANCE = 1e-5
# Reform differences match the API to the dollar, but the local and API income
# levels differ by a constant, so a few households change decile near the top.
DECILE_MEAN_TOLERANCE = 2.0
CAREGIVER_AGE = 18
PRIMARY_YEAR = 2026
CHECK_YEARS = (2026, 2035)
CREDIT = "tax_unit.family_income_supplement_credit"
BASE = "tax_unit.family_income_supplement_credit_base_amount"
NET_INCOME = "household.household_net_income"


def api_result(policy: int, baseline: int, year: int) -> dict:
    return json.loads((API / f"econ_{policy}_over_{baseline}_{year}.json").read_text())


def load(work: Path, scenario: str, year: int) -> dict[str, np.ndarray]:
    """Read a run with its floats widened, since float32 sums lose dollars."""
    arrays = np.load(work / f"{scenario}_{year}.npz")
    return {
        name: arrays[name].astype(float)
        if arrays[name].dtype == np.float32
        else arrays[name]
        for name in arrays
    }


def weighted_sum(run: dict[str, np.ndarray], name: str) -> float:
    entity = name.split(".")[0]
    return float((run[name] * run[f"{entity}.{entity}_weight"]).sum())


def budget_by_year() -> pd.DataFrame:
    rows = []
    for year in YEARS:
        full = api_result(FISC, CURRENT_LAW, year)
        no_bonus = api_result(NO_BONUS, CURRENT_LAW, year)
        direct = api_result(FISC, NO_BONUS, year)
        rows.append(
            {
                "year": year,
                "full_fisc": full["budget"]["budgetary_impact"],
                "fisc_no_bonus": no_bonus["budget"]["budgetary_impact"],
                "bonus_as_difference": full["budget"]["budgetary_impact"]
                - no_bonus["budget"]["budgetary_impact"],
                "bonus_direct": direct["budget"]["budgetary_impact"],
                "bonus_income_tax": direct["detailed_budget"]["income_tax"][
                    "difference"
                ],
                "bonus_state_income_tax": direct["detailed_budget"]["state_income_tax"][
                    "difference"
                ],
                "bonus_benefits": direct["budget"]["benefit_spending_impact"],
                "full_fisc_income_tax": full["detailed_budget"]["income_tax"][
                    "difference"
                ],
            }
        )
    table = pd.DataFrame(rows).set_index("year")
    table.loc["2026-2035"] = table.sum()
    return table


def poverty_effects() -> pd.DataFrame:
    rows = []
    comparisons = {
        "full_fisc_over_current_law": (FISC, CURRENT_LAW),
        "fisc_no_bonus_over_current_law": (NO_BONUS, CURRENT_LAW),
        "bonus_over_fisc_no_bonus": (FISC, NO_BONUS),
    }
    for label, (policy, baseline) in comparisons.items():
        poverty = api_result(policy, baseline, PRIMARY_YEAR)["poverty"]["poverty"]
        for group in ("all", "child"):
            rows.append(
                {
                    "comparison": label,
                    "group": group,
                    "baseline_rate": poverty[group]["baseline"],
                    "reform_rate": poverty[group]["reform"],
                }
            )
    return pd.DataFrame(rows)


def provision_comparison() -> pd.DataFrame:
    """Each provision's production API results for 2026, with and without it.

    The repeal and the credit add up in sequence from current law. The other
    three rows remove one provision from the full reform. Each row ranks deciles
    on income without the provision, and each reform dollar raises net income.
    """
    provisions = {
        "ctc_repeal": (FISC_CTC_REPEAL_ONLY, CURRENT_LAW),
        "credit_without_bonus": (NO_BONUS, FISC_CTC_REPEAL_ONLY),
        "marriage_bonus": (FISC, NO_BONUS),
        "newborn_add_on": (FISC, NO_NEWBORN_ADD_ON),
        "phase_out": (FISC, NO_PHASE_OUT),
        "agi_cap": (FISC, NO_AGI_CAP),
        "full_fisc": (FISC, CURRENT_LAW),
    }
    rows = []
    for provision, (policy, baseline) in provisions.items():
        result = api_result(policy, baseline, PRIMARY_YEAR)
        gini = result["inequality"]["gini"]
        poverty = result["poverty"]["poverty"]
        relative = result["decile"]["relative"]
        average = result["decile"]["average"]
        cost = -result["budget"]["budgetary_impact"]
        rows.append(
            {
                "provision": provision,
                "net_cost": cost,
                "gini_without": gini["baseline"],
                "gini_with": gini["reform"],
                "gini_change_per_billion": (gini["reform"] - gini["baseline"])
                / abs(cost)
                * 1e9,
                "poverty_without": poverty["all"]["baseline"],
                "poverty_with": poverty["all"]["reform"],
                "child_poverty_without": poverty["child"]["baseline"],
                "child_poverty_with": poverty["child"]["reform"],
                **{f"mean_decile_{d}": average[str(d)] for d in range(1, 11)},
                **{f"relative_decile_{d}": relative[str(d)] for d in range(1, 11)},
            }
        )
    return pd.DataFrame(rows)


def credit_gaps_from_the_bill(run: dict[str, np.ndarray], rate: float) -> dict:
    """Compare every tax unit's credit with H.R. 1308 Sec. 2(d) at a bonus rate."""
    joint = run["tax_unit.joint"].astype(bool)
    agi = run["tax_unit.adjusted_gross_income"]
    weight = run["tax_unit.tax_unit_weight"]
    formula = closed_form_credit(run[BASE], joint, agi, rate)
    adults = np.maximum(run["tax_unit.age_head"], run["tax_unit.age_spouse"])
    caregiver = adults >= CAREGIVER_AGE
    if (np.abs(run[CREDIT] - formula * caregiver) > DOLLAR_TOLERANCE).any():
        raise AssertionError("the credit differs from the bill's closed form")
    excluded = (run[BASE] > 0) & ~caregiver
    return {
        "tax_units_with_a_child_and_no_adult_caregiver": float(weight[excluded].sum()),
        "dollars_the_caregiver_test_removes": float((formula * weight)[excluded].sum()),
    }


def check_invariants(work: Path, rerun: Path) -> dict:
    fisc = load(work, "fisc", PRIMARY_YEAR)
    no_bonus = load(work, "fisc_no_bonus", PRIMARY_YEAR)
    restored = load(work, "fisc_restored_bonus", PRIMARY_YEAR)
    repeat = load(rerun, "fisc_no_bonus", PRIMARY_YEAR)
    joint = fisc["tax_unit.joint"].astype(bool)
    bonus = fisc[CREDIT] - no_bonus[CREDIT]
    results: dict[str, object] = {}

    for name in fisc:
        if not np.array_equal(fisc[name], restored[name]):
            raise AssertionError(f"restoring the bonus changed {name}")
    results["restoring_the_bonus_reproduces_full_fisc"] = True

    for name in no_bonus:
        if not np.array_equal(no_bonus[name], repeat[name]):
            raise AssertionError(f"a rerun changed {name}")
    results["reruns_are_identical"] = True

    if (bonus[~joint] != 0).any():
        raise AssertionError("an unmarried tax unit received the bonus")
    results["unmarried_units_with_a_bonus"] = 0

    if (bonus < -DOLLAR_TOLERANCE).any():
        raise AssertionError("the bonus lowered a credit")
    if (no_bonus[CREDIT] > no_bonus[BASE] + DOLLAR_TOLERANCE).any():
        raise AssertionError("a credit exceeds its base amount with the bonus at zero")
    results["no_bonus_units_above_their_base_amount"] = 0

    results |= credit_gaps_from_the_bill(fisc, STATUTORY_BONUS_RATE)
    credit_gaps_from_the_bill(no_bonus, 0.0)

    weight = fisc["tax_unit.tax_unit_weight"]
    by_credit = float((bonus * weight).sum())
    by_tax = float(
        ((no_bonus["tax_unit.income_tax"] - fisc["tax_unit.income_tax"]) * weight).sum()
    )
    by_net_income = float(
        (
            (fisc[NET_INCOME] - no_bonus[NET_INCOME])
            * fisc["household.household_weight"]
        ).sum()
    )
    results["bonus_measured_by_the_credit"] = by_credit
    results["bonus_measured_by_income_tax"] = by_tax
    results["bonus_measured_by_net_income"] = by_net_income
    if abs(by_credit - by_tax) > RELATIVE_TOLERANCE * abs(by_credit):
        raise AssertionError("the credit and income tax disagree on the bonus")
    return results


def bonus_gap_from_api(work: Path, year: int) -> dict:
    """Compare one year's bonus with the API and check who receives it."""
    fisc = load(work, "fisc", year)
    no_bonus = load(work, "fisc_no_bonus", year)
    bonus = fisc[CREDIT] - no_bonus[CREDIT]
    if (bonus[~fisc["tax_unit.joint"].astype(bool)] != 0).any():
        raise AssertionError(f"an unmarried tax unit received the bonus in {year}")
    local = float(
        (
            (no_bonus["tax_unit.income_tax"] - fisc["tax_unit.income_tax"])
            * fisc["tax_unit.tax_unit_weight"]
        ).sum()
    )
    api = -float(
        api_result(FISC, NO_BONUS, year)["detailed_budget"]["income_tax"]["difference"]
    )
    if abs(local - api) > RELATIVE_TOLERANCE * abs(api):
        raise AssertionError(f"local and API runs disagree on the {year} bonus")
    return {f"bonus_local_{year}": local, f"bonus_api_{year}": api}


def check_against_api(work: Path) -> dict:
    """Differential check: the local runs against the production API."""
    current = load(work, "baseline", PRIMARY_YEAR)
    fisc = load(work, "fisc", PRIMARY_YEAR)
    no_bonus = load(work, "fisc_no_bonus", PRIMARY_YEAR)
    results: dict[str, object] = {}

    direct = api_result(FISC, NO_BONUS, PRIMARY_YEAR)
    for year in CHECK_YEARS:
        results |= bonus_gap_from_api(work, year)

    comparisons = {
        "bonus_over_fisc_no_bonus": (fisc, no_bonus, direct),
        "full_fisc_over_current_law": (
            fisc,
            current,
            api_result(FISC, CURRENT_LAW, PRIMARY_YEAR),
        ),
    }
    for label, (reform, baseline, api) in comparisons.items():
        table = decile_table(
            baseline["household.household_income_decile"],
            reform[NET_INCOME] - baseline[NET_INCOME],
            baseline[NET_INCOME],
            baseline["household.household_weight"],
        ).set_index("group")
        gaps = [
            abs(
                table.mean_per_household[decile] - api["decile"]["average"][str(decile)]
            )
            for decile in range(1, 11)
        ]
        results[f"{label}_largest_decile_mean_gap_dollars"] = float(max(gaps))
        if max(gaps) > DECILE_MEAN_TOLERANCE:
            raise AssertionError(f"{label}: local and API decile means disagree")

    api_gini = {
        "baseline": direct_gini(FISC, CURRENT_LAW)["baseline"],
        "fisc": direct_gini(FISC, CURRENT_LAW)["reform"],
        "fisc_no_bonus": direct_gini(FISC, NO_BONUS)["baseline"],
        "fisc_no_newborn_add_on": direct_gini(FISC, NO_NEWBORN_ADD_ON)["baseline"],
        "fisc_no_phase_out": direct_gini(FISC, NO_PHASE_OUT)["baseline"],
        "fisc_no_agi_cap": direct_gini(FISC, NO_AGI_CAP)["baseline"],
    }
    gaps = {
        scenario: abs(household_gini(load(work, scenario, PRIMARY_YEAR)) - reported)
        for scenario, reported in api_gini.items()
    }
    results["largest_gini_gap"] = float(max(gaps.values()))
    if max(gaps.values()) > GINI_TOLERANCE:
        raise AssertionError(f"local and API Gini disagree: {gaps}")
    return results


def direct_gini(policy: int, baseline: int) -> dict:
    return api_result(policy, baseline, PRIMARY_YEAR)["inequality"]["gini"]


def household_gini(run: dict[str, np.ndarray]) -> float:
    """Household net income across households: the Gini the production API reports."""
    return weighted_gini(run[NET_INCOME], run["household.household_weight"])


def equivalised_gini(run: dict[str, np.ndarray]) -> float:
    """Equivalised household net income across people, with negatives at zero."""
    return weighted_gini(
        np.maximum(run["household.equiv_household_net_income"], 0),
        run["household.household_weight"] * run["household.household_count_people"],
    )


def gini_by_provision(work: Path) -> pd.DataFrame:
    """Each provision's effect on both Gini measures, from the local runs."""
    provisions = {
        "ctc_repeal": ("fisc_ctc_repeal_only", "baseline"),
        "credit_without_bonus": ("fisc_no_bonus", "fisc_ctc_repeal_only"),
        "marriage_bonus": ("fisc", "fisc_no_bonus"),
        "newborn_add_on": ("fisc", "fisc_no_newborn_add_on"),
        "phase_out": ("fisc", "fisc_no_phase_out"),
        "agi_cap": ("fisc", "fisc_no_agi_cap"),
        "full_fisc": ("fisc", "baseline"),
    }
    rows = []
    for provision, (with_it, without_it) in provisions.items():
        reform = load(work, with_it, PRIMARY_YEAR)
        baseline = load(work, without_it, PRIMARY_YEAR)
        dollars = float(
            (
                (reform[NET_INCOME] - baseline[NET_INCOME])
                * baseline["household.household_weight"]
            ).sum()
        )
        household_change = household_gini(reform) - household_gini(baseline)
        equivalised_change = equivalised_gini(reform) - equivalised_gini(baseline)
        rows.append(
            {
                "provision": provision,
                "net_income_change": dollars,
                "household_gini_without": household_gini(baseline),
                "household_gini_with": household_gini(reform),
                "household_gini_change_per_billion": household_change
                / abs(dollars)
                * 1e9,
                "equivalised_gini_without": equivalised_gini(baseline),
                "equivalised_gini_with": equivalised_gini(reform),
                "equivalised_gini_change_per_billion": equivalised_change
                / abs(dollars)
                * 1e9,
            }
        )
    return pd.DataFrame(rows)


def bonus_reach(work: Path) -> pd.DataFrame:
    """How marriage and the limits shape the bonus in each current-law decile.

    The person links carry each tax unit to its household's decile.
    """
    current = load(work, "baseline", PRIMARY_YEAR)
    fisc = load(work, "fisc", PRIMARY_YEAR)
    no_bonus = load(work, "fisc_no_bonus", PRIMARY_YEAR)
    links = pd.DataFrame(
        {
            "tax_unit": no_bonus["person.person_tax_unit_id"],
            "household": no_bonus["person.person_household_id"],
        }
    ).drop_duplicates()
    if links.tax_unit.duplicated().any():
        raise AssertionError("a tax unit spans two households")
    household = links.set_index("tax_unit").household
    decile = pd.Series(
        current["household.household_income_decile"],
        index=current["household.household_id"],
    )
    weight = no_bonus["tax_unit.tax_unit_weight"]
    joint = no_bonus["tax_unit.joint"].astype(bool)
    base = no_bonus[BASE]
    to_phase_out, to_cap = bonus_lost_to_limits(
        base, joint, no_bonus["tax_unit.adjusted_gross_income"]
    )
    frame = pd.DataFrame(
        {
            "decile": decile.reindex(
                household.reindex(no_bonus["tax_unit.tax_unit_id"]).to_numpy()
            ).to_numpy(),
            "units_with_a_child": weight * (base > 0),
            "joint_units_with_a_child": weight * ((base > 0) & joint),
            "base_amount": weight * base,
            "joint_base_amount": weight * base * joint,
            "statutory_bonus": weight * base * joint * STATUTORY_BONUS_RATE,
            "bonus_lost_to_phase_out": weight * to_phase_out,
            "bonus_lost_to_agi_cap": weight * to_cap,
            "bonus": weight * (fisc[CREDIT] - no_bonus[CREDIT]),
        }
    )
    table = frame.groupby("decile").sum()
    table["joint_share_of_units_with_a_child"] = (
        table.joint_units_with_a_child / table.units_with_a_child
    )
    table["joint_share_of_base_amount"] = table.joint_base_amount / table.base_amount
    table["share_of_statutory_bonus_paid"] = table.bonus / table.statutory_bonus
    return table.reset_index()


def distribution(work: Path) -> dict[str, pd.DataFrame]:
    current = load(work, "baseline", PRIMARY_YEAR)
    fisc = load(work, "fisc", PRIMARY_YEAR)
    no_bonus = load(work, "fisc_no_bonus", PRIMARY_YEAR)
    weight = current["household.household_weight"]
    people = current["household.household_count_people"]
    income = current["household.household_net_income"]
    equivalised = current["household.equiv_household_net_income"]
    credit = "household.family_income_supplement_credit"
    net = NET_INCOME

    rankings = {
        "household_net_income": current["household.household_income_decile"],
        "equivalised_household_net_income": weighted_decile(
            equivalised, weight, people
        ),
    }
    components = {
        "marriage_bonus": fisc[credit] - no_bonus[credit],
        "credit_without_bonus": no_bonus[credit],
        "ctc_repeal": load(work, "fisc_ctc_repeal_only", PRIMARY_YEAR)[net]
        - current[net],
        "full_fisc_net": fisc[net] - current[net],
        "newborn_add_on": fisc[net]
        - load(work, "fisc_no_newborn_add_on", PRIMARY_YEAR)[net],
        "phase_out": fisc[net] - load(work, "fisc_no_phase_out", PRIMARY_YEAR)[net],
        "agi_cap": fisc[net] - load(work, "fisc_no_agi_cap", PRIMARY_YEAR)[net],
    }

    tables = []
    summary = []
    for ranking, groups in rankings.items():
        rank_income = income if ranking == "household_net_income" else equivalised
        gini = concentration_coefficient(income, rank_income, weight, people)
        for component, amount in components.items():
            table = decile_table(groups, amount, income, weight)
            table.insert(0, "component", component)
            table.insert(0, "ranking", ranking)
            tables.append(table)
            total = float((amount * weight).sum())
            if abs(table.dollars.sum() - total) > DOLLAR_TOLERANCE * 1e3:
                raise AssertionError(f"{component}: decile rows miss the aggregate")
            summary.append(
                {
                    "ranking": ranking,
                    "component": component,
                    "dollars": total,
                    **group_shares(table),
                    "concentration": concentration_coefficient(
                        amount, rank_income, weight, people
                    ),
                    "income_concentration": gini,
                }
            )
    return {
        "deciles_by_component": pd.concat(tables, ignore_index=True),
        "component_summary": pd.DataFrame(summary),
    }


def versus_reeves(work: Path) -> pd.DataFrame:
    fisc = load(work, "fisc", PRIMARY_YEAR)
    no_bonus = load(work, "fisc_no_bonus", PRIMARY_YEAR)
    weight = no_bonus["tax_unit.tax_unit_weight"]
    joint = no_bonus["tax_unit.joint"].astype(bool)
    bonus = float(((fisc[CREDIT] - no_bonus[CREDIT]) * weight).sum())
    joint_credit = float((no_bonus[CREDIT] * weight)[joint].sum())
    all_credit = float((no_bonus[CREDIT] * weight).sum())
    # The bonus applies to the base amount before the phase-out and cap, so the
    # joint base amount bounds it and the joint credit does not.
    joint_base = float((no_bonus[BASE] * weight)[joint].sum())
    all_base = float((no_bonus[BASE] * weight).sum())
    rows = {
        "reeves_estimate": REEVES_ESTIMATE,
        "base_that_estimate_implies_at_20_percent": REEVES_ESTIMATE
        / STATUTORY_BONUS_RATE,
        "base_amount_all_filers": all_base,
        "base_amount_joint_filers": joint_base,
        "joint_share_of_base_amount": joint_base / all_base,
        "twenty_percent_of_joint_base_amount": STATUTORY_BONUS_RATE * joint_base,
        "credit_without_bonus_all_filers": all_credit,
        "credit_without_bonus_joint_filers": joint_credit,
        "joint_share_of_credit_without_bonus": joint_credit / all_credit,
        "twenty_percent_of_joint_credit": STATUTORY_BONUS_RATE * joint_credit,
        "modelled_bonus": bonus,
        "modelled_bonus_less_reeves_estimate": bonus - REEVES_ESTIMATE,
    }
    return pd.Series(rows, name="value").rename_axis("line").reset_index()


def reconciliation(march: Path, ecps: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    published = pd.read_csv(MARCH_2025_CSV, index_col=0)["Static Impact"]

    def stack(year: int, scenario: str) -> dict:
        return json.loads((march / f"{scenario}_{year}.json").read_text())

    rows = []
    for year in CHECK_YEARS:
        base = stack(year, "baseline")
        full = stack(year, "fisc")
        zero = stack(year, "fisc_no_bonus")
        rows.append(
            {
                "year": year,
                "published_csv": float(published.loc[year]),
                "march_2025_stack": full["income_tax"] - base["income_tax"],
                "march_2025_bonus": full["income_tax"] - zero["income_tax"],
                "march_2025_credit": full["family_income_supplement_credit"],
                "march_2025_ctc_repealed": base["ctc"],
                "today": api_result(FISC, CURRENT_LAW, year)["detailed_budget"][
                    "income_tax"
                ]["difference"],
                "today_bonus": api_result(FISC, NO_BONUS, year)["detailed_budget"][
                    "income_tax"
                ]["difference"],
            }
        )
    table = pd.DataFrame(rows).set_index("year")

    tax = "tax_unit.income_tax"
    full = weighted_sum(load(ecps, "fisc", PRIMARY_YEAR), tax)
    zero = weighted_sum(load(ecps, "fisc_no_bonus", PRIMARY_YEAR), tax)
    old_ctc = weighted_sum(load(ecps, "baseline_march_2025_ctc", PRIMARY_YEAR), tax)
    new_ctc = weighted_sum(load(ecps, "baseline", PRIMARY_YEAR), tax)
    start = table.loc[PRIMARY_YEAR, "march_2025_stack"]
    model_step = full - old_ctc
    baseline_step = full - new_ctc
    final = table.loc[PRIMARY_YEAR, "today"]
    ladder = pd.DataFrame(
        [
            ("published CSV", table.loc[PRIMARY_YEAR, "published_csv"], np.nan),
            ("March 2025 model, data and law, rerun", start, np.nan),
            (
                "today's model, March 2025 data, March 2025 CTC",
                model_step,
                model_step - start,
            ),
            (
                "today's model, March 2025 data, today's CTC",
                baseline_step,
                baseline_step - model_step,
            ),
            ("today's model, today's data, today's CTC", final, final - baseline_step),
        ],
        columns=["rung", "full_fisc_income_tax_2026", "step"],
    )
    ladder.attrs["ecps_bonus"] = full - zero
    return table, ladder


def main(work: Path, rerun: Path, march: Path, ecps: Path) -> None:
    budget_by_year().to_csv(RESULTS / "budget_by_year.csv")
    poverty_effects().to_csv(RESULTS / "poverty_2026.csv", index=False)
    provision_comparison().to_csv(RESULTS / "provisions_2026.csv", index=False)
    invariants = check_invariants(work, rerun) | check_against_api(work)
    for name, table in distribution(work).items():
        table.to_csv(RESULTS / f"{name}_2026.csv", index=False)
    gini_by_provision(work).to_csv(RESULTS / "gini_by_provision_2026.csv", index=False)
    bonus_reach(work).to_csv(RESULTS / "bonus_reach_2026.csv", index=False)
    versus_reeves(work).to_csv(RESULTS / "versus_reeves_estimate.csv", index=False)
    years, ladder = reconciliation(march, ecps)
    years.to_csv(RESULTS / "march_2025_comparison.csv")
    ladder.to_csv(RESULTS / "march_2025_ladder.csv", index=False)
    invariants["bonus_on_march_2025_data_with_todays_model"] = ladder.attrs[
        "ecps_bonus"
    ]
    (RESULTS / "invariants.json").write_text(json.dumps(invariants, indent=1))
    provenance = json.loads((work / f"fisc_{PRIMARY_YEAR}.json").read_text())["bundle"]
    (RESULTS / "provenance.json").write_text(
        json.dumps(provenance, indent=1, sort_keys=True)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--rerun", type=Path, required=True)
    parser.add_argument("--march", type=Path, required=True)
    parser.add_argument("--ecps", type=Path, required=True)
    args = parser.parse_args()
    main(args.work, args.rerun, args.march, args.ecps)
