# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["policyengine[models]==6.11.1"]
# ///
"""Rebuild the tables the provision runs feed and compare them with the commit.

    uv run us/congress/fisc_marriage_bonus/recheck_tables.py runs

`runs` holds one folder for each set in github_provision_runs.yml: current, the four
sets of weights, cps and march. The script writes nothing. It raises if a rebuilt
table differs from results/ in shape, in a label or in a blank cell, or if a number
moves by more than RECHECK_TOLERANCE of its value.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

import summarize

# A few units in the last place of a double.
RECHECK_TOLERANCE = 1e-15
WEIGHT_SETS = ("household_counts", "family_income", "child_credit", "all_targets")
FACTORS = Path(__file__).parent / "factors"


def compare_table(
    name: str, saved: pd.DataFrame, fresh: pd.DataFrame
) -> tuple[int, float]:
    """How many numbers a table holds and the largest relative gap among them."""
    if list(saved.columns) != list(fresh.columns) or len(saved) != len(fresh):
        raise AssertionError(f"{name}: the rebuilt table changes shape")
    saved, fresh = saved.reset_index(drop=True), fresh.reset_index(drop=True)
    numbers, largest = 0, 0.0
    for column in saved.columns:
        old, new = saved[column], fresh[column]
        if (old.isna() != new.isna()).any():
            raise AssertionError(f"{name}: {column} holds a blank against a value")
        filled = old.notna()
        if not (is_numeric_dtype(old) and is_numeric_dtype(new)):
            if (old[filled].astype(str) != new[filled].astype(str)).any():
                raise AssertionError(f"{name}: {column} changes a label")
            continue
        a, b = old[filled].to_numpy(float), new[filled].to_numpy(float)
        with np.errstate(divide="ignore", invalid="ignore"):
            gap = np.where(
                a == b, 0.0, np.abs(a - b) / np.maximum(np.abs(a), np.abs(b))
            )
        if not (gap <= RECHECK_TOLERANCE).all():
            raise AssertionError(f"{name}: {column} moves past the tolerance")
        numbers += a.size
        largest = max(largest, float(gap.max(initial=0.0)))
    return numbers, largest


def rebuilt_tables(runs: Path) -> dict[str, pd.DataFrame]:
    """Each whole table the runs feed, named for its file in results/."""
    work, ecps, cps = runs / "current", runs / "march", runs / "cps"
    weights = {label: runs / label for label in WEIGHT_SETS}
    factors = {label: FACTORS / f"factors_{label}.npz" for label in WEIGHT_SETS}
    return {
        **{
            f"{name}_2026": table
            for name, table in summarize.distribution(work).items()
        },
        "gini_by_provision_2026": summarize.gini_by_provision(work),
        "bonus_reach_2026": summarize.bonus_reach(work),
        "versus_outside_estimate": summarize.versus_outside_estimate(work),
        "data_comparison_2026": summarize.data_comparison(ecps, cps, work, work),
        "reweighted_comparison_2026": summarize.reweighted_comparison(
            work, work, weights
        ),
        "deciles_by_weights_2026": summarize.deciles_by_weights(weights),
        "weight_factors": summarize.weight_factor_summary(work, factors),
        "deciles_by_data_file_2026": summarize.deciles_by_data_file(ecps, cps, work),
        "cps_sampling_spread_2026": summarize.sampling_spread(cps),
    }


def main(runs: Path, results: Path = summarize.RESULTS) -> dict[str, tuple[int, float]]:
    checked = {
        name: compare_table(name, pd.read_csv(results / f"{name}.csv"), fresh)
        for name, fresh in rebuilt_tables(runs).items()
    }
    # These runs feed one row of this table.
    row, _ = summarize.agi_cap_provision(runs / "current", runs / "current")
    saved = pd.read_csv(results / "provisions_2026.csv")
    saved = saved.loc[saved.provision == row["provision"], list(row)]
    checked["provisions_2026"] = compare_table(
        "provisions_2026", saved, pd.DataFrame([row])
    )
    return checked


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path)
    tables = main(parser.parse_args().runs)
    for name, (numbers, largest) in tables.items():
        print(f"{name}: {numbers} numbers, largest relative gap {largest:.3g}")
    total = sum(numbers for numbers, _ in tables.values())
    worst = max(largest for _, largest in tables.values())
    print(f"{len(tables)} tables, {total} numbers, largest relative gap {worst:.3g}")
