# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["policyengine[models]==6.11.1"]
# ///
"""Rerun the bonus for years of the budget window on reweighted households.

    uv run us/congress/fisc_marriage_bonus/decade.py 2027 2028 \
        --out <work-dir> --weight-factors <factors.npz>

run.py saves every array a year's tables need. A ten-year total on a second set
of weights needs far less, so each year here holds two microsimulations, FISC
and FISC with the bonus at zero, and saves their weighted totals to
<work-dir>/decade_<year>.json with the sha256 of the factor file. summarize.py
reads those files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from policyengine.tax_benefit_models.us import managed_microsimulation

from analysis import SCENARIOS
from reweight import apply_weight_factors

COMPARED_SCENARIOS = ("fisc", "fisc_no_bonus")
TOTALS = ("income_tax", "family_income_supplement_credit")


def scenario_totals(
    scenario: str, year: int, weight_factors: Path
) -> tuple[dict[str, float], dict]:
    sim = managed_microsimulation(reform=SCENARIOS[scenario])
    apply_weight_factors(sim, year, weight_factors)

    def calculate(variable: str) -> np.ndarray:
        return np.asarray(
            sim.calculate(variable, period=year, map_to="tax_unit").values, dtype=float
        )

    weights = calculate("tax_unit_weight")
    totals = {name: float(weights @ calculate(name)) for name in TOTALS}
    return totals, dict(getattr(sim, "policyengine_bundle", {}))


def run(year: int, out: Path, weight_factors: Path) -> Path:
    results = {}
    bundle = {}
    for scenario in COMPARED_SCENARIOS:
        results[scenario], bundle = scenario_totals(scenario, year, weight_factors)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"decade_{year}.json"
    record = {
        "year": year,
        "totals": results,
        "bundle": bundle,
        "factors_sha256": hashlib.sha256(weight_factors.read_bytes()).hexdigest(),
    }
    path.write_text(json.dumps(record, indent=2, default=str))
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", type=int, nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--weight-factors", type=Path, required=True)
    args = parser.parse_args()
    for year in args.years:
        print(run(year, args.out, args.weight_factors), flush=True)
