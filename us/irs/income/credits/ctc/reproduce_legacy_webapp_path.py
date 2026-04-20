"""
Reproduce the legacy PolicyEngine web-app path for reform 94589.

This script is meant to be run in the old macro environment that powered the
legacy app/API path investigated for November 4, 2025:

    uv run --python 3.11 \
      --with policyengine==0.3.9 \
      --with policyengine-us==1.425.4 \
      --with policyengine-core==3.20.1 \
      python us/irs/income/credits/ctc/reproduce_legacy_webapp_path.py

By default it uses the local `cps_2023.h5` file from the policyengine-us-data
repo, which is the most reproducible approximation we found for the legacy
national-US web path when no `dataset=enhanced_cps` query param was present.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from policyengine import Simulation
from policyengine_core.reforms import Reform


DEFAULT_DATASET = Path(
    "/Users/pavelmakarchuk/policyengine-us-data/policyengine_us_data/storage/cps_2023.h5"
)


def build_reform() -> Reform:
    return Reform.from_dict(
        {
            "gov.irs.credits.eitc.max[0].amount": {
                "2025-01-01.2100-12-31": 2000
            },
            "gov.irs.credits.eitc.max[1].amount": {
                "2025-01-01.2100-12-31": 2000
            },
            "gov.irs.credits.eitc.max[2].amount": {
                "2025-01-01.2100-12-31": 2000
            },
            "gov.irs.credits.eitc.max[3].amount": {
                "2025-01-01.2100-12-31": 2000
            },
            "gov.irs.credits.ctc.phase_out.amount": {
                "2025-01-01.2100-12-31": 25
            },
            "gov.irs.credits.ctc.amount.arpa[0].amount": {
                "2025-01-01.2100-12-31": 4800
            },
            "gov.irs.credits.ctc.amount.arpa[1].amount": {
                "2025-01-01.2100-12-31": 4800
            },
            "gov.irs.credits.ctc.phase_out.arpa.amount": {
                "2025-01-01.2100-12-31": 25
            },
            "gov.contrib.ctc.minimum_refundable.in_effect": {
                "2025-01-01.2100-12-31": True
            },
            "gov.contrib.ctc.per_child_phase_in.in_effect": {
                "2025-01-01.2100-12-31": True
            },
            "gov.irs.credits.ctc.phase_out.arpa.in_effect": {
                "2025-01-01.2100-12-31": True
            },
            "gov.irs.credits.ctc.refundable.phase_in.rate": {
                "2025-01-01.2100-12-31": 0.2
            },
            "gov.irs.credits.eitc.phase_in_rate[0].amount": {
                "2025-01-01.2100-12-31": 0.2
            },
            "gov.irs.credits.eitc.phase_in_rate[1].amount": {
                "2025-01-01.2100-12-31": 0.2
            },
            "gov.irs.credits.eitc.phase_in_rate[2].amount": {
                "2025-01-01.2100-12-31": 0.2
            },
            "gov.irs.credits.eitc.phase_in_rate[3].amount": {
                "2025-01-01.2100-12-31": 0.2
            },
            "gov.contrib.ctc.per_child_phase_out.in_effect": {
                "2025-01-01.2100-12-31": True
            },
            "gov.irs.credits.ctc.phase_out.threshold.JOINT": {
                "2025-01-01.2100-12-31": 200000
            },
            "gov.irs.credits.ctc.refundable.individual_max": {
                "2025-01-01.2100-12-31": 4800
            },
            "gov.irs.credits.eitc.phase_out.rate[0].amount": {
                "2025-01-01.2100-12-31": 0.1
            },
            "gov.irs.credits.eitc.phase_out.rate[1].amount": {
                "2025-01-01.2100-12-31": 0.1
            },
            "gov.irs.credits.eitc.phase_out.rate[2].amount": {
                "2025-01-01.2100-12-31": 0.1
            },
            "gov.irs.credits.eitc.phase_out.rate[3].amount": {
                "2025-01-01.2100-12-31": 0.1
            },
            "gov.irs.credits.ctc.phase_out.threshold.SINGLE": {
                "2025-01-01.2100-12-31": 100000
            },
            "gov.irs.credits.eitc.phase_out.start[0].amount": {
                "2025-01-01.2100-12-31": 20000
            },
            "gov.irs.credits.eitc.phase_out.start[1].amount": {
                "2025-01-01.2100-12-31": 20000
            },
            "gov.irs.credits.eitc.phase_out.start[2].amount": {
                "2025-01-01.2100-12-31": 20000
            },
            "gov.irs.credits.eitc.phase_out.start[3].amount": {
                "2025-01-01.2100-12-31": 20000
            },
            "gov.irs.credits.ctc.phase_out.threshold.SEPARATE": {
                "2025-01-01.2100-12-31": 100000
            },
            "gov.contrib.ctc.per_child_phase_out.avoid_overlap": {
                "2025-01-01.2100-12-31": True
            },
            "gov.irs.credits.ctc.refundable.phase_in.threshold": {
                "2025-01-01.2100-12-31": 0
            },
            "gov.irs.credits.ctc.phase_out.arpa.threshold.JOINT": {
                "2025-01-01.2100-12-31": 35000
            },
            "gov.contrib.ctc.minimum_refundable.amount[0].amount": {
                "2025-01-01.2100-12-31": 2400
            },
            "gov.contrib.ctc.minimum_refundable.amount[1].amount": {
                "2025-01-01.2100-12-31": 2400
            },
            "gov.irs.credits.ctc.phase_out.arpa.threshold.SINGLE": {
                "2025-01-01.2100-12-31": 25000
            },
            "gov.irs.credits.eitc.phase_out.joint_bonus[0].amount": {
                "2025-01-01.2100-12-31": 7000
            },
            "gov.irs.credits.eitc.phase_out.joint_bonus[1].amount": {
                "2025-01-01.2100-12-31": 7000
            },
            "gov.irs.credits.ctc.phase_out.arpa.threshold.SEPARATE": {
                "2025-01-01.2100-12-31": 25000
            },
            "gov.irs.credits.ctc.phase_out.threshold.SURVIVING_SPOUSE": {
                "2025-01-01.2100-12-31": 100000
            },
            "gov.irs.credits.ctc.phase_out.threshold.HEAD_OF_HOUSEHOLD": {
                "2025-01-01.2100-12-31": 100000
            },
            "gov.irs.credits.ctc.phase_out.arpa.threshold.SURVIVING_SPOUSE": {
                "2025-01-01.2100-12-31": 25000
            },
            "gov.irs.credits.ctc.phase_out.arpa.threshold.HEAD_OF_HOUSEHOLD": {
                "2025-01-01.2100-12-31": 25000
            },
        },
        country_id="us",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET),
        help="Path to the dataset file used by the old macro simulation.",
    )
    parser.add_argument(
        "--time-period",
        type=int,
        default=2025,
        help="Simulation year.",
    )
    parser.add_argument(
        "--region",
        default="us",
        help="Region argument passed to the old macro simulation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_path = Path(args.dataset).expanduser()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    simulation = Simulation(
        country="us",
        scope="macro",
        reform=build_reform(),
        time_period=args.time_period,
        region=args.region,
        data=str(dataset_path),
    )
    impact = simulation.calculate_economy_comparison().model_dump()

    poverty_all = impact["poverty"]["poverty"]["all"]
    winners_losers = impact["intra_decile"]["all"]

    output = {
        "assumptions": {
            "scope": "macro",
            "country": "us",
            "region": args.region,
            "time_period": args.time_period,
            "dataset": str(dataset_path),
            "legacy_path": "national US web-app run with no dataset=enhanced_cps",
        },
        "budget": impact["budget"],
        "poverty_all": {
            **poverty_all,
            "relative_change": poverty_all["reform"] / poverty_all["baseline"] - 1,
        },
        "winners_losers_all": winners_losers,
    }

    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
