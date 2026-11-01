# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["policyengine[models]==6.11.1"]
# ///
"""Run one FISC scenario for one year on the certified US dataset.

    uv run us/congress/fisc_marriage_bonus/run.py fisc 2026 --out <work-dir>

Each run holds one microsimulation in one process, and writes the household and
tax-unit arrays to <work-dir>/<scenario>_<year>.npz. summarize.py reads those
files. policyengine 6.11.1 pins policyengine-us 2.2.1 and the dataset
hf://policyengine/populace-us/populace_us_2024.h5@populace-us-2024-spm-20260915,
the same bundle the production API runs. The dataset's weights and incomes
extend to later years through the model's own uprating.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import h5py
import numpy as np
from policyengine.tax_benefit_models.us import managed_microsimulation

from analysis import SCENARIOS, uncapped_credit

HOUSEHOLD_VARIABLES = (
    "household_id",
    "household_weight",
    "household_count_people",
    "household_net_income",
    "equiv_household_net_income",
    "household_income_decile",
    "household_tax",
    "household_benefits",
)
TAX_UNIT_VARIABLES = (
    "tax_unit_id",
    "tax_unit_weight",
    "income_tax",
    "adjusted_gross_income",
    "age_head",
    "age_spouse",
)
# Each person's household and tax unit link the two entities in summarize.py.
PERSON_VARIABLES = ("person_household_id", "person_tax_unit_id")
# The reform registers these two variables, so they exist only in reform runs.
REFORM_ONLY_VARIABLES = (
    "family_income_supplement_credit",
    "family_income_supplement_credit_base_amount",
)
CURRENT_LAW_ONLY_VARIABLES = ("refundable_ctc", "non_refundable_ctc")
PEOPLE_VARIABLES = ("age", "person_weight")
# The poverty flag with what the model builds it from, the state income tax that
# moves with the federal credit, and the head who carries a tax unit's taxes into
# an SPM unit. summarize.py rebuilds these chains from them.
DETAIL_VARIABLES = (
    *PEOPLE_VARIABLES,
    "is_tax_unit_head",
    "person_in_poverty",
    "person_spm_unit_id",
    "spm_unit_id",
    "spm_unit_net_income",
    "spm_unit_spm_threshold",
    "state_income_tax",
)
CAREGIVER_AGE = 18


def without_saved_spm_outputs(dataset: str, out: Path) -> str:
    """Copy an older dataset without the saved outputs this model refuses to load.

    The reconciliation reads income tax, which takes none of these as an input.
    """
    from policyengine_us.spm import REJECTED_DATASET_INPUTS

    out.mkdir(parents=True, exist_ok=True)
    copy = out / Path(dataset).name
    if not copy.exists():
        with h5py.File(dataset) as source, h5py.File(copy, "w") as target:
            for name in source:
                if name not in REJECTED_DATASET_INPUTS:
                    source.copy(name, target)
    return str(copy)


def remove_the_agi_cap(sim, year: int) -> None:
    """Hand the model the credit with no cap at any AGI, and let it compute the rest.

    The reform floors the cap at zero, so no parameter lifts it at zero or
    negative AGI. Income tax and net income then follow from this credit.
    """

    def calculate(variable: str) -> np.ndarray:
        return np.asarray(
            sim.calculate(variable, period=year, map_to="tax_unit").values
        )

    caregiver = np.maximum(calculate("age_head"), calculate("age_spouse"))
    credit = uncapped_credit(
        calculate("family_income_supplement_credit_base_amount"),
        calculate("filing_status") == "JOINT",
        calculate("adjusted_gross_income"),
    )
    sim.set_input(
        "family_income_supplement_credit",
        year,
        credit * (caregiver >= CAREGIVER_AGE),
    )


def run(
    scenario: str,
    year: int,
    out: Path,
    dataset: str | None = None,
    detail: bool = False,
    people: bool = False,
) -> Path:
    policy = SCENARIOS[scenario]
    source = (
        {"dataset": without_saved_spm_outputs(dataset, out), "allow_unmanaged": True}
        if dataset is not None
        else {}
    )
    sim = managed_microsimulation(reform=policy or None, **source)
    if scenario == "fisc_no_agi_cap":
        remove_the_agi_cap(sim, year)

    def calculate(variable: str, map_to: str | None = None) -> np.ndarray:
        return np.asarray(sim.calculate(variable, period=year, map_to=map_to).values)

    arrays = {f"household.{name}": calculate(name) for name in HOUSEHOLD_VARIABLES}
    arrays |= {f"tax_unit.{name}": calculate(name) for name in TAX_UNIT_VARIABLES}
    arrays |= {f"person.{name}": calculate(name) for name in PERSON_VARIABLES}
    arrays["tax_unit.joint"] = calculate("filing_status") == "JOINT"
    if not arrays["tax_unit.joint"].any():
        raise ValueError("no joint filers: filing_status did not decode to names")

    is_reform = scenario.startswith("fisc")
    for name in REFORM_ONLY_VARIABLES if is_reform else CURRENT_LAW_ONLY_VARIABLES:
        arrays[f"tax_unit.{name}"] = calculate(name, map_to="tax_unit")
        arrays[f"household.{name}"] = calculate(name, map_to="household")

    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{scenario}_{year}.npz"
    np.savez_compressed(path, **arrays)
    for wanted, suffix, names in (
        (people, "people", PEOPLE_VARIABLES),
        (detail, "detail", DETAIL_VARIABLES),
    ):
        sidecar = out / f"{scenario}_{year}_{suffix}.npz"
        # A rerun without the flag must not leave an older run's arrays behind.
        sidecar.unlink(missing_ok=True)
        if wanted:
            np.savez_compressed(sidecar, **{name: calculate(name) for name in names})
    bundle = dict(getattr(sim, "policyengine_bundle", {}))
    (out / f"{scenario}_{year}.json").write_text(
        json.dumps(
            {"scenario": scenario, "year": year, "policy": policy, "bundle": bundle},
            indent=2,
            default=str,
        )
    )
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=sorted(SCENARIOS))
    parser.add_argument("year", type=int)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--dataset",
        help="Path to a dataset outside the bundle, for the reconciliation only.",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Also save the poverty and state tax arrays summarize.py rebuilds.",
    )
    parser.add_argument(
        "--people",
        action="store_true",
        help="Also save ages and weights, for a dataset this model's SPM code refuses.",
    )
    args = parser.parse_args()
    print(
        run(args.scenario, args.year, args.out, args.dataset, args.detail, args.people)
    )
