"""Turn the local runs and API results into the tables in results/.

    uv run python us/congress/fisc_marriage_bonus/summarize.py \
        --work <work-dir> --rerun <rerun-dir> --march <march-dir> \
        --ecps <ecps-dir> --cps <cps-dir> --detail <detail-dir>

The script removes results/invariants.json first and writes every table only
after every check passes, so that file exists only for a run that passed.
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
    stepped_credit,
    uncapped_credit,
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
AGI_CAP_AT_ZERO_ONLY = 99024
FISC_CTC_REPEAL_ONLY = 99025
CURRENT_LAW = 2
REEVES_ESTIMATE = 30e9
DOLLAR_TOLERANCE = 1.0
RELATIVE_TOLERANCE = 1e-3
GINI_TOLERANCE = 1e-5
POVERTY_TOLERANCE = 1e-6
# Local and API rates agree for children and working-age adults, and the local
# rate for people 65 and over runs 8.6e-5 above the API's, cause untraced. That
# moves the all-ages rate by 1.5e-5.
SENIOR_POVERTY_TOLERANCE = 1e-4
# Reform differences match the API to the dollar, but the local and API income
# levels differ by a constant, so a few households change decile near the top.
DECILE_MEAN_TOLERANCE = 2.0
# The weights save in single precision, so their ratio carries that much noise.
WEIGHT_GROWTH_TOLERANCE = 1e-5
SAMPLING_DRAWS = 200
SAMPLING_SEED = 0
# Cells these tables leave empty on purpose: the ladder's first rungs have no
# step, the Census Bureau publishes no credit figures, and a decile row has no
# percent of negative income and no mean across zero recipients.
DECILE_BLANKS = ["percent_of_income", "mean_per_receiving_household"]
BLANK_COLUMNS = {
    "march_2025_ladder": ["step"],
    "data_comparison_2026": ["census_2023"],
    "deciles_by_component_2026": DECILE_BLANKS,
    "deciles_by_data_file_2026": DECILE_BLANKS,
}
CAREGIVER_AGE = 18
PRIMARY_YEAR = 2026
LAST_YEAR = 2035
CHECK_YEARS = (PRIMARY_YEAR, LAST_YEAR)
CREDIT = "tax_unit.family_income_supplement_credit"
BASE = "tax_unit.family_income_supplement_credit_base_amount"
HOUSEHOLD_CREDIT = "household.family_income_supplement_credit"
INCOME_TAX = "tax_unit.income_tax"
NET_INCOME = "household.household_net_income"
CHILD_AGE = 18
SENIOR_AGE = 65
# Census Bureau, America's Families and Living Arrangements: 2023, in thousands.
# Table C3: https://www2.census.gov/programs-surveys/demo/tables/families/2023/cps-2023/tabc3-all.xls
# Table FG3, opposite-sex couples: https://www2.census.gov/programs-surveys/demo/tables/families/2023/cps-2023/tabfg3-all.xls
CENSUS_2023 = {
    "children_under_18": 72_296,
    "children_with_married_parents": 48_228,
    "married_couple_family_groups": 63_869,
    "married_couple_family_groups_with_own_children": 24_040,
}


def api_result(policy: int, baseline: int, year: int) -> dict:
    return json.loads((API / f"econ_{policy}_over_{baseline}_{year}.json").read_text())


def read_arrays(path: Path) -> dict[str, np.ndarray]:
    """Read saved arrays with their floats widened, since float32 sums lose dollars."""
    saved = np.load(path)
    arrays = {
        name: saved[name].astype(float)
        if saved[name].dtype == np.float32
        else saved[name]
        for name in saved
    }
    for name, values in arrays.items():
        if np.issubdtype(values.dtype, np.floating) and not np.isfinite(values).all():
            raise AssertionError(f"{path.name}: {name} is not finite")
    return arrays


def load(work: Path, scenario: str, year: int) -> dict[str, np.ndarray]:
    return read_arrays(work / f"{scenario}_{year}.npz")


def load_detail(detail: Path, scenario: str) -> dict[str, np.ndarray]:
    """The poverty and state tax arrays run.py --detail saves beside a run."""
    return read_arrays(detail / f"{scenario}_{PRIMARY_YEAR}_detail.npz")


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
        "agi_cap_above_zero_agi": (FISC, AGI_CAP_AT_ZERO_ONLY),
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


def poverty_rates(arrays) -> dict[str, float]:
    """Share of people in SPM poverty, overall and by the API's age groups."""
    weight = arrays["person_weight"]
    in_poverty = arrays["person_in_poverty"].astype(float)
    age = arrays["age"]
    child = age < CHILD_AGE
    senior = age >= SENIOR_AGE
    groups = {
        "all": np.ones_like(child),
        "child": child,
        "adult": ~child & ~senior,
        "senior": senior,
    }
    return {
        group: float(np.average(in_poverty[member], weights=weight[member]))
        for group, member in groups.items()
    }


def rebuilt_poverty(detail: dict[str, np.ndarray]) -> np.ndarray:
    """Each person's poverty flag, from their SPM unit's income and threshold."""
    poor = pd.Series(
        detail["spm_unit_net_income"] < detail["spm_unit_spm_threshold"],
        index=detail["spm_unit_id"],
    )
    return poor.reindex(detail["person_spm_unit_id"]).to_numpy()


def spm_income_by_household(
    run: dict[str, np.ndarray], detail: dict[str, np.ndarray]
) -> np.ndarray:
    """Add SPM unit net income up to households through the person links."""
    links = pd.DataFrame(
        {
            "spm_unit": detail["person_spm_unit_id"],
            "household": run["person.person_household_id"],
        }
    ).drop_duplicates()
    if links.spm_unit.duplicated().any():
        raise AssertionError("an SPM unit spans two households")
    household = links.set_index("spm_unit").household
    totals = (
        pd.Series(
            detail["spm_unit_net_income"],
            index=household.reindex(detail["spm_unit_id"]).to_numpy(),
        )
        .groupby(level=0)
        .sum()
    )
    return totals.reindex(run["household.household_id"], fill_value=0.0).to_numpy()


def check_poverty_run(
    with_cap: dict[str, np.ndarray],
    without_cap: dict[str, np.ndarray],
    detail_with: dict[str, np.ndarray],
    detail_without: dict[str, np.ndarray],
) -> dict:
    """Tie each run's poverty flags to its incomes, and those incomes to the credit."""
    for name in ("age", "person_weight", "person_spm_unit_id", "spm_unit_id"):
        if not np.array_equal(detail_with[name], detail_without[name]):
            raise AssertionError("the poverty files hold different people")
    if not np.array_equal(
        detail_with["spm_unit_spm_threshold"], detail_without["spm_unit_spm_threshold"]
    ):
        raise AssertionError("removing the cap moved a poverty threshold")
    for detail in (detail_with, detail_without):
        if not np.array_equal(detail["person_in_poverty"], rebuilt_poverty(detail)):
            raise AssertionError("a poverty flag misses its income and threshold")

    gap = np.abs(
        (
            spm_income_by_household(without_cap, detail_without)
            - spm_income_by_household(with_cap, detail_with)
        )
        - (without_cap[NET_INCOME] - with_cap[NET_INCOME])
    )
    if gap.max() > DOLLAR_TOLERANCE:
        raise AssertionError("SPM income moved apart from household net income")

    poor_with = detail_with["person_in_poverty"]
    poor_without = detail_without["person_in_poverty"]
    if (poor_without & ~poor_with).any():
        raise AssertionError("removing the cap moved someone into poverty")
    if not (poor_with & ~poor_without).any():
        raise AssertionError("removing the cap lifted no one out of poverty")
    return {"agi_cap_largest_household_gap_from_spm_income": float(gap.max())}


def agi_cap_provision(work: Path, detail: Path) -> tuple[dict, dict]:
    """The AGI cap's row, from local runs, since no API policy removes all of it.

    Each row of provisions_2026.csv ranks deciles on income without the
    provision, so this one ranks on income in the uncapped run.
    """
    fisc = load(work, "fisc", PRIMARY_YEAR)
    uncapped = load(work, "fisc_no_agi_cap", PRIMARY_YEAR)
    weight = fisc["household.household_weight"]
    detail_with = load_detail(detail, "fisc")
    detail_without = load_detail(detail, "fisc_no_agi_cap")
    invariants = check_poverty_run(fisc, uncapped, detail_with, detail_without)
    rates_with = poverty_rates(detail_with)
    rates_without = poverty_rates(detail_without)
    api = api_result(FISC, CURRENT_LAW, PRIMARY_YEAR)["poverty"]["poverty"]
    for group, tolerance in (
        ("child", POVERTY_TOLERANCE),
        ("adult", POVERTY_TOLERANCE),
        ("senior", SENIOR_POVERTY_TOLERANCE),
        ("all", SENIOR_POVERTY_TOLERANCE),
    ):
        if abs(rates_with[group] - api[group]["reform"]) > tolerance:
            raise AssertionError("local and API poverty disagree")
    partial = api_result(FISC, AGI_CAP_AT_ZERO_ONLY, PRIMARY_YEAR)["poverty"]["poverty"]
    for group in ("all", "child"):
        if rates_without[group] > partial[group]["baseline"]:
            raise AssertionError("removing all of the cap beat removing part of it")

    def net_cost_part(run: dict[str, np.ndarray]) -> np.ndarray:
        return run["household.household_tax"] - run["household.household_benefits"]

    cost = float(((net_cost_part(uncapped) - net_cost_part(fisc)) * weight).sum())
    gini_with = household_gini(fisc)
    gini_without = household_gini(uncapped)
    change = fisc[NET_INCOME] - uncapped[NET_INCOME]
    table = decile_table(
        uncapped["household.household_income_decile"],
        change,
        uncapped[NET_INCOME],
        weight,
    ).set_index("group")
    row = {
        "provision": "agi_cap",
        "net_cost": cost,
        "gini_without": gini_without,
        "gini_with": gini_with,
        "gini_change_per_billion": (gini_with - gini_without) / abs(cost) * 1e9,
        "poverty_without": rates_without["all"],
        "poverty_with": rates_with["all"],
        "child_poverty_without": rates_without["child"],
        "child_poverty_with": rates_with["child"],
        **{f"mean_decile_{d}": table.mean_per_household[d] for d in range(1, 11)},
        **{
            f"relative_decile_{d}": table.dollars[d] / table.income_dollars[d]
            for d in range(1, 11)
        },
    }
    return row, invariants


def credit_gaps_from_the_bill(run: dict[str, np.ndarray], rate: float) -> dict:
    """Compare every tax unit's credit with the model's reading of the bill."""
    joint = run["tax_unit.joint"].astype(bool)
    agi = run["tax_unit.adjusted_gross_income"]
    weight = run["tax_unit.tax_unit_weight"]
    formula = closed_form_credit(run[BASE], joint, agi, rate)
    caregiver = has_caregiver(run)
    if (np.abs(run[CREDIT] - formula * caregiver) > DOLLAR_TOLERANCE).any():
        raise AssertionError("the credit differs from the bill's closed form")
    excluded = (run[BASE] > 0) & ~caregiver
    return {
        "tax_units_with_a_child_and_no_adult_caregiver": float(weight[excluded].sum()),
        "dollars_the_caregiver_test_removes": float((formula * weight)[excluded].sum()),
    }


def has_caregiver(run: dict[str, np.ndarray]) -> np.ndarray:
    return (
        np.maximum(run["tax_unit.age_head"], run["tax_unit.age_spouse"])
        >= CAREGIVER_AGE
    )


def household_totals(run: dict[str, np.ndarray], amount: np.ndarray) -> np.ndarray:
    """Add a tax-unit amount up to households through the person links."""
    links = pd.DataFrame(
        {
            "tax_unit": run["person.person_tax_unit_id"],
            "household": run["person.person_household_id"],
        }
    ).drop_duplicates()
    if links.tax_unit.duplicated().any():
        raise AssertionError("a tax unit spans two households")
    household = links.set_index("tax_unit").household
    totals = (
        pd.Series(
            amount, index=household.reindex(run["tax_unit.tax_unit_id"]).to_numpy()
        )
        .groupby(level=0)
        .sum()
    )
    return totals.reindex(run["household.household_id"], fill_value=0.0).to_numpy()


def check_accounting(
    reform: dict, baseline: dict, label: str, state_tax: np.ndarray
) -> dict:
    """Check two runs against each other for every tax unit and household.

    state_tax holds each tax unit's change in state income tax.
    """
    results: dict[str, object] = {}
    for entity in ("tax_unit", "household"):
        name = f"{entity}.{entity}_weight"
        if not np.array_equal(reform[name], baseline[name]):
            raise AssertionError(f"{label}: {entity} weights differ")

    credit = reform[CREDIT] - baseline[CREDIT]
    tax_gap = np.abs((baseline[INCOME_TAX] - reform[INCOME_TAX]) - credit)
    if tax_gap.max() > DOLLAR_TOLERANCE:
        raise AssertionError(f"{label}: income tax moved apart from the credit")
    results[f"{label}_largest_tax_unit_gap_from_the_credit"] = float(tax_gap.max())

    for run in (reform, baseline):
        rebuilt = household_totals(run, run[CREDIT])
        if np.abs(rebuilt - run[HOUSEHOLD_CREDIT]).max() > DOLLAR_TOLERANCE:
            raise AssertionError(f"{label}: household credit misses its tax units")

    def change(name: str) -> np.ndarray:
        return reform[name] - baseline[name]

    gap = np.abs(
        change(NET_INCOME)
        - (change("household.household_benefits") - change("household.household_tax"))
    )
    if gap.max() > DOLLAR_TOLERANCE:
        raise AssertionError(f"{label}: net income moved apart from tax and benefits")
    results[f"{label}_largest_household_gap_from_tax_and_benefits"] = float(gap.max())

    credit_by_household = household_totals(reform, reform[CREDIT]) - household_totals(
        baseline, baseline[CREDIT]
    )
    if (state_tax[credit == 0] != 0).any():
        raise AssertionError(f"{label}: state tax moved with no credit behind it")
    gap = np.abs(
        change(NET_INCOME) - (credit_by_household - household_totals(reform, state_tax))
    )
    if gap.max() > DOLLAR_TOLERANCE:
        raise AssertionError(f"{label}: net income moved apart from the credit")
    results[f"{label}_largest_household_gap_from_credit_and_state_tax"] = float(
        gap.max()
    )
    results[f"{label}_state_income_tax_change"] = float(
        (state_tax * reform["tax_unit.tax_unit_weight"]).sum()
    )
    return results


def state_tax_change(detail: Path, reform: str, baseline: str) -> np.ndarray:
    return (
        load_detail(detail, reform)["state_income_tax"]
        - load_detail(detail, baseline)["state_income_tax"]
    )


def check_agi_cap_run(work: Path, detail: Path) -> dict:
    """The uncapped run must pay the uncapped credit at every AGI."""
    fisc = load(work, "fisc", PRIMARY_YEAR)
    uncapped = load(work, "fisc_no_agi_cap", PRIMARY_YEAR)
    expected = uncapped_credit(
        uncapped[BASE],
        uncapped["tax_unit.joint"].astype(bool),
        uncapped["tax_unit.adjusted_gross_income"],
    ) * has_caregiver(uncapped)
    if np.abs(uncapped[CREDIT] - expected).max() > DOLLAR_TOLERANCE:
        raise AssertionError("the uncapped run misses the uncapped credit")
    weight = uncapped["tax_unit.tax_unit_weight"]
    at_or_below_zero = uncapped["tax_unit.adjusted_gross_income"] <= 0
    removed = (uncapped[CREDIT] - fisc[CREDIT]) * weight
    if removed[at_or_below_zero].sum() <= 0:
        raise AssertionError("the uncapped run paid nothing at zero or negative AGI")
    return {
        "credit_the_agi_cap_removes": float(removed.sum()),
        "credit_the_agi_cap_removes_at_zero_or_negative_agi": float(
            removed[at_or_below_zero].sum()
        ),
    } | check_accounting(
        uncapped, fisc, "agi_cap", state_tax_change(detail, "fisc_no_agi_cap", "fisc")
    )


def check_invariants(work: Path, rerun: Path, detail: Path) -> dict:
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
    state_tax = state_tax_change(detail, "fisc", "fisc_no_bonus")
    results |= check_accounting(fisc, no_bonus, "bonus", state_tax)

    weight = fisc["tax_unit.tax_unit_weight"]
    by_credit = float((bonus * weight).sum())
    by_tax = float(((no_bonus[INCOME_TAX] - fisc[INCOME_TAX]) * weight).sum())
    by_net_income = float(
        (
            (fisc[NET_INCOME] - no_bonus[NET_INCOME])
            * fisc["household.household_weight"]
        ).sum()
    )
    results["bonus_measured_by_the_credit"] = by_credit
    results["bonus_measured_by_income_tax"] = by_tax
    results["bonus_measured_by_net_income"] = by_net_income
    for measure in (by_tax, by_net_income):
        if abs(by_credit - measure) > RELATIVE_TOLERANCE * abs(by_credit):
            raise AssertionError("the credit and its effects disagree on the bonus")

    caregiver = has_caregiver(fisc)
    agi = fisc["tax_unit.adjusted_gross_income"]
    stepped = stepped_credit(fisc[BASE], joint, agi) * caregiver
    stepped_no_bonus = stepped_credit(no_bonus[BASE], joint, agi, 0) * caregiver
    results["credit_on_the_bills_phase_out_steps_less_the_model"] = float(
        ((stepped - fisc[CREDIT]) * weight).sum()
    )
    results["bonus_on_the_bills_phase_out_steps_less_the_model"] = float(
        ((stepped - stepped_no_bonus - bonus) * weight).sum()
    )
    return results


def check_the_decade(work: Path) -> dict:
    """The later years keep every family as it stands and scale all weights alike."""
    first = load(work, "fisc", PRIMARY_YEAR)
    last = load(work, "fisc", LAST_YEAR)
    for name in (
        "tax_unit.age_head",
        "tax_unit.age_spouse",
        "tax_unit.joint",
        BASE,
        "household.household_count_people",
    ):
        if not np.array_equal(first[name], last[name]):
            raise AssertionError(f"the later years changed {name}")
    growth = np.concatenate(
        [
            last[f"{entity}.{entity}_weight"] / first[f"{entity}.{entity}_weight"]
            for entity in ("household", "tax_unit")
        ]
    )
    if growth.max() - growth.min() > WEIGHT_GROWTH_TOLERANCE:
        raise AssertionError("the later years scaled weights unevenly")
    return {"weight_growth_from_2026_to_2035": float(growth.mean())}


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


def check_state_tax_against_api(detail: Path) -> dict:
    """The saved state income tax must add up to the API's change."""
    fisc = load_detail(detail, "fisc")
    no_bonus = load_detail(detail, "fisc_no_bonus")
    weights = np.load(detail / f"fisc_{PRIMARY_YEAR}.npz")["tax_unit.tax_unit_weight"]
    local = float(
        ((fisc["state_income_tax"] - no_bonus["state_income_tax"]) * weights).sum()
    )
    api = float(
        api_result(FISC, NO_BONUS, PRIMARY_YEAR)["detailed_budget"]["state_income_tax"][
            "difference"
        ]
    )
    if abs(local - api) > RELATIVE_TOLERANCE * abs(api):
        raise AssertionError("local and API runs disagree on state income tax")
    return {"bonus_state_income_tax_local": local, "bonus_state_income_tax_api": api}


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
        "fisc_agi_cap_at_zero_only": direct_gini(FISC, AGI_CAP_AT_ZERO_ONLY)[
            "baseline"
        ],
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


def equivalised_income(run: dict[str, np.ndarray]) -> np.ndarray:
    """The saved equivalised income, checked against its definition."""
    income = run["household.equiv_household_net_income"]
    expected = run[NET_INCOME] / np.sqrt(run["household.household_count_people"])
    if np.abs(income - expected).max() > DOLLAR_TOLERANCE:
        raise AssertionError("equivalised income misses net income and household size")
    return income


def equivalised_gini(run: dict[str, np.ndarray]) -> float:
    """Equivalised household net income across people, with negatives at zero."""
    return weighted_gini(
        np.maximum(equivalised_income(run), 0),
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
    equivalised = equivalised_income(current)
    credit = "household.family_income_supplement_credit"
    net = NET_INCOME

    person_weight = weight * people
    rankings = {
        "household_net_income": current["household.household_income_decile"],
        "equivalised_household_net_income": weighted_decile(
            equivalised, weight, people
        ),
    }

    def concentration(ranking: str, amount: np.ndarray) -> float:
        """Concentration in the units the ranking uses, as the Gini beside it does."""
        if ranking == "household_net_income":
            return concentration_coefficient(amount, income, weight)
        return concentration_coefficient(
            amount / np.sqrt(people), equivalised, person_weight
        )

    income_ginis = {
        "household_net_income": weighted_gini(income, weight),
        "equivalised_household_net_income": weighted_gini(equivalised, person_weight),
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
        for component, amount in components.items():
            table = decile_table(groups, amount, income, weight, people)
            table.insert(0, "component", component)
            table.insert(0, "ranking", ranking)
            tables.append(table)
            total = float((amount * weight).sum())
            if abs(table.dollars.sum() - total) > DOLLAR_TOLERANCE * 1e3:
                raise AssertionError(f"{component}: decile rows miss the aggregate")
            row = {
                "dollars": total,
                **group_shares(table),
                "concentration": concentration(ranking, amount),
                "income_gini": income_ginis[ranking],
            }
            if not np.isfinite(list(row.values())).all():
                raise AssertionError(f"{component}: a summary value is not finite")
            summary.append({"ranking": ranking, "component": component, **row})
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


def reconciliation(
    march: Path, ecps: Path, work: Path
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
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
    gap = (table.march_2025_stack - table.published_csv).abs().max()
    if gap > DOLLAR_TOLERANCE * 1e3:
        raise AssertionError("the March 2025 rerun misses the published CSV")

    def tax(folder: Path, scenario: str) -> float:
        return weighted_sum(load(folder, scenario, PRIMARY_YEAR), "tax_unit.income_tax")

    old_data_old_ctc = tax(ecps, "fisc") - tax(ecps, "baseline_march_2025_ctc")
    old_data_new_ctc = tax(ecps, "fisc") - tax(ecps, "baseline")
    new_data_old_ctc = tax(work, "fisc") - tax(work, "baseline_march_2025_ctc")
    start = table.loc[PRIMARY_YEAR, "march_2025_stack"]
    final = table.loc[PRIMARY_YEAR, "today"]
    ladder = pd.DataFrame(
        [
            ("published CSV", table.loc[PRIMARY_YEAR, "published_csv"], np.nan),
            ("March 2025 model, data and law, rerun", start, np.nan),
            (
                "today's model, March 2025 data, March 2025 CTC",
                old_data_old_ctc,
                old_data_old_ctc - start,
            ),
            (
                "today's model, March 2025 data, today's CTC",
                old_data_new_ctc,
                old_data_new_ctc - old_data_old_ctc,
            ),
            (
                "today's model, today's data, today's CTC",
                final,
                final - old_data_new_ctc,
            ),
        ],
        columns=["rung", "full_fisc_income_tax_2026", "step"],
    )
    # The data and baseline steps interact, so the order changes each one's size.
    orders = pd.DataFrame(
        [
            {
                "step": "CTC baseline",
                "with_march_2025_data": old_data_new_ctc - old_data_old_ctc,
                "with_todays_data": final - new_data_old_ctc,
            },
            {
                "step": "data",
                "with_march_2025_data": final - old_data_new_ctc,
                "with_todays_data": new_data_old_ctc - old_data_old_ctc,
            },
        ]
    )
    return table, ladder, orders


def children_in_joint_units(
    run: dict[str, np.ndarray], people: dict[str, np.ndarray]
) -> dict:
    """Children under 18, and the share of them in joint tax units."""
    joint = pd.Series(
        run["tax_unit.joint"].astype(bool), index=run["tax_unit.tax_unit_id"]
    )
    weight = people["person_weight"]
    child = people["age"] < CHILD_AGE
    in_joint_unit = joint.reindex(run["person.person_tax_unit_id"]).to_numpy()
    return {
        "children_under_18": float(weight[child].sum()),
        "share_of_children_in_joint_tax_units": float(
            weight[child & in_joint_unit].sum() / weight[child].sum()
        ),
    }


def bonus_by_decile(folder: Path) -> pd.DataFrame:
    """The bonus by current-law decile on one data file."""
    current = load(folder, "baseline", PRIMARY_YEAR)
    fisc = load(folder, "fisc", PRIMARY_YEAR)
    no_bonus = load(folder, "fisc_no_bonus", PRIMARY_YEAR)
    return decile_table(
        current["household.household_income_decile"],
        fisc[HOUSEHOLD_CREDIT] - no_bonus[HOUSEHOLD_CREDIT],
        current[NET_INCOME],
        current["household.household_weight"],
        current["household.household_count_people"],
    )


def deciles_by_data_file(ecps: Path, cps: Path, work: Path) -> pd.DataFrame:
    """The bonus by decile on each data file, ranked within that file."""
    return pd.concat(
        [
            bonus_by_decile(folder).assign(data_file=label)
            for label, folder in (
                ("march_2025_data", ecps),
                ("cps_2024_data", cps),
                ("todays_data", work),
            )
        ],
        ignore_index=True,
    )


def distribution_lines(folder: Path) -> dict:
    """Shares, concentration and Gini on one data file, ranked within that file."""
    current = load(folder, "baseline", PRIMARY_YEAR)
    fisc = load(folder, "fisc", PRIMARY_YEAR)
    no_bonus = load(folder, "fisc_no_bonus", PRIMARY_YEAR)
    weight = current["household.household_weight"]
    people = current["household.household_count_people"]
    income = current[NET_INCOME]
    adjusted = income / np.sqrt(people)
    person_weight = weight * people
    pieces = {
        "bonus": fisc[HOUSEHOLD_CREDIT] - no_bonus[HOUSEHOLD_CREDIT],
        "rest_of_credit": no_bonus[HOUSEHOLD_CREDIT],
    }
    lines: dict[str, float] = {
        "household_income_gini": weighted_gini(income, weight),
        "gini_without_the_bonus": household_gini(no_bonus),
        "gini_with_the_bonus": household_gini(fisc),
        "equivalised_income_gini": weighted_gini(adjusted, person_weight),
    }
    for name, amount in pieces.items():
        shares = group_shares(
            decile_table(
                current["household.household_income_decile"], amount, income, weight
            )
        )
        lines |= {
            f"{name}_share_of_bottom_five_deciles": shares["bottom_five_deciles"],
            f"{name}_share_of_top_three_deciles": shares["top_three_deciles"],
            f"{name}_concentration": concentration_coefficient(amount, income, weight),
            f"{name}_concentration_equivalised": concentration_coefficient(
                amount / np.sqrt(people), adjusted, person_weight
            ),
        }
    return lines


def sampling_spread(folder: Path) -> pd.DataFrame:
    """How far a fresh draw could move the figures on a file saved as weighted draws.

    The CPS file holds households drawn with replacement in proportion to their
    Census weights, and each saved weight counts a household's draws. Redrawing the
    same number from those households shows the spread a sample that size carries.
    """
    current = load(folder, "baseline", PRIMARY_YEAR)
    fisc = load(folder, "fisc", PRIMARY_YEAR)
    no_bonus = load(folder, "fisc_no_bonus", PRIMARY_YEAR)
    weight = current["household.household_weight"]
    people = current["household.household_count_people"]
    income = current[NET_INCOME]
    bonus = fisc[HOUSEHOLD_CREDIT] - no_bonus[HOUSEHOLD_CREDIT]
    draw_weight = weight.min()
    draws = np.rint(weight / draw_weight)
    if (np.abs(weight / draw_weight - draws) > RELATIVE_TOLERANCE).any():
        raise AssertionError("the saved weights do not count draws")
    generator = np.random.default_rng(SAMPLING_SEED)
    redraws = generator.multinomial(
        int(draws.sum()), draws / draws.sum(), size=SAMPLING_DRAWS
    )

    def lines(redrawn: np.ndarray) -> dict[str, float]:
        groups = weighted_decile(income, redrawn, people)
        shares = group_shares(decile_table(groups, bonus, income, redrawn))
        return {
            "bonus": float((bonus * redrawn).sum()),
            "bonus_share_of_bottom_five_deciles": shares["bottom_five_deciles"],
            "bonus_share_of_top_three_deciles": shares["top_three_deciles"],
        }

    spread = pd.DataFrame([lines(draw_weight * counts) for counts in redraws])
    return (
        pd.DataFrame(
            {
                "saved_file": pd.Series(lines(weight)),
                "standard_deviation": spread.std(),
                "lowest_redraw": spread.min(),
                "highest_redraw": spread.max(),
            }
        )
        .rename_axis("line")
        .reset_index()
    )


def data_comparison(ecps: Path, cps: Path, work: Path, detail: Path) -> pd.DataFrame:
    """The same model and reform on each data file, against the Census Bureau."""
    columns = {}
    for label, folder, person_file in (
        ("march_2025_data", ecps, ecps / f"fisc_{PRIMARY_YEAR}_people.npz"),
        ("cps_2024_data", cps, cps / f"fisc_{PRIMARY_YEAR}_people.npz"),
        ("todays_data", work, detail / f"fisc_{PRIMARY_YEAR}_detail.npz"),
    ):
        fisc = load(folder, "fisc", PRIMARY_YEAR)
        no_bonus = load(folder, "fisc_no_bonus", PRIMARY_YEAR)
        weight = no_bonus["tax_unit.tax_unit_weight"]
        joint = no_bonus["tax_unit.joint"].astype(bool)
        base = no_bonus[BASE]
        joint_base = float((base * weight)[joint].sum())
        columns[label] = {
            "tax_units": float(weight.sum()),
            "joint_tax_units": float(weight[joint].sum()),
            "tax_units_with_a_child": float(weight[base > 0].sum()),
            "joint_tax_units_with_a_child": float(weight[(base > 0) & joint].sum()),
            "base_amount": float((base * weight).sum()),
            "joint_base_amount": joint_base,
            "joint_share_of_base_amount": joint_base / float((base * weight).sum()),
            "statutory_bonus": STATUTORY_BONUS_RATE * joint_base,
            "bonus": float(((fisc[CREDIT] - no_bonus[CREDIT]) * weight).sum()),
            "credit": float((fisc[CREDIT] * weight).sum()),
            **children_in_joint_units(fisc, read_arrays(person_file)),
            **distribution_lines(folder),
        }
    columns["census_2023"] = {
        "joint_tax_units": 1e3 * CENSUS_2023["married_couple_family_groups"],
        "joint_tax_units_with_a_child": 1e3
        * CENSUS_2023["married_couple_family_groups_with_own_children"],
        "children_under_18": 1e3 * CENSUS_2023["children_under_18"],
        "share_of_children_in_joint_tax_units": CENSUS_2023[
            "children_with_married_parents"
        ]
        / CENSUS_2023["children_under_18"],
    }
    return pd.DataFrame(columns).rename_axis("line").reset_index()


def check_the_answer_on_every_file(table: pd.DataFrame) -> dict:
    """The regressivity answer must hold on each data file, on both rankings."""
    lines = table.set_index("line")
    results = {}
    for label in ("march_2025_data", "cps_2024_data", "todays_data"):
        column = lines[label].dropna()
        if len(column) < len(lines[label]) or not np.isfinite(column).all():
            raise AssertionError(f"{label}: a line is not finite")
        if column["gini_with_the_bonus"] >= column["gini_without_the_bonus"]:
            raise AssertionError(f"{label}: the bonus does not narrow the Gini")
        for income_gini, suffix in (
            ("household_income_gini", ""),
            ("equivalised_income_gini", "_equivalised"),
        ):
            bonus = column[f"bonus_concentration{suffix}"]
            if bonus >= column[income_gini]:
                raise AssertionError(f"{label}: the bonus concentrates above income")
            if bonus <= column[f"rest_of_credit_concentration{suffix}"]:
                raise AssertionError(f"{label}: the bonus reaches lower than the rest")
        if (
            column["bonus_share_of_bottom_five_deciles"]
            >= column["rest_of_credit_share_of_bottom_five_deciles"]
        ):
            raise AssertionError(f"{label}: the bonus reaches lower than the rest")
        results[f"{label}_gini_change_with_the_bonus"] = float(
            column["gini_with_the_bonus"] - column["gini_without_the_bonus"]
        )
    return results


def check_tables_are_finite(tables: dict[str, pd.DataFrame]) -> None:
    """Every numeric cell must hold a number, apart from the ones left blank."""
    for name, table in tables.items():
        numbers = table.drop(columns=BLANK_COLUMNS.get(name, [])).select_dtypes(
            "number"
        )
        if not np.isfinite(numbers.to_numpy(dtype=float)).all():
            raise AssertionError(f"{name}: a cell is not finite")


def main(
    work: Path, rerun: Path, march: Path, ecps: Path, cps: Path, detail: Path
) -> None:
    marker = RESULTS / "invariants.json"
    marker.unlink(missing_ok=True)
    invariants = (
        check_invariants(work, rerun, detail)
        | check_agi_cap_run(work, detail)
        | check_against_api(work)
        | check_state_tax_against_api(detail)
        | check_the_decade(work)
    )
    comparison = data_comparison(ecps, cps, work, detail)
    invariants |= check_the_answer_on_every_file(comparison)
    years, ladder, orders = reconciliation(march, ecps, work)
    agi_cap_row, poverty_invariants = agi_cap_provision(work, detail)
    invariants |= poverty_invariants
    provisions = pd.concat(
        [provision_comparison(), pd.DataFrame([agi_cap_row])],
        ignore_index=True,
    )
    indexed = {"budget_by_year": budget_by_year(), "march_2025_comparison": years}
    plain = {
        "poverty_2026": poverty_effects(),
        "provisions_2026": provisions,
        **{f"{name}_2026": table for name, table in distribution(work).items()},
        "gini_by_provision_2026": gini_by_provision(work),
        "bonus_reach_2026": bonus_reach(work),
        "versus_reeves_estimate": versus_reeves(work),
        "march_2025_ladder": ladder,
        "march_2025_step_orders": orders,
        "data_comparison_2026": comparison,
        "deciles_by_data_file_2026": deciles_by_data_file(ecps, cps, work),
        "cps_sampling_spread_2026": sampling_spread(cps),
    }
    check_tables_are_finite(indexed | plain)
    for name, table in indexed.items():
        table.to_csv(RESULTS / f"{name}.csv")
    for name, table in plain.items():
        table.to_csv(RESULTS / f"{name}.csv", index=False)
    provenance = json.loads((work / f"fisc_{PRIMARY_YEAR}.json").read_text())["bundle"]
    (RESULTS / "provenance.json").write_text(
        json.dumps(provenance, indent=1, sort_keys=True)
    )
    marker.write_text(json.dumps(invariants, indent=1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--rerun", type=Path, required=True)
    parser.add_argument("--march", type=Path, required=True)
    parser.add_argument("--ecps", type=Path, required=True)
    parser.add_argument("--cps", type=Path, required=True)
    parser.add_argument("--detail", type=Path, required=True)
    args = parser.parse_args()
    main(args.work, args.rerun, args.march, args.ecps, args.cps, args.detail)
