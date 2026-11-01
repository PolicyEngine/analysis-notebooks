# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["numpy", "pandas"]
# ///
"""Compare each data file with published counts that do not tabulate the CPS.

    uv run us/congress/fisc_marriage_bonus/benchmarks.py <name>=<work-dir>[,<factors.npz>] ...

Census table C3 tabulates the CPS, so a CPS-based file agreeing with it tests
nothing. These rows use the IRS, the American Community Survey and the Census
Bureau's population estimates. filing_benchmark.py writes the run each file
needs, and the output lands in results/benchmarks_2024.csv.

Published years differ from the 2024 runs where the source stops earlier: the
IRS tables cover tax year 2023, and the advance child credit covers 2021.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from reweight import (
    MARRIED_OWN_CHILD_FAMILIES_BY_INCOME,
    family_income_moments,
    household_moments,
    household_position,
)

RESULTS = Path(__file__).parent / "results"

JOINT = "JOINT"
SURVIVING_SPOUSE = "SURVIVING_SPOUSE"
HEAD_OF_HOUSEHOLD = "HEAD_OF_HOUSEHOLD"
FILING_STATUSES = (JOINT, SURVIVING_SPOUSE, HEAD_OF_HOUSEHOLD, "SINGLE", "SEPARATE")
# The 2021 credit's $2,000 portion phases out at $50 per $1,000 above $400,000
# on a joint return and $200,000 on others, so each child adds $40,000 of room.
ADVANCE_LIMIT_JOINT = 400_000.0
ADVANCE_LIMIT_OTHER = 200_000.0
ADVANCE_PER_CHILD_AGI = 40_000.0

# IRS Table 1.2, tax year 2023: returns of married persons filing jointly and
# surviving spouses. The first band holds the table's no-AGI row.
JOINT_RETURNS_BY_AGI = (
    ("under_25000", -np.inf, 25_000.0, 4_932_918),
    ("25000_to_50000", 25_000.0, 50_000.0, 6_062_981),
    ("50000_to_100000", 50_000.0, 100_000.0, 13_541_531),
    ("100000_to_200000", 100_000.0, 200_000.0, 18_900_024),
    ("200000_to_500000", 200_000.0, 500_000.0, 8_960_113),
    ("500000_or_more", 500_000.0, np.inf, 2_171_373),
)

SOURCES = {
    "pep": "Census Vintage 2025 population estimates, July 2024",
    "acs": "American Community Survey 2024 1-year",
    "soi_12": "IRS Publication 1304 Table 1.2, tax year 2023",
    "soi_13": "IRS Publication 1304 Table 1.3, tax year 2023",
    "advance": "IRS advance child tax credit Table 3, 2021",
    "births": "CDC, Births: Final Data for 2024",
}
SOURCE_URLS = {
    "pep": "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/national/asrh/nc-est2025-agesex-res.csv",
    "acs": "https://api.census.gov/data/2024/acs/acs1",
    "soi_12": "https://www.irs.gov/pub/irs-soi/23in12ms.xls",
    "soi_13": "https://www.irs.gov/pub/irs-soi/23in13ms.xls",
    "advance": "https://www.irs.gov/pub/irs-soi/21in03actc.xls",
    "births": "https://www.cdc.gov/nchs/fastats/unmarried-childbearing.htm",
}


@dataclass(frozen=True)
class Benchmark:
    measure: str
    published: float
    source: str
    note: str = ""


BENCHMARKS = (
    Benchmark("children_under_18", 72_548_879, "pep"),
    Benchmark("children_under_1", 3_617_221, "pep"),
    Benchmark(
        "share_of_infants_in_married_tax_units",
        1 - 1_433_976 / 3_628_934,
        "births",
        "Married at birth; the ACS puts 69.9% of mothers with a recent birth as "
        "now married (B13002_003E of B13002_002E), measured at the interview",
    ),
    Benchmark("households", 132_737_146, "acs", "B11001_001E"),
    Benchmark("married_couple_households", 61_980_084, "acs", "B11001_003E"),
    Benchmark(
        "married_couple_households_with_own_child",
        22_978_636,
        "acs",
        "B11003_003E; the 2020 Census counted 22,284,317 (P20_003N)",
    ),
    Benchmark(
        "children_in_married_couple_households",
        48_553_644,
        "acs",
        "B09005_002E of 72,736,534",
    ),
    Benchmark(
        "share_of_children_in_married_couple_households",
        48_553_644 / 72_736_534,
        "acs",
        "B09005_002E over B09005_001E",
    ),
    Benchmark(
        "joint_filers",
        54_568_939 + 4_139_858,
        "soi_13",
        "Joint, surviving spouse and separate returns, since the model files "
        "every couple jointly",
    ),
    Benchmark("all_filers", 160_602_107, "soi_13"),
    Benchmark("head_of_household_filers", 21_604_491, "soi_13"),
    Benchmark(
        "joint_returns_with_child_credit",
        21_526_250 + 739_342,
        "soi_13",
        "Nonrefundable child and other dependent credit, joint, surviving "
        "spouse and separate",
    ),
    Benchmark(
        "joint_child_credit",
        58_813_439_000 + 1_527_331_000,
        "soi_13",
        "Nonrefundable child and other dependent credit, joint, surviving "
        "spouse and separate",
    ),
    Benchmark(
        "other_returns_with_child_credit",
        14_827_347 + 1_856_588,
        "soi_13",
        "Head of household plus single",
    ),
    Benchmark(
        "other_child_credit",
        22_060_826_000 + 2_016_769_000,
        "soi_13",
        "Head of household plus single",
    ),
    Benchmark(
        "share_of_advance_children_joint",
        (35_165_385 + 1_038_058) / 61_976_091,
        "advance",
        "Joint plus separate; recipients of a 2021 advance payment only",
    ),
    Benchmark(
        "children_outside_joint_units",
        22_346_185 + 3_362_687 + 63_776,
        "advance",
        "A floor: head of household, single and widow(er) recipients, before "
        "any child outside the payments",
    ),
    *(
        Benchmark(f"joint_filers_agi_{label}", returns, "soi_12")
        for label, _, _, returns in JOINT_RETURNS_BY_AGI
    ),
    *(
        Benchmark(f"married_own_child_income_{label}", families, "acs", "B19131")
        for label, _, _, families in MARRIED_OWN_CHILD_FAMILIES_BY_INCOME
    ),
)


def weighted_count(mask: np.ndarray, weights: np.ndarray) -> float:
    return float(weights @ mask.astype(float))


def measures(run: dict[str, np.ndarray]) -> dict[str, float]:
    """Return each benchmark's measure for one file, at the file's own weights."""
    unit_ids = run["tax_unit.tax_unit_id"]
    person_unit = household_position(unit_ids, run["person.person_tax_unit_id"])
    status = run["tax_unit.filing_status"]
    if not np.isin(status, FILING_STATUSES).all():
        raise ValueError(f"unknown filing status in {sorted(set(status))}")
    married = status == JOINT
    # IRS tables put surviving spouses in the joint column.
    joint_column = np.isin(status, (JOINT, SURVIVING_SPOUSE))
    filer = run["tax_unit.tax_unit_is_filer"].astype(bool)
    unit_weight = run["tax_unit.tax_unit_weight"].astype(float)
    household_weight = run["household.household_weight"].astype(float)
    in_households = household_moments(run)
    income = run["tax_unit.adjusted_gross_income"].astype(float)
    child = run["person.age"] < 18
    infant = run["person.age"] < 1

    children_in_unit = np.bincount(
        person_unit, weights=child.astype(float), minlength=unit_ids.size
    )
    infants_in_unit = np.bincount(
        person_unit, weights=infant.astype(float), minlength=unit_ids.size
    )
    # The IRS reports the credit after the tax limit, and the model's
    # non_refundable_ctc comes before it.
    credit = np.minimum(
        run["tax_unit.non_refundable_ctc"].astype(float),
        np.maximum(run["tax_unit.ctc_limiting_tax_liability"].astype(float), 0.0),
    )
    claimed = credit > 0
    limit = np.where(joint_column, ADVANCE_LIMIT_JOINT, ADVANCE_LIMIT_OTHER)
    advance = (children_in_unit > 0) & (
        income < limit + ADVANCE_PER_CHILD_AGI * children_in_unit
    )
    child_weight = unit_weight * children_in_unit

    return {
        "children_under_18": float(child_weight.sum()),
        "children_under_1": float(unit_weight @ infants_in_unit),
        "share_of_infants_in_married_tax_units": float(
            unit_weight @ (infants_in_unit * married) / (unit_weight @ infants_in_unit)
        ),
        **{
            name: float(household_weight @ in_households[name])
            for name in (
                "households",
                "married_couple_households",
                "married_couple_households_with_own_child",
                "children_in_married_couple_households",
            )
        },
        "share_of_children_in_married_couple_households": float(
            household_weight
            @ in_households["children_in_married_couple_households"]
            / (household_weight @ in_households["children_under_18"])
        ),
        "children_in_married_tax_units": float(child_weight @ married),
        "share_of_children_in_married_tax_units": float(
            child_weight @ married / child_weight.sum()
        ),
        "married_tax_units": weighted_count(married, unit_weight),
        "married_tax_units_with_child": weighted_count(
            married & (children_in_unit > 0), unit_weight
        ),
        "joint_filers": weighted_count(joint_column & filer, unit_weight),
        "all_filers": weighted_count(filer, unit_weight),
        "head_of_household_filers": weighted_count(
            (status == HEAD_OF_HOUSEHOLD) & filer, unit_weight
        ),
        "joint_returns_with_child_credit": weighted_count(
            joint_column & claimed, unit_weight
        ),
        "joint_child_credit": float(unit_weight @ (credit * joint_column)),
        "other_returns_with_child_credit": weighted_count(
            ~joint_column & claimed, unit_weight
        ),
        "other_child_credit": float(unit_weight @ (credit * ~joint_column)),
        "share_of_advance_children_joint": float(
            child_weight @ (advance & joint_column) / (child_weight @ advance)
        ),
        "children_outside_joint_units": float(child_weight @ ~joint_column),
        **{
            f"joint_filers_agi_{label}": weighted_count(
                joint_column & filer & (income >= low) & (income < high), unit_weight
            )
            for label, low, high, _ in JOINT_RETURNS_BY_AGI
        },
        **{
            name: float(household_weight @ families)
            for name, families in family_income_moments(in_households).items()
        },
    }


def benchmark_table(runs: dict[str, dict[str, np.ndarray]]) -> pd.DataFrame:
    """One row per measure, with the published figure beside each file."""
    by_file = {name: measures(run) for name, run in runs.items()}
    published = {item.measure: item for item in BENCHMARKS}
    rows = []
    for measure in next(iter(by_file.values())):
        item = published.get(measure)
        rows.append(
            {
                "measure": measure,
                "published": item.published if item else np.nan,
                "source": SOURCES[item.source] if item else "",
                "url": SOURCE_URLS[item.source] if item else "",
                "note": item.note if item else "",
                **{name: values[measure] for name, values in by_file.items()},
            }
        )
    return pd.DataFrame(rows)


def load_run(work: Path) -> dict[str, np.ndarray]:
    with np.load(work / "filing_2024.npz") as saved:
        return {name: saved[name] for name in saved.files}


def with_weight_factors(
    run: dict[str, np.ndarray], factors: np.ndarray
) -> dict[str, np.ndarray]:
    """The same run at reweighted households, which carry their tax units along."""
    unit_row = household_position(
        run["tax_unit.tax_unit_id"], run["person.person_tax_unit_id"]
    )
    household_row = household_position(
        run["household.household_id"], run["person.person_household_id"]
    )
    unit_household = np.zeros(run["tax_unit.tax_unit_id"].size, dtype=int)
    unit_household[unit_row] = household_row
    return run | {
        "household.household_weight": run["household.household_weight"] * factors,
        "tax_unit.tax_unit_weight": run["tax_unit.tax_unit_weight"]
        * factors[unit_household],
    }


def load_file(spec: str) -> tuple[str, dict[str, np.ndarray]]:
    """Read name=work-dir, or name=work-dir,factors.npz for reweighted runs."""
    name, paths = spec.split("=", 1)
    work, _, factors = paths.partition(",")
    run = load_run(Path(work))
    if not factors:
        return name, run
    with np.load(factors) as saved:
        return name, with_weight_factors(run, saved["factor"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="name=work-dir[,factors.npz]")
    parser.add_argument("--out", type=Path, default=RESULTS / "benchmarks_2024.csv")
    args = parser.parse_args()
    table = benchmark_table(dict(load_file(item) for item in args.files))
    table.to_csv(args.out, index=False)
    print(table.drop(columns=["url", "note", "source"]).to_string())
