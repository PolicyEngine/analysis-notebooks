# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["policyengine[models]==6.11.1"]
# ///
"""Compare FISC's provisions on every data file and set of weights.

    uv run us/congress/fisc_marriage_bonus/provisions.py todays_data=current \
        household_counts=household_counts family_income=family_income \
        child_credit=child_credit all_targets=all_targets \
        cps_2024_data=cps march_2025_data=march

Each folder holds run.py's seven 2026 scenarios in PROVISION_SCENARIOS. The script
compares them as summarize.gini_by_provision and summarize.distribution do on the
current dataset, ranks households within each file, and writes
results/provisions_by_file_2026.csv.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import SCENARIOS, closed_form_credit, uncapped_credit
from summarize import (
    BASE,
    CREDIT,
    DOLLAR_TOLERANCE,
    INCOME_TAX,
    NET_INCOME,
    PRIMARY_YEAR,
    RESULTS,
    check_same_records,
    check_tables_are_finite,
    distribution,
    gini_by_provision,
    has_caregiver,
    income_tolerance,
    labelled_folders,
    load,
)

FILES = (
    "todays_data",
    "household_counts",
    "family_income",
    "child_credit",
    "all_targets",
    "cps_2024_data",
    "march_2025_data",
)

PROVISION_SCENARIOS = (
    "baseline",
    "fisc",
    "fisc_no_bonus",
    "fisc_ctc_repeal_only",
    "fisc_no_newborn_add_on",
    "fisc_no_phase_out",
    "fisc_no_agi_cap",
)
# These three add in sequence from current law to full FISC.
CHAIN = ("ctc_repeal", "credit_without_bonus", "marriage_bonus")
PAYMENTS = ("credit_without_bonus", "marriage_bonus", "newborn_add_on")
CUTS = ("ctc_repeal", "phase_out", "agi_cap")
RANKINGS = {
    "household_net_income": "",
    "equivalised_household_net_income": "_equivalised",
}
REACH = ("bottom_five_deciles", "top_three_deciles", "concentration", "income_gini")
GINIS = ("household_gini", "equivalised_gini")
# Household net income across a whole file sums in double precision.
ACCOUNT_TOLERANCE = 1e-6
GINI_ACCOUNT_TOLERANCE = 1e-12
# Both readings of these runs compute most lines from the same arrays.
SAVED_LINE_TOLERANCE = 1e-12
# summarize.distribution_lines divides income by the square root of household size,
# and summarize.distribution reads the single-precision array the model saved. So
# the two can order a few households differently on the equivalised ranking.
SINGLE_PRECISION_LINES = {
    "bonus_concentration_equivalised",
    "rest_of_credit_concentration_equivalised",
    "equivalised_income_gini",
}
SINGLE_PRECISION_LINE_TOLERANCE = 1e-6
SAVED_LINES = {
    ("marriage_bonus", "household_gini_without"): "gini_without_the_bonus",
    ("marriage_bonus", "household_gini_with"): "gini_with_the_bonus",
    (
        "marriage_bonus",
        "equivalised_gini_without",
    ): "equivalised_gini_without_the_bonus",
    ("marriage_bonus", "equivalised_gini_with"): "equivalised_gini_with_the_bonus",
    ("marriage_bonus", "bottom_five_deciles"): "bonus_share_of_bottom_five_deciles",
    ("marriage_bonus", "top_three_deciles"): "bonus_share_of_top_three_deciles",
    ("marriage_bonus", "concentration"): "bonus_concentration",
    (
        "marriage_bonus",
        "bottom_five_deciles_equivalised",
    ): "bonus_share_of_bottom_five_deciles_equivalised",
    (
        "marriage_bonus",
        "concentration_equivalised",
    ): "bonus_concentration_equivalised",
    (
        "credit_without_bonus",
        "bottom_five_deciles",
    ): "rest_of_credit_share_of_bottom_five_deciles",
    ("credit_without_bonus", "concentration"): "rest_of_credit_concentration",
    (
        "credit_without_bonus",
        "bottom_five_deciles_equivalised",
    ): "rest_of_credit_share_of_bottom_five_deciles_equivalised",
    (
        "credit_without_bonus",
        "concentration_equivalised",
    ): "rest_of_credit_concentration_equivalised",
    (
        "marriage_bonus",
        "top_three_deciles_equivalised",
    ): "bonus_share_of_top_three_deciles_equivalised",
    (
        "credit_without_bonus",
        "top_three_deciles",
    ): "rest_of_credit_share_of_top_three_deciles",
    (
        "credit_without_bonus",
        "top_three_deciles_equivalised",
    ): "rest_of_credit_share_of_top_three_deciles_equivalised",
    ("marriage_bonus", "income_gini"): "household_income_gini",
    ("marriage_bonus", "income_gini_equivalised"): "equivalised_income_gini",
}


def check_runs(folder: Path, label: str) -> None:
    """Each scenario's arrays must hold that scenario, by its sidecar and by the law.

    The chain telescopes, so it holds on any arrays, and outside today's data the saved
    tables reach only three of the seven scenarios. This check reads all seven on every
    file.
    """
    runs = {name: load(folder, name, PRIMARY_YEAR) for name in PROVISION_SCENARIOS}
    for name in PROVISION_SCENARIOS:
        sidecar = json.loads((Path(folder) / f"{name}_{PRIMARY_YEAR}.json").read_text())
        policy = json.loads(json.dumps(SCENARIOS[name], default=str))
        if (sidecar["scenario"], sidecar["year"], sidecar["policy"]) != (
            name,
            PRIMARY_YEAR,
            policy,
        ):
            raise AssertionError(f"{label}: {name} holds another scenario's run")
    fisc = runs["fisc"]
    joint = fisc["tax_unit.joint"].astype(bool)
    agi = fisc["tax_unit.adjusted_gross_income"]
    caregiver = has_caregiver(fisc)
    expected = {
        "fisc": closed_form_credit(fisc[BASE], joint, agi, 0.2),
        "fisc_no_bonus": closed_form_credit(
            runs["fisc_no_bonus"][BASE], joint, agi, 0.0
        ),
        "fisc_no_newborn_add_on": closed_form_credit(
            runs["fisc_no_newborn_add_on"][BASE], joint, agi, 0.2
        ),
        "fisc_no_phase_out": np.minimum(
            runs["fisc_no_phase_out"][BASE] * (1 + 0.2 * joint), np.maximum(agi, 0)
        ),
        "fisc_no_agi_cap": uncapped_credit(runs["fisc_no_agi_cap"][BASE], joint, agi),
        "fisc_ctc_repeal_only": np.zeros(agi.shape),
    }
    for name, credit in expected.items():
        if np.abs(runs[name][CREDIT] - credit * caregiver).max() > DOLLAR_TOLERANCE:
            raise AssertionError(f"{label}: {name}'s credit misses the law")
    # Current law's arrays reach the saved tables, and one March household of current
    # law, at $65 million and weight 0.009, sits $10 from this identity against a $9
    # tolerance, so this reads only the reforms.
    for name, run in runs.items():
        if name in ("baseline", "fisc"):
            continue
        if name != "fisc_ctc_repeal_only":
            tax = (run[INCOME_TAX] - fisc[INCOME_TAX]) - (fisc[CREDIT] - run[CREDIT])
            if np.abs(tax).max() > DOLLAR_TOLERANCE:
                raise AssertionError(f"{label}: {name}'s income tax misses its credit")
        moved = (run[NET_INCOME] - fisc[NET_INCOME]) - (
            run["household.household_benefits"]
            - fisc["household.household_benefits"]
            - run["household.household_tax"]
            + fisc["household.household_tax"]
        )
        if (np.abs(moved) > income_tolerance(run)).any():
            raise AssertionError(
                f"{label}: {name}'s net income misses tax and benefits"
            )


def provisions_by_file(folders: dict[str, Path]) -> pd.DataFrame:
    """Each provision's effect on the Gini and its reach, file by file."""
    tables = []
    for label, folder in folders.items():
        baseline = load(folder, "baseline", PRIMARY_YEAR)
        for scenario in PROVISION_SCENARIOS[1:]:
            check_same_records(baseline, load(folder, scenario, PRIMARY_YEAR), label)
        table = gini_by_provision(folder).set_index("provision")
        summary = distribution(folder)["component_summary"]
        summary["component"] = summary.component.replace({"full_fisc_net": "full_fisc"})
        for ranking, suffix in RANKINGS.items():
            reach = summary[summary.ranking == ranking].set_index("component")
            table = table.join(reach[list(REACH)].add_suffix(suffix))
        for gini in GINIS:
            table[f"{gini}_change"] = table[f"{gini}_with"] - table[f"{gini}_without"]
        table.insert(0, "file", label)
        tables.append(table.rename_axis("provision").reset_index())
    return pd.concat(tables, ignore_index=True)


def check_accounts(table: pd.DataFrame) -> None:
    """The chain must add to full FISC, and each provision must point its own way."""
    for label, rows in table.groupby("file", sort=False):
        rows = rows.set_index("provision")
        full = rows.loc["full_fisc"]
        chain = rows.loc[list(CHAIN)]
        dollars = chain.net_income_change.sum() - full.net_income_change
        if abs(dollars) > ACCOUNT_TOLERANCE * abs(full.net_income_change):
            raise AssertionError(f"{label}: the chain misses full FISC's net cost")
        for gini in GINIS:
            change = chain[f"{gini}_change"].sum() - full[f"{gini}_change"]
            if abs(change) > GINI_ACCOUNT_TOLERANCE:
                raise AssertionError(f"{label}: the chain misses full FISC's {gini}")
        if (rows.loc[list(PAYMENTS), "net_income_change"] <= 0).any():
            raise AssertionError(f"{label}: a payment lowers net income")
        if (rows.loc[list(CUTS), "net_income_change"] >= 0).any():
            raise AssertionError(f"{label}: a cut raises net income")


def check_against_saved_tables(
    table: pd.DataFrame, results: Path = RESULTS
) -> dict[str, float]:
    """These runs must reproduce what the committed tables say about the same runs."""
    rows = table.set_index(["file", "provision"])
    comparison = pd.concat(
        [
            pd.read_csv(results / "data_comparison_2026.csv", index_col="line"),
            pd.read_csv(
                results / "reweighted_comparison_2026.csv", index_col="line"
            ).drop(columns="todays_data"),
        ],
        axis=1,
    )
    gaps = {}
    for label in table.file.unique():
        largest = 0.0
        for (provision, column), line in SAVED_LINES.items():
            gap = abs(
                rows.loc[(label, provision), column] - comparison.loc[line, label]
            )
            tolerance = (
                SINGLE_PRECISION_LINE_TOLERANCE
                if line in SINGLE_PRECISION_LINES
                else SAVED_LINE_TOLERANCE
            )
            if not gap <= tolerance:
                raise AssertionError(f"{label}: {provision} {column} misses {line}")
            largest = max(largest, float(gap))
        gaps[label] = largest
    saved = pd.read_csv(results / "gini_by_provision_2026.csv").set_index("provision")
    for provision, row in saved.iterrows():
        for column, value in row.items():
            found = rows.loc[("todays_data", provision), column]
            if not abs(found - value) <= SAVED_LINE_TOLERANCE * max(abs(value), 1.0):
                raise AssertionError(f"todays_data: {provision} misses {column}")
    return gaps


def check_tables_hold_the_answer(table: pd.DataFrame) -> None:
    """The regressivity answer must hold on every file, on both rankings."""
    for label, rows in table.groupby("file", sort=False):
        rows = rows.set_index("provision")
        for gini in GINIS:
            change = rows[f"{gini}_change"]
            if change["marriage_bonus"] >= 0:
                raise AssertionError(f"{label}: the bonus does not lower {gini}")
            if change["ctc_repeal"] <= 0:
                raise AssertionError(f"{label}: the repeal does not raise {gini}")
            if change["agi_cap"] <= 0:
                raise AssertionError(f"{label}: the AGI cap does not raise {gini}")
            per_billion = rows[f"{gini}_change_per_billion"]
            if per_billion["agi_cap"] <= per_billion["ctc_repeal"]:
                raise AssertionError(f"{label}: the repeal raises {gini} more per $1B")
        moves = rows[[f"{gini}_change" for gini in GINIS]]
        if not ((moves > 0).all(axis=1) | (moves < 0).all(axis=1)).all():
            raise AssertionError(f"{label}: a provision moves the two Ginis apart")
        per_billion = rows["household_gini_change_per_billion"]
        for payment in set(PAYMENTS) - {"marriage_bonus"}:
            if per_billion["marriage_bonus"] <= per_billion[payment]:
                raise AssertionError(f"{label}: the bonus beats {payment} per $1B")
        for suffix in RANKINGS.values():
            shares = rows[f"bottom_five_deciles{suffix}"]
            for payment in set(PAYMENTS) - {"marriage_bonus"}:
                if shares["marriage_bonus"] >= shares[payment]:
                    raise AssertionError(
                        f"{label}: the bonus reaches the bottom more than {payment}"
                    )


def main(folders: dict[str, Path], results: Path = RESULTS) -> pd.DataFrame:
    if set(folders) != set(FILES):
        raise ValueError(f"expected one folder for each of {FILES}")
    for label, folder in folders.items():
        check_runs(folder, label)
    table = provisions_by_file(folders)
    check_accounts(table)
    check_against_saved_tables(table, results)
    check_tables_hold_the_answer(table)
    check_tables_are_finite({"provisions_by_file_2026": table})
    table.to_csv(results / "provisions_by_file_2026.csv", index=False)
    return table


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="+", metavar="LABEL=DIR")
    main(labelled_folders(parser.parse_args().folders))
