# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["numpy"]
# ///
"""Reweight the current dataset to population and household counts outside the CPS.

    uv run us/congress/fisc_marriage_bonus/reweight.py <work-dir> <factors.npz>

The current dataset has no household-type or marital-status targets
(PolicyEngine/microcosm#880), so this asks what such targets would do to the
bonus. Entropy balancing changes each household's weight as little as it can
while it hits the targets below, which come from the Census Bureau's population
estimates and the American Community Survey. run.py then reruns the reform on
those weights, so every figure from them comes from a full run.

The dataset's own 2024 income and income tax totals stay fixed, because the
experiment moves family structure and nothing else.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# Census Bureau, Vintage 2025 national population estimates, July 1, 2024.
# https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/national/asrh/nc-est2025-agesex-res.csv
CHILDREN_UNDER_1_2024 = 3_617_221
CHILDREN_UNDER_6_2024 = 22_450_934
CHILDREN_UNDER_18_2024 = 72_548_879
# American Community Survey 2024 1-year estimates.
HOUSEHOLDS_2024 = 132_737_146  # B11001_001E
MARRIED_COUPLE_HOUSEHOLDS_2024 = 61_980_084  # B11001_003E
MARRIED_COUPLE_FAMILIES_WITH_OWN_CHILD_2024 = 22_978_636  # B11003_003E
CHILDREN_ANY_HOUSEHOLD_2024 = 72_736_534  # B09005_001E
CHILDREN_MARRIED_HOUSEHOLD_2024 = 48_553_644  # B09005_002E
# B19131_004E to B19131_019E, married-couple families with own children under 18
# by family income, summed by band. Family income counts every source, and the
# model side uses the adjusted gross income of the household's tax units, which
# leaves some transfers out.
MARRIED_OWN_CHILD_FAMILIES_BY_INCOME = (
    ("under_25000", -np.inf, 25_000.0, 724_561),
    ("25000_to_50000", 25_000.0, 50_000.0, 1_656_621),
    ("50000_to_100000", 50_000.0, 100_000.0, 5_258_653),
    ("100000_to_200000", 100_000.0, 200_000.0, 9_178_004),
    ("200000_or_more", 200_000.0, np.inf, 6_160_797),
)

MAX_NEWTON_STEPS = 200
TARGET_TOLERANCE = 1e-9


@dataclass(frozen=True)
class Calibration:
    factors: np.ndarray
    targets: dict[str, float]
    before: dict[str, float]
    after: dict[str, float]


def household_position(ids: np.ndarray, links: np.ndarray) -> np.ndarray:
    """Each link's row in ids, whatever order ids take."""
    order = np.argsort(ids)
    found = np.searchsorted(ids, links, sorter=order)
    position = order[np.minimum(found, ids.size - 1)]
    if not np.array_equal(ids[position], links):
        raise ValueError("a link points at no row")
    return position


def household_moments(run: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Count what each target measures in each household, at weight one."""
    household_ids = run["household.household_id"]
    households = household_ids.size
    person_household = household_position(
        household_ids, run["person.person_household_id"]
    )
    person_unit = household_position(
        run["tax_unit.tax_unit_id"], run["person.person_tax_unit_id"]
    )
    age = run["person.age"]
    head = run["person.is_household_head"].astype(bool)
    unit_married = run["tax_unit.filing_status"] == "JOINT"

    def per_household(values: np.ndarray) -> np.ndarray:
        return np.bincount(
            person_household, weights=values.astype(float), minlength=households
        )

    married_head = per_household(head & unit_married[person_unit]) > 0
    own_child = per_household(
        (age < 18)
        & run["person.is_tax_unit_dependent"].astype(bool)
        & np.isin(person_unit, person_unit[head])
    )
    unit_household = np.zeros(run["tax_unit.tax_unit_id"].size, dtype=int)
    unit_household[person_unit] = person_household
    children = per_household(age < 18)

    def unit_sum(values: np.ndarray) -> np.ndarray:
        return np.bincount(unit_household, weights=values, minlength=households)

    return {
        "people": per_household(np.ones_like(age)),
        "people_65_and_over": per_household(age >= 65),
        "children_under_1": per_household(age < 1),
        "children_under_6": per_household(age < 6),
        "children_under_18": children,
        "households": np.ones(households),
        "married_couple_households": married_head.astype(float),
        "married_couple_households_with_own_child": (
            married_head & (own_child > 0)
        ).astype(float),
        "children_in_married_couple_households": children * married_head,
        "adjusted_gross_income": unit_sum(
            run["tax_unit.adjusted_gross_income"].astype(float)
        ),
        "income_tax": unit_sum(run["tax_unit.income_tax"].astype(float)),
    }


def family_income_moments(moments: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Split married-couple households with an own child by household income."""
    income = moments["adjusted_gross_income"]
    families = moments["married_couple_households_with_own_child"]
    return {
        f"married_own_child_income_{label}": families
        * ((income >= low) & (income < high))
        for label, low, high, _ in MARRIED_OWN_CHILD_FAMILIES_BY_INCOME
    }


def published_targets(
    moments: dict[str, np.ndarray], weights: np.ndarray, detailed: bool = False
) -> dict[str, float]:
    """The published counts, with the totals this experiment holds fixed."""
    held = ("people", "people_65_and_over", "adjusted_gross_income", "income_tax")
    share_married = CHILDREN_MARRIED_HOUSEHOLD_2024 / CHILDREN_ANY_HOUSEHOLD_2024
    # The income bands add to the family total, so the total leaves the solve.
    extra = (
        {
            "children_under_1": CHILDREN_UNDER_1_2024,
            **{
                f"married_own_child_income_{label}": families
                for label, _, _, families in MARRIED_OWN_CHILD_FAMILIES_BY_INCOME
            },
        }
        if detailed
        else {
            "married_couple_households_with_own_child": (
                MARRIED_COUPLE_FAMILIES_WITH_OWN_CHILD_2024
            )
        }
    )
    return {
        **{name: float(moments[name] @ weights) for name in held},
        "children_under_6": CHILDREN_UNDER_6_2024,
        "children_under_18": CHILDREN_UNDER_18_2024,
        "households": HOUSEHOLDS_2024,
        "married_couple_households": MARRIED_COUPLE_HOUSEHOLDS_2024,
        **extra,
        # The ACS and population estimates give different child totals, so the
        # target takes the ACS share of the population estimate's total.
        "children_in_married_couple_households": (
            share_married * CHILDREN_UNDER_18_2024
        ),
    }


def entropy_balance(
    weights: np.ndarray, moments: np.ndarray, targets: np.ndarray
) -> np.ndarray:
    """Return factors nearest one, in relative entropy, that hit every target.

    The dual is smooth and convex, so damped Newton steps reach the unique
    solution when the targets lie inside what the records can reach.
    """
    scale = np.abs(targets)
    scale[scale == 0] = 1.0
    scaled_moments = moments / scale[:, None]
    scaled_targets = targets / scale
    multipliers = np.zeros(moments.shape[0])

    def factors_at(point: np.ndarray) -> np.ndarray:
        return np.exp(np.clip(point @ scaled_moments, -30.0, 30.0))

    def dual(point: np.ndarray) -> float:
        return float(weights @ factors_at(point) - point @ scaled_targets)

    def gap_at(point: np.ndarray) -> np.ndarray:
        return scaled_moments @ (factors_at(point) * weights) - scaled_targets

    for _ in range(MAX_NEWTON_STEPS):
        gap = gap_at(multipliers)
        worst = np.max(np.abs(gap))
        if worst < TARGET_TOLERANCE:
            return factors_at(multipliers)
        current = factors_at(multipliers) * weights
        hessian = (scaled_moments * current) @ scaled_moments.T
        direction = np.linalg.solve(hessian + 1e-12 * np.eye(hessian.shape[0]), -gap)
        value = dual(multipliers)
        slope = gap @ direction
        step = 1.0
        # Near the solution the dual stops changing within rounding, so a step
        # also counts as progress when it shrinks the worst miss.
        while (
            dual(multipliers + step * direction) > value + 1e-4 * step * slope
            and np.max(np.abs(gap_at(multipliers + step * direction))) >= worst
        ):
            step /= 2
            if step < 1e-10:
                raise ValueError("the line search stalled")
        multipliers = multipliers + step * direction
    raise ValueError("entropy balancing did not reach the targets")


def apply_weight_factors(sim, year: int, path: Path) -> None:
    """Multiply each household's weight for this year by its saved factor."""
    with np.load(path) as saved:
        household_ids, factors = saved["household_id"], saved["factor"]

    def household_values(variable: str) -> np.ndarray:
        return np.asarray(sim.calculate(variable, period=year).values, dtype=float)

    if not np.array_equal(household_ids, household_values("household_id")):
        raise ValueError("the factors belong to another file's households")
    weights = household_values("household_weight") * factors
    sim.set_input("household_weight", year, weights)
    if not np.allclose(household_values("household_weight"), weights):
        raise ValueError("the simulation kept its old household weights")


def calibrate(run: dict[str, np.ndarray], detailed: bool = False) -> Calibration:
    moments = household_moments(run)
    if detailed:
        moments |= family_income_moments(moments)
    weights = run["household.household_weight"].astype(float)
    targets = published_targets(moments, weights, detailed)
    names = list(targets)
    matrix = np.vstack([moments[name] for name in names])
    factors = entropy_balance(
        weights, matrix, np.array([targets[name] for name in names], dtype=float)
    )
    return Calibration(
        factors=factors,
        targets=targets,
        before={name: float(moments[name] @ weights) for name in names},
        after={name: float(moments[name] @ (weights * factors)) for name in names},
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("factors", type=Path)
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Also match infants, and married families with children by income.",
    )
    args = parser.parse_args()
    with np.load(args.work / "filing_2024.npz") as saved:
        run = {name: saved[name] for name in saved.files}
    result = calibrate(run, args.detailed)
    np.savez_compressed(
        args.factors,
        household_id=run["household.household_id"],
        factor=result.factors,
    )
    for name, target in result.targets.items():
        print(
            f"{name:46s} {result.before[name]:>22,.0f} {target:>22,.0f} "
            f"{result.after[name]:>22,.0f}"
        )
    print(
        "factor quantiles",
        np.quantile(result.factors, [0, 0.01, 0.5, 0.99, 1]).round(3),
    )
