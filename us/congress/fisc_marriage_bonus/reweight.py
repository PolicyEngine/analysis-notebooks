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
estimates, the American Community Survey and the IRS. run.py then reruns the
reform on those weights, so every figure from them comes from a full run.

The dataset's own 2024 income and income tax totals stay fixed, so the weights
move family structure and filing without moving those totals. People's incomes
and family records stay as they are, and tax unit totals move with the weights.

The ACS sorts households by the householder's relationships, so the household
targets read the survey's relationship codes, which relationship.py saves beside
the run. The IRS targets read the model's filing status, as the IRS counts returns.
"""

from __future__ import annotations

import argparse
import json
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

# The IRS lines below split returns into married people's and everyone else's. The
# model files a couple jointly unless a spouse has separated, and the bonus turns on
# marriage, so the married side adds separate returns to the joint column, on the
# IRS side and the model side alike. IRS tables put surviving spouses in the joint
# column.
MARRIED_RETURNS = ("JOINT", "SURVIVING_SPOUSE", "SEPARATE")

# IRS Publication 1304 Table 1.3, tax year 2023, a year before these runs under the
# same $2,000 credit: the nonrefundable child and other dependent credit. The other
# lines add head of household and single returns.
CHILD_CREDIT_2023 = {
    "joint_returns_with_child_credit": 21_526_250 + 739_342,
    "joint_child_credit": 58_813_439_000 + 1_527_331_000,
    "other_returns_with_child_credit": 14_827_347 + 1_856_588,
    "other_child_credit": 22_060_826_000 + 2_016_769_000,
}
# IRS Publication 1304 Table 1.3, tax year 2023.
ALL_RETURNS_2023 = 160_602_107
HEAD_OF_HOUSEHOLD_RETURNS_2023 = 21_604_491
# IRS Publication 1304 Table 1.2, tax year 2023: joint and surviving spouse returns
# plus separate returns. The first band holds the table's no-AGI row.
MARRIED_RETURNS_BY_AGI = (
    ("under_25000", -np.inf, 25_000.0, 4_932_918 + 841_526),
    ("25000_to_50000", 25_000.0, 50_000.0, 6_062_981 + 1_154_641),
    ("50000_to_100000", 50_000.0, 100_000.0, 13_541_531 + 1_421_936),
    ("100000_to_200000", 100_000.0, 200_000.0, 18_900_024 + 558_588),
    ("200000_to_500000", 200_000.0, 500_000.0, 8_960_113 + 123_766),
    ("500000_or_more", 500_000.0, np.inf, 2_171_373 + 39_401),
)

# The 2024 ASEC's A_EXPRRP codes each person's relationship to the household's
# reference person, whom the Census Bureau counts as the householder, and A_MARITL
# codes marital status.
REFERENCE_PERSON_CODES = (1, 2)
SPOUSE_CODES = (3, 4)
OWN_CHILD_CODE = 5
NEVER_MARRIED = 7
ACS_SHARE_OF_CHILDREN_IN_MARRIED_COUPLE_HOUSEHOLDS = (
    CHILDREN_MARRIED_HOUSEHOLD_2024 / CHILDREN_ANY_HOUSEHOLD_2024
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


def child_credit_after_tax_limit(run: dict[str, np.ndarray]) -> np.ndarray:
    """The IRS reports the credit after the tax limit, and the model's comes before."""
    return np.minimum(
        run["tax_unit.non_refundable_ctc"].astype(float),
        np.maximum(run["tax_unit.ctc_limiting_tax_liability"].astype(float), 0.0),
    )


def tax_unit_totals(run: dict[str, np.ndarray]):
    """A function that adds a value per tax unit up to each household."""
    unit_ids = run["tax_unit.tax_unit_id"]
    household_of_unit = np.zeros(unit_ids.size, dtype=int)
    household_of_unit[
        household_position(unit_ids, run["person.person_tax_unit_id"])
    ] = household_position(
        run["household.household_id"], run["person.person_household_id"]
    )

    def per_household(values: np.ndarray) -> np.ndarray:
        return np.bincount(
            household_of_unit,
            weights=values.astype(float),
            minlength=run["household.household_id"].size,
        )

    return per_household


def child_credit_moments(run: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Count the IRS child credit lines in each household, at weight one."""
    per_household = tax_unit_totals(run)
    married = np.isin(run["tax_unit.filing_status"], MARRIED_RETURNS)
    credit = child_credit_after_tax_limit(run)
    return {
        "joint_returns_with_child_credit": per_household((credit > 0) & married),
        "joint_child_credit": per_household(credit * married),
        "other_returns_with_child_credit": per_household((credit > 0) & ~married),
        "other_child_credit": per_household(credit * ~married),
    }


def filer_moments(run: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Count the IRS return lines in each household, at weight one."""
    per_household = tax_unit_totals(run)
    filer = run["tax_unit.tax_unit_is_filer"].astype(bool)
    status = run["tax_unit.filing_status"]
    married = np.isin(status, MARRIED_RETURNS) & filer
    income = run["tax_unit.adjusted_gross_income"].astype(float)
    return {
        "all_filers": per_household(filer),
        "head_of_household_filers": per_household(
            (status == "HEAD_OF_HOUSEHOLD") & filer
        ),
        **{
            f"joint_filers_agi_{label}": per_household(
                married & (income >= low) & (income < high)
            )
            for label, low, high, _ in MARRIED_RETURNS_BY_AGI
        },
    }


def household_moments(run: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Count what each target measures in each household, at weight one.

    The household types here follow the head's joint filing, which the benchmarks
    compare across files. calibrate takes them from relationship_moments instead.
    """
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

    dependent = run["person.is_tax_unit_dependent"].astype(bool)
    # A head who is someone's dependent heads no married couple, even when the
    # unit they belong to files jointly, and is no one's own child.
    married_head = per_household(head & ~dependent & unit_married[person_unit]) > 0
    own_child = per_household(
        (age < 18) & dependent & ~head & np.isin(person_unit, person_unit[head])
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


def relationship_moments(run: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Count the ACS household types from the survey's relationship codes.

    A married-couple household holds the householder's spouse, and an own child is
    the householder's never-married child under 18 by birth, marriage or adoption.
    Children in households leave out householders and spouses, as table B09005
    does. B09005 also leaves out unmarried partners, whom code 13 lumps with
    roommates, so the count keeps them; the 2024 ASEC's partner pointer names no
    one under 18 as a partner.

    The last moment measures how far the household's children sit from the ACS
    share in married-couple households, so a target of zero holds that share over
    the same children B09005 counts.
    """
    if "person.cps_relationship" not in run or "person.cps_marital_status" not in run:
        raise ValueError("the run has no relationship codes: run relationship.py")
    household_ids = run["household.household_id"]
    person_household = household_position(
        household_ids, run["person.person_household_id"]
    )
    code = run["person.cps_relationship"]
    never_married = run["person.cps_marital_status"] == NEVER_MARRIED
    young = run["person.age"] < 18

    def per_household(values: np.ndarray) -> np.ndarray:
        return np.bincount(
            person_household, weights=values.astype(float), minlength=household_ids.size
        )

    married = per_household(np.isin(code, SPOUSE_CODES)) > 0
    own_child = per_household(young & never_married & (code == OWN_CHILD_CODE)) > 0
    children = per_household(
        young & ~np.isin(code, REFERENCE_PERSON_CODES + SPOUSE_CODES)
    )
    return {
        "married_couple_households": married.astype(float),
        "married_couple_households_with_own_child": (married & own_child).astype(float),
        "children_in_households": children,
        "children_in_married_couple_households": children * married,
        "children_in_married_couple_households_above_acs_share": children
        * (married - ACS_SHARE_OF_CHILDREN_IN_MARRIED_COUPLE_HOUSEHOLDS),
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
    moments: dict[str, np.ndarray],
    weights: np.ndarray,
    detailed: bool = False,
    child_credit: bool = False,
    filers: bool = False,
) -> dict[str, float]:
    """The published counts, with the totals this experiment holds fixed."""
    held = ("people", "people_65_and_over", "adjusted_gross_income", "income_tax")
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
        **(CHILD_CREDIT_2023 if child_credit else {}),
        **(
            {
                "all_filers": ALL_RETURNS_2023,
                "head_of_household_filers": HEAD_OF_HOUSEHOLD_RETURNS_2023,
                **{
                    f"joint_filers_agi_{label}": returns
                    for label, _, _, returns in MARRIED_RETURNS_BY_AGI
                },
            }
            if filers
            else {}
        ),
        # The ACS and population estimates give different child totals, so the
        # target holds the ACS share rather than its count.
        "children_in_married_couple_households_above_acs_share": 0.0,
    }


def entropy_balance(
    weights: np.ndarray, moments: np.ndarray, targets: np.ndarray
) -> np.ndarray:
    """Return factors nearest one, in relative entropy, that hit every target.

    The dual is smooth and convex, so damped Newton steps reach the unique
    solution when the targets lie inside what the records can reach. Each step
    measures a miss against its target's size. A target of zero has no size, so
    its miss counts against the moment's absolute total at the current weights,
    which the step recomputes as the weights move. Summing n records rounds by at
    most n machine epsilons of that absolute total, plus n of the smallest
    subnormal where products underflow. The solve stops only when every miss plus
    that bound falls within tolerance, so rounding cannot hide a miss. A nonzero
    target whose tolerance the bound alone fills, where the solve ends, raises as
    too near zero. The bound covers the worst case, so it also refuses some
    targets the arithmetic happens to hit exactly.
    """
    size = np.abs(targets)
    zero = size == 0
    records = moments.shape[1]
    machine = np.finfo(float)

    def check_resolvable(rounding: np.ndarray) -> None:
        if np.any(~zero & (rounding >= TARGET_TOLERANCE)):
            raise ValueError("a target this near zero must be zero")

    # Multipliers on the moments as given; each step rescales them to solve.
    multipliers = np.zeros(moments.shape[0])

    def factors_at(point: np.ndarray) -> np.ndarray:
        return np.exp(np.clip(point @ moments, -30.0, 30.0))

    def dual(point: np.ndarray) -> float:
        return float(weights @ factors_at(point) - point @ targets)

    for _ in range(MAX_NEWTON_STEPS):
        current = factors_at(multipliers) * weights
        total = np.abs(moments) @ current
        scale = np.where(zero, total, size)
        scale[scale == 0] = 1.0
        rounding = records * (machine.eps * total + machine.smallest_subnormal) / scale

        def gap_at(point: np.ndarray) -> np.ndarray:
            return (moments @ (factors_at(point) * weights) - targets) / scale

        gap = gap_at(multipliers)
        worst = np.max(np.abs(gap))
        if np.max(np.abs(gap) + rounding) < TARGET_TOLERANCE:
            return factors_at(multipliers)
        scaled_moments = moments / scale[:, None]
        hessian = (scaled_moments * current) @ scaled_moments.T
        direction = (
            np.linalg.solve(hessian + 1e-12 * np.eye(hessian.shape[0]), -gap) / scale
        )
        value = dual(multipliers)
        slope = (gap * scale) @ direction
        step = 1.0
        # Near the solution the dual stops changing within rounding, so a step
        # also counts as progress when it shrinks the worst miss.
        while (
            dual(multipliers + step * direction) > value + 1e-4 * step * slope
            and np.max(np.abs(gap_at(multipliers + step * direction))) >= worst
        ):
            step /= 2
            if step < 1e-10:
                check_resolvable(rounding)
                raise ValueError("the line search stalled")
        multipliers = multipliers + step * direction
    check_resolvable(rounding)
    raise ValueError("entropy balancing did not reach the targets")


def load_factors(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """The household ids and weight factors a calibration saved, checked first.

    A NaN would turn every comparison against the factors false, so a file must
    hold one finite, positive factor for each distinct household.
    """
    with np.load(path) as saved:
        household_ids, factors = saved["household_id"], saved["factor"]
    if household_ids.ndim != 1 or factors.shape != household_ids.shape:
        raise ValueError(f"{path}: the factors and household ids differ in shape")
    if not np.all(np.isfinite(factors) & (factors > 0)):
        raise ValueError(f"{path}: a factor is not finite and positive")
    if np.unique(household_ids).size != household_ids.size:
        raise ValueError(f"{path}: a household appears twice")
    return household_ids, factors


def load_filing_run(work: Path) -> dict[str, np.ndarray]:
    """A file's 2024 run, with the relationship codes if relationship.py saved them.

    The codes must come from the run's own dataset and list the run's people by id.
    """
    with np.load(work / "filing_2024.npz") as saved:
        run = {name: saved[name] for name in saved.files}
    codes = work / "relationship_2024.npz"
    if codes.exists():
        bundle = json.loads((work / "filing_2024.json").read_text())["bundle"]
        with np.load(codes) as saved:
            if str(saved["dataset_sha256"]) != bundle["runtime_dataset_sha256"]:
                raise ValueError(f"{codes} comes from another dataset than the run")
            if "person.person_id" not in run or not np.array_equal(
                saved["person.person_id"], run["person.person_id"]
            ):
                raise ValueError(f"{codes} lists other people than the run")
            for name in ("person.cps_relationship", "person.cps_marital_status"):
                run[name] = saved[name]
    return run


def apply_weight_factors(sim, year: int, path: Path) -> None:
    """Multiply each household's weight for this year by its saved factor."""
    household_ids, factors = load_factors(path)

    def household_values(variable: str) -> np.ndarray:
        return np.asarray(sim.calculate(variable, period=year).values, dtype=float)

    if not np.array_equal(household_ids, household_values("household_id")):
        raise ValueError("the factors belong to another file's households")
    weights = household_values("household_weight") * factors
    sim.set_input("household_weight", year, weights)
    if not np.allclose(household_values("household_weight"), weights):
        raise ValueError("the simulation kept its old household weights")


def calibrate(
    run: dict[str, np.ndarray],
    detailed: bool = False,
    child_credit: bool = False,
    filers: bool = False,
) -> Calibration:
    moments = household_moments(run) | relationship_moments(run)
    if detailed:
        moments |= family_income_moments(moments)
    if child_credit:
        moments |= child_credit_moments(run)
    if filers:
        moments |= filer_moments(run)
    weights = run["household.household_weight"].astype(float)
    targets = published_targets(moments, weights, detailed, child_credit, filers)
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
    parser.add_argument(
        "--child-credit",
        action="store_true",
        help="Also match the IRS child credit by joint and other returns.",
    )
    parser.add_argument(
        "--filers",
        action="store_true",
        help="Also match IRS returns in total, by head of household and by AGI.",
    )
    args = parser.parse_args()
    run = load_filing_run(args.work)
    result = calibrate(run, args.detailed, args.child_credit, args.filers)
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
