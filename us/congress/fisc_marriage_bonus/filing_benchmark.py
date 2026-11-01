# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["policyengine[models]==6.11.1"]
# ///
"""Save what the IRS filing-status tables count, from one current-law run.

    uv run us/congress/fisc_marriage_bonus/filing_benchmark.py 2024 --out <work-dir>

The IRS publishes filing status against the child credit, and the Census tables
tabulate the CPS, so these arrays test each data file against a source outside
the CPS. run.py saves only a joint flag for a 2026 reform comparison, and this
run keeps every filing status, the filer flag and each person's age for a year
under the $2,000 child tax credit.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from policyengine.tax_benefit_models.us import managed_microsimulation

from run import without_saved_spm_outputs

TAX_UNIT_VARIABLES = (
    "tax_unit_id",
    "tax_unit_weight",
    "adjusted_gross_income",
    "income_tax",
    "tax_unit_is_filer",
    "ctc_qualifying_children",
    "ctc_limiting_tax_liability",
)
# The model's non_refundable_ctc comes before the tax liability limit, and the IRS
# reports the credit after it, so the benchmark needs the liability as well.
TAX_UNIT_CREDITS = ("ctc", "non_refundable_ctc", "refundable_ctc")
PERSON_VARIABLES = (
    "person_tax_unit_id",
    "person_household_id",
    "age",
    "person_weight",
    "is_household_head",
    "is_tax_unit_dependent",
)
HOUSEHOLD_VARIABLES = ("household_id", "household_weight")


def run(year: int, out: Path, dataset: str | None = None) -> Path:
    source = (
        {"dataset": without_saved_spm_outputs(dataset, out), "allow_unmanaged": True}
        if dataset is not None
        else {}
    )
    sim = managed_microsimulation(**source)

    def calculate(variable: str, map_to: str | None = None) -> np.ndarray:
        return np.asarray(sim.calculate(variable, period=year, map_to=map_to).values)

    arrays = {f"tax_unit.{name}": calculate(name) for name in TAX_UNIT_VARIABLES}
    arrays |= {
        f"tax_unit.{name}": calculate(name, map_to="tax_unit")
        for name in TAX_UNIT_CREDITS
    }
    arrays |= {f"person.{name}": calculate(name) for name in PERSON_VARIABLES}
    arrays |= {f"household.{name}": calculate(name) for name in HOUSEHOLD_VARIABLES}
    arrays["tax_unit.filing_status"] = calculate("filing_status").astype(str)
    if not (arrays["tax_unit.filing_status"] == "JOINT").any():
        raise ValueError("no joint filers: filing_status did not decode to names")

    out.mkdir(parents=True, exist_ok=True)
    path = out / f"filing_{year}.npz"
    np.savez_compressed(path, **arrays)
    bundle = dict(getattr(sim, "policyengine_bundle", {}))
    (out / f"filing_{year}.json").write_text(
        json.dumps({"year": year, "bundle": bundle}, indent=2, default=str)
    )
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", type=int)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dataset", help="Path to a dataset outside the bundle.")
    args = parser.parse_args()
    print(run(args.year, args.out, args.dataset))
