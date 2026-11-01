"""Rerun the March 2025 static FISC estimates with the stack that made them.

fisc_act_10_year_impact.csv landed on 2025-03-12. This script takes one scenario
and one year, with the versions of that date:

- policyengine-us 1.211.0, commit b967cf54a9
- policyengine-us-data 1.18.1, commit db98b43d
- policyengine-core 3.16.3, numpy 1.26.4, pandas 2.2.3, on Python 3.11
- enhanced_cps_2024.h5 at Hugging Face revision 0611cbeda3, the file live that day

PyPI no longer carries that policyengine-us, so build the environment from git:

    git -C policyengine-us archive b967cf54a9 | tar -x -C old-pe-us
    git -C policyengine-us-data archive db98b43d | tar -x -C old-us-data
    uv venv --python 3.11 env
    uv pip install --exclude-newer 2025-03-13T00:00:00Z \
        "policyengine-core>=3.14.1" "microdf-python>=0.4.3" tqdm tables h5py requests
    uv pip install --no-deps ./old-pe-us ./old-us-data
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from policyengine_core.reforms import Reform
from policyengine_us import Microsimulation

PERIOD = "2026-01-01.2100-12-31"
FISC = "gov.contrib.congress.golden.fisc_act"
SCENARIOS = {
    "baseline": None,
    "fisc": {f"{FISC}.in_effect": {PERIOD: True}},
    "fisc_no_bonus": {
        f"{FISC}.in_effect": {PERIOD: True},
        f"{FISC}.family_income_supplement.marriage_bonus_rate": {PERIOD: 0},
    },
}


def run(scenario: str, year: int, dataset: str, out: Path) -> dict:
    policy = SCENARIOS[scenario]
    reform = Reform.from_dict(policy, country_id="us") if policy else None
    sim = Microsimulation(reform=reform, dataset=dataset)
    total = {
        "income_tax": float(
            sim.calculate("income_tax", map_to="household", period=year).sum()
        ),
        "household_net_income": float(
            sim.calculate("household_net_income", period=year).sum()
        ),
    }
    names = ("family_income_supplement_credit",) if policy else ("ctc",)
    for name in names:
        total[name] = float(sim.calculate(name, map_to="household", period=year).sum())
    record = {"scenario": scenario, "year": year, **total}
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{scenario}_{year}.json").write_text(json.dumps(record, indent=1))
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=sorted(SCENARIOS))
    parser.add_argument("year", type=int)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(run(args.scenario, args.year, args.dataset, args.out))
