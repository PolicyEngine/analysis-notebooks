"""Definitions and pure calculations for the FISC Act marriage bonus analysis.

Nothing here loads the model or microdata, so the property tests in
test_analysis.py cover it without a microsimulation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

YEARS = tuple(range(2026, 2036))
STATUTORY_BONUS_RATE = 0.2

PERIOD = "2026-01-01.2100-12-31"
FISC = "gov.contrib.congress.golden.fisc_act"
SUPPLEMENT = f"{FISC}.family_income_supplement"
BONUS_RATE = f"{SUPPLEMENT}.marriage_bonus_rate"

# Policy 76612 stores in_effect as 0.01. The reform gate reads any non-zero
# value as true, and this keeps the variant identical to 76612 in every
# parameter but the bonus.
FISC_POLICY = {f"{FISC}.in_effect": {PERIOD: 0.01}}

# Each variant changes one provision of the full reform. The no-cap variant
# leaves the cap at zero for tax units with zero or negative AGI, because the
# reform floors the cap at zero; it sets a fraction no AGI above $1 can reach.
SCENARIOS: dict[str, dict] = {
    "baseline": {},
    "fisc": FISC_POLICY,
    "fisc_no_bonus": {**FISC_POLICY, BONUS_RATE: {PERIOD: 0}},
    "fisc_restored_bonus": {**FISC_POLICY, BONUS_RATE: {PERIOD: STATUTORY_BONUS_RATE}},
    "fisc_no_newborn_add_on": {
        **FISC_POLICY,
        f"{SUPPLEMENT}.amount.base[0].amount": {PERIOD: 4_800},
    },
    "fisc_no_phase_out": {
        **FISC_POLICY,
        f"{SUPPLEMENT}.phase_out.joint[1].rate": {PERIOD: 0},
        f"{SUPPLEMENT}.phase_out.other[1].rate": {PERIOD: 0},
    },
    "fisc_no_agi_cap": {**FISC_POLICY, f"{SUPPLEMENT}.agi_fraction": {PERIOD: 1e9}},
}

# The 2026 child tax credit schedule in the model the March 2025 run used, which
# predates the 2025 reconciliation law. Applied to today's model, it isolates how
# much the repealed credit's size moves the net cost of FISC.
CTC = "gov.irs.credits.ctc"
MARCH_2025_CTC = {
    f"{CTC}.amount.base[0].amount": {PERIOD: 1_000},
    f"{CTC}.amount.adult_dependent": {PERIOD: 0},
    f"{CTC}.phase_out.threshold.JOINT": {PERIOD: 110_000},
    f"{CTC}.phase_out.threshold.SINGLE": {PERIOD: 75_000},
    f"{CTC}.phase_out.threshold.HEAD_OF_HOUSEHOLD": {PERIOD: 75_000},
    f"{CTC}.phase_out.threshold.SURVIVING_SPOUSE": {PERIOD: 75_000},
    f"{CTC}.phase_out.threshold.SEPARATE": {PERIOD: 55_000},
    f"{CTC}.refundable.individual_max": {PERIOD: 1_000},
    f"{CTC}.refundable.phase_in.threshold": {PERIOD: 3_000},
    f"{CTC}.adult_ssn_requirement_applies": {PERIOD: False},
    f"{CTC}.child_ssn_requirement_applies": {PERIOD: False},
}
SCENARIOS["baseline_march_2025_ctc"] = MARCH_2025_CTC

# A dollar test keeps float32 rounding from counting as receipt.
RECEIPT_THRESHOLD = 0.005
NEGATIVE_INCOME_GROUP = -1


def closed_form_credit(
    base_amount: np.ndarray,
    joint: np.ndarray,
    agi: np.ndarray,
    bonus_rate: float = STATUTORY_BONUS_RATE,
) -> np.ndarray:
    """H.R. 1308 Sec. 2(d) as an annual formula, in the bill's order.

    (d)(2) raises the payment by the bonus, (d)(3) phases it out and (d)(4)
    caps it at AGI. The test suite checks the model against this reference.
    """
    base_amount = np.asarray(base_amount, dtype=float)
    joint = np.asarray(joint, dtype=bool)
    agi = np.asarray(agi, dtype=float)
    with_bonus = base_amount * (1 + joint * bonus_rate)
    threshold = np.where(joint, 250_000, 125_000)
    phase_out = 0.2 * np.maximum(agi - threshold, 0)
    return np.minimum(np.maximum(with_bonus - phase_out, 0), np.maximum(agi, 0))


def closed_form_bonus(
    base_amount: np.ndarray,
    joint: np.ndarray,
    agi: np.ndarray,
    bonus_rate: float = STATUTORY_BONUS_RATE,
) -> np.ndarray:
    """Dollars the bonus adds once the phase-out and cap have applied."""
    return closed_form_credit(base_amount, joint, agi, bonus_rate) - closed_form_credit(
        base_amount, joint, agi, 0
    )


def weighted_decile(
    income: np.ndarray, household_weight: np.ndarray, people: np.ndarray
) -> np.ndarray:
    """Rank households into person-weighted deciles of a ranking income.

    Follows the convention in household_income_decile: each decile holds about
    a tenth of people, and households with negative income take group -1.
    """
    income = np.asarray(income, dtype=float)
    weight = np.asarray(household_weight, dtype=float) * np.asarray(people, dtype=float)
    order = np.argsort(income, kind="stable")
    position = np.empty(len(income), dtype=float)
    position[order] = np.cumsum(weight[order]) / weight.sum()
    groups = np.clip(np.ceil(position * 10), 1, 10).astype(int)
    return np.where(income < 0, NEGATIVE_INCOME_GROUP, groups)


def decile_table(
    groups: np.ndarray,
    amount: np.ndarray,
    income: np.ndarray,
    household_weight: np.ndarray,
) -> pd.DataFrame:
    """Dollars, shares and receipt by income group, one row per group.

    The negative-income group keeps its own row so the rows sum to the total.
    """
    frame = pd.DataFrame(
        {
            "group": np.asarray(groups),
            "amount": np.asarray(amount, dtype=float),
            "income": np.asarray(income, dtype=float),
            "weight": np.asarray(household_weight, dtype=float),
        }
    )
    frame["dollars"] = frame.amount * frame.weight
    frame["income_dollars"] = frame.income * frame.weight
    frame["receiving"] = frame.weight * (frame.amount.abs() > RECEIPT_THRESHOLD)
    table = frame.groupby("group", sort=True).agg(
        households=("weight", "sum"),
        households_receiving=("receiving", "sum"),
        dollars=("dollars", "sum"),
        income_dollars=("income_dollars", "sum"),
    )
    total = table.dollars.sum()
    table["share_of_total"] = table.dollars / total if total else 0.0
    table["share_of_households_receiving"] = (
        table.households_receiving / table.households
    )
    table["mean_per_household"] = table.dollars / table.households
    table["mean_per_receiving_household"] = (
        table.dollars / table.households_receiving.where(table.households_receiving > 0)
    )
    table["percent_of_income"] = (
        100 * table.dollars / table.income_dollars.where(table.income_dollars > 0)
    )
    return table.reset_index()


def concentration_coefficient(
    amount: np.ndarray,
    rank_income: np.ndarray,
    household_weight: np.ndarray,
    people: np.ndarray,
) -> float:
    """Concentration of an amount across people ranked by income.

    Each person takes an equal part of the household amount. The coefficient
    runs from -1, with everything at the bottom, to +1, with everything at the
    top; zero means an equal amount per person. A positive transfer whose
    coefficient exceeds the Gini of income raises income by a larger percentage
    at the top than at the bottom.
    """
    amount = np.asarray(amount, dtype=float)
    weight = np.asarray(household_weight, dtype=float) * np.asarray(people, dtype=float)
    per_person = amount / np.asarray(people, dtype=float)
    order = np.argsort(np.asarray(rank_income, dtype=float), kind="stable")
    weight = weight[order]
    per_person = per_person[order]
    total_weight = weight.sum()
    midpoint = (np.cumsum(weight) - weight / 2) / total_weight
    mean = (weight * per_person).sum() / total_weight
    return float(
        2 * (weight * per_person * (midpoint - 0.5)).sum() / total_weight / mean
    )


def group_shares(table: pd.DataFrame) -> dict[str, float]:
    """Share of dollars reaching the bottom half and the top three deciles."""
    ranked = table[table.group >= 1]
    total = table.dollars.sum()
    return {
        "bottom_five_deciles": float(ranked[ranked.group <= 5].dollars.sum() / total),
        "top_three_deciles": float(ranked[ranked.group >= 8].dollars.sum() / total),
    }
