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

# Each variant changes one provision of the full reform. No parameter can lift
# the cap at zero or negative AGI, because the reform floors the cap at zero, so
# fisc_agi_cap_at_zero_only lifts it above zero AGI, which the API can run, and
# run.py removes it at every AGI for fisc_no_agi_cap.
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
    "fisc_agi_cap_at_zero_only": {
        **FISC_POLICY,
        f"{SUPPLEMENT}.agi_fraction": {PERIOD: 1e9},
    },
    "fisc_no_agi_cap": FISC_POLICY,
    "fisc_ctc_repeal_only": {
        **FISC_POLICY,
        f"{SUPPLEMENT}.amount.base[0].amount": {PERIOD: 0},
        f"{SUPPLEMENT}.amount.base[1].amount": {PERIOD: 0},
        f"{SUPPLEMENT}.amount.base[2].amount": {PERIOD: 0},
    },
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
BILL_MONTHLY_PHASE_OUT_STEP = 16.67


def uncapped_credit(
    base_amount: np.ndarray,
    joint: np.ndarray,
    agi: np.ndarray,
    bonus_rate: float = STATUTORY_BONUS_RATE,
) -> np.ndarray:
    """The model's annual credit after the bonus and phase-out, before the cap."""
    base_amount = np.asarray(base_amount, dtype=float)
    joint = np.asarray(joint, dtype=bool)
    agi = np.asarray(agi, dtype=float)
    with_bonus = base_amount * (1 + joint * bonus_rate)
    threshold = np.where(joint, 250_000, 125_000)
    phase_out = 0.2 * np.maximum(agi - threshold, 0)
    return np.maximum(with_bonus - phase_out, 0)


def closed_form_credit(
    base_amount: np.ndarray,
    joint: np.ndarray,
    agi: np.ndarray,
    bonus_rate: float = STATUTORY_BONUS_RATE,
) -> np.ndarray:
    """The model's annual reading of H.R. 1308 Sec. 2(d), in the bill's order.

    (d)(2) raises the payment by the bonus, (d)(3) phases it out and (d)(4)
    caps it at AGI. The model replaces the bill's monthly steps with a smooth
    20 cents per dollar, and stepped_credit shows the bill's steps.
    """
    capped = np.minimum(
        uncapped_credit(base_amount, joint, agi, bonus_rate),
        np.maximum(np.asarray(agi, dtype=float), 0),
    )
    return capped


def stepped_credit(
    base_amount: np.ndarray,
    joint: np.ndarray,
    agi: np.ndarray,
    bonus_rate: float = STATUTORY_BONUS_RATE,
) -> np.ndarray:
    """Sec. 2(d) with the bill's phase-out, $16.67 a month per whole $1,000."""
    base_amount = np.asarray(base_amount, dtype=float)
    joint = np.asarray(joint, dtype=bool)
    agi = np.asarray(agi, dtype=float)
    threshold = np.where(joint, 250_000, 125_000)
    steps = np.floor(np.maximum(agi - threshold, 0) / 1_000)
    with_bonus = base_amount * (1 + joint * bonus_rate)
    reduced = np.maximum(with_bonus - 12 * BILL_MONTHLY_PHASE_OUT_STEP * steps, 0)
    return np.minimum(reduced, np.maximum(agi, 0))


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


def bonus_lost_to_limits(
    base_amount: np.ndarray,
    joint: np.ndarray,
    agi: np.ndarray,
    bonus_rate: float = STATUTORY_BONUS_RATE,
) -> tuple[np.ndarray, np.ndarray]:
    """Statutory bonus the phase-out removes, then the bonus the AGI cap removes.

    Follows the bill's order, so the two parts and the bonus paid sum to the
    statutory bonus, the rate times a joint filer's base amount.
    """
    base_amount = np.asarray(base_amount, dtype=float)
    joint = np.asarray(joint, dtype=bool)
    agi = np.asarray(agi, dtype=float)
    threshold = np.where(joint, 250_000, 125_000)
    phase_out = 0.2 * np.maximum(agi - threshold, 0)
    with_bonus = np.maximum(base_amount * (1 + joint * bonus_rate) - phase_out, 0)
    without_bonus = np.maximum(base_amount - phase_out, 0)
    statutory = base_amount * joint * bonus_rate
    return (
        statutory - (with_bonus - without_bonus),
        with_bonus
        - without_bonus
        - closed_form_bonus(base_amount, joint, agi, bonus_rate),
    )


def weighted_decile(
    income: np.ndarray, household_weight: np.ndarray, people: np.ndarray
) -> np.ndarray:
    """Rank households into person-weighted deciles of a ranking income.

    Follows the convention in household_income_decile: each decile holds about
    a tenth of people, households with negative income take group -1, and tied
    households all take the cumulative weight at the end of their tie, so they
    share a group.
    """
    income = np.asarray(income, dtype=float)
    weight = np.asarray(household_weight, dtype=float) * np.asarray(people, dtype=float)
    order = np.argsort(income, kind="stable")
    ranked = income[order]
    end_of_tie = np.searchsorted(ranked, ranked, side="right") - 1
    position = np.empty(len(income), dtype=float)
    position[order] = np.cumsum(weight[order])[end_of_tie] / weight.sum()
    groups = np.clip(np.ceil(position * 10), 1, 10).astype(int)
    return np.where(income < 0, NEGATIVE_INCOME_GROUP, groups)


def decile_table(
    groups: np.ndarray,
    amount: np.ndarray,
    income: np.ndarray,
    household_weight: np.ndarray,
    people: np.ndarray | None = None,
) -> pd.DataFrame:
    """Dollars, shares and receipt by income group, one row per group.

    The negative-income group keeps its own row so the rows sum to the total.
    Pass people to add the mean per person.
    """
    frame = pd.DataFrame(
        {
            "group": np.asarray(groups),
            "amount": np.asarray(amount, dtype=float),
            "income": np.asarray(income, dtype=float),
            "weight": np.asarray(household_weight, dtype=float),
            "people": 1.0 if people is None else np.asarray(people, dtype=float),
        }
    )
    frame["dollars"] = frame.amount * frame.weight
    frame["income_dollars"] = frame.income * frame.weight
    frame["receiving"] = frame.weight * (frame.amount.abs() > RECEIPT_THRESHOLD)
    frame["weighted_people"] = frame.people * frame.weight
    table = frame.groupby("group", sort=True).agg(
        households=("weight", "sum"),
        households_receiving=("receiving", "sum"),
        dollars=("dollars", "sum"),
        income_dollars=("income_dollars", "sum"),
        weighted_people=("weighted_people", "sum"),
    )
    if people is not None:
        table["mean_per_person"] = table.dollars / table.weighted_people
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
    amount: np.ndarray, rank_income: np.ndarray, weight: np.ndarray
) -> float:
    """Concentration of an amount across weighted units ranked by income.

    Units with equal income share a midrank. The coefficient runs from -1, with
    everything at the bottom, to +1, with everything at the top, and zero means
    an equal amount per unit. Compare it with the Gini of income in the same
    units: a positive transfer scoring below that Gini raises income by a larger
    percentage at the bottom than at the top.
    """
    amount = np.asarray(amount, dtype=float)
    weight = np.asarray(weight, dtype=float)
    _, tie_group = np.unique(np.asarray(rank_income, dtype=float), return_inverse=True)
    group_weight = np.bincount(tie_group, weights=weight)
    midpoint = (np.cumsum(group_weight) - group_weight / 2) / group_weight.sum()
    share = weight * amount / (weight * amount).sum()
    return float(2 * (share * (midpoint[tie_group] - 0.5)).sum())


def weighted_gini(income: np.ndarray, weight: np.ndarray) -> float:
    """Gini of income across weighted units."""
    income = np.asarray(income, dtype=float)
    weight = np.asarray(weight, dtype=float)
    if (income * weight).sum() == 0:
        return 0.0
    return concentration_coefficient(income, income, weight)


def group_shares(table: pd.DataFrame) -> dict[str, float]:
    """Share of dollars reaching the bottom half and the top three deciles."""
    ranked = table[table.group >= 1]
    total = table.dollars.sum()
    return {
        "bottom_five_deciles": float(ranked[ranked.group <= 5].dollars.sum() / total),
        "top_three_deciles": float(ranked[ranked.group >= 8].dollars.sum() / total),
    }
