# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["policyengine[models]==6.11.1"]
# ///
"""Compare the model's joint filing with the filing status the dataset records.

    uv run us/congress/fisc_marriage_bonus/filing_roles.py <work-dir>

The dataset records each tax unit's filing status and each person's role in it,
and policyengine-us 2.2.1 reads neither (PolicyEngine/policyengine-us#9868). This
reads both from the file named in <work-dir>/fisc_2026.json, checks its sha256,
and sets them beside the 2026 runs. It writes results/filing_roles_2026.csv: the
units the model files jointly and the file does not, the bonus they receive, and
the units the file lists as joint and the model does not.

The reverse line asks what the model would pay those units at its own base amounts
and AGI, so it does not take back a base amount the model gives a person the file
calls a spouse. The net is a diagnostic, not a corrected estimate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from analysis import STATUTORY_BONUS_RATE, closed_form_credit
from relationship import dataset_path, sha256

RESULTS = Path(__file__).parent / "results"
CREDIT = "tax_unit.family_income_supplement_credit"
BASE = "tax_unit.family_income_supplement_credit_base_amount"
# The file's statuses for a married couple, joint or apart.
MARRIED_IN_FILE = ("JOINT", "SEPARATE")
# CPS A_MARITL: 7 means never married.
NEVER_MARRIED = 7


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order]) / weights.sum()
    return float(values[order][np.searchsorted(cumulative, 0.5)])


def model_roles(people: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """The tax unit head and spouse policyengine-us 2.2.1 picks, in people's order.

    is_tax_unit_head takes the oldest adult, and is_tax_unit_spouse the oldest
    adult left, unless anyone in the unit has separated. Ties go to the person the
    dataset lists first, as get_rank's sort keeps them.
    """
    adult = people["age"].to_numpy() >= 18
    order = pd.DataFrame(
        {
            "unit": people["person_tax_unit_id"].to_numpy(),
            "older_first": -people["age"].to_numpy(),
            "row": np.arange(len(people)),
        }
    )[adult].sort_values(["unit", "older_first", "row"], kind="stable")
    rank = np.full(len(people), -1)
    rank[order["row"].to_numpy()] = order.groupby("unit").cumcount().to_numpy()
    separated = (
        people["is_separated"]
        .astype(bool)
        .groupby(people["person_tax_unit_id"])
        .transform("any")
        .to_numpy()
    )
    return rank == 0, (rank == 1) & ~separated


def filing_roles(
    units: pd.DataFrame,
    people: pd.DataFrame,
    fisc: dict[str, np.ndarray],
    no_bonus: dict[str, np.ndarray],
) -> dict[str, float]:
    """Lines for the units where the model's joint filing departs from the file's."""
    if not np.array_equal(
        units["tax_unit_id"].to_numpy(), fisc["tax_unit.tax_unit_id"]
    ):
        raise ValueError("the dataset lists other tax units or another order")
    status = units["filing_status_input"].to_numpy(dtype=str)
    joint = fisc["tax_unit.joint"].astype(bool)
    weight = fisc["tax_unit.tax_unit_weight"].astype(float)
    bonus = fisc[CREDIT].astype(float) - no_bonus[CREDIT].astype(float)
    model_only = joint & ~np.isin(status, MARRIED_IN_FILE)
    file_only = ~joint & (status == "JOINT")

    unit_ids = fisc["tax_unit.tax_unit_id"]
    _, spouse = model_roles(people)
    spouses = people[spouse & people["person_tax_unit_id"].isin(unit_ids[model_only])]
    spouse_age = pd.Series(
        fisc["tax_unit.age_spouse"].astype(float), index=unit_ids
    ).loc[spouses["person_tax_unit_id"]]
    if spouses.shape[0] != model_only.sum() or not np.array_equal(
        spouses["age"].to_numpy(dtype=float), spouse_age.to_numpy()
    ):
        raise ValueError("the spouses picked here differ from the run's")

    base = fisc[BASE].astype(float)
    income = fisc["tax_unit.adjusted_gross_income"].astype(float)
    every_unit_joint = np.ones(base.size, dtype=bool)
    bonus_if_joint = closed_form_credit(
        base, every_unit_joint, income, STATUTORY_BONUS_RATE
    ) - closed_form_credit(base, every_unit_joint, income, 0.0)
    model_only_bonus = float(weight @ (bonus * model_only))
    # Holds the model's base amounts and AGI, so it does not repair the roles.
    file_only_bonus = float(weight @ (bonus_if_joint * file_only))
    return {
        "joint_in_model_not_in_file_records": float(model_only.sum()),
        "joint_in_model_not_in_file_weight": float(weight @ model_only),
        "joint_in_model_not_in_file_bonus": model_only_bonus,
        "their_spouse_never_married_records": float(
            (spouses["A_MARITL"] == NEVER_MARRIED).sum()
        ),
        "their_spouse_weighted_median_age": weighted_median(
            fisc["tax_unit.age_spouse"].astype(float)[model_only], weight[model_only]
        ),
        "joint_in_file_not_in_model_records": float(file_only.sum()),
        "joint_in_file_not_in_model_weight": float(weight @ file_only),
        "joint_in_file_not_in_model_bonus_if_joint": file_only_bonus,
        "net_bonus_the_model_adds": model_only_bonus - file_only_bonus,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("--out", type=Path, default=RESULTS / "filing_roles_2026.csv")
    args = parser.parse_args()
    bundle = json.loads((args.work / "fisc_2026.json").read_text())["bundle"]
    path = dataset_path(bundle)
    if sha256(path) != bundle["runtime_dataset_sha256"]:
        raise ValueError(f"{path} is not the run's dataset")
    units = pd.read_hdf(
        path, "tax_unit", columns=["tax_unit_id", "filing_status_input"]
    )
    people = pd.read_hdf(
        path,
        "person",
        columns=["person_tax_unit_id", "is_separated", "A_MARITL", "age"],
    )

    def load(scenario: str) -> dict[str, np.ndarray]:
        with np.load(args.work / f"{scenario}_2026.npz") as saved:
            return {name: saved[name] for name in saved.files}

    lines = filing_roles(units, people, load("fisc"), load("fisc_no_bonus"))
    table = pd.DataFrame({"line": list(lines), "value": list(lines.values())})
    table.to_csv(args.out, index=False)
    print(table.to_string(index=False))
