"""Fetch FISC Act comparisons from the production PolicyEngine API.

Policy 76612 holds the FISC Act and policy 99021 holds the same reform with the
marriage bonus at zero. Policy 2 is current law. Policies 99022 to 99025 hold the
other single-provision variants in analysis.SCENARIOS, run for 2026.

    uv run python us/congress/fisc_marriage_bonus/fetch_api.py results/api

The endpoint returns `computing` until a job finishes, so this polls until every
comparison has landed, and it skips any file already on disk. Each saved file
keeps the outputs this analysis reads and the versions of the run behind them.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

FISC = 76612
FISC_NO_BONUS = 99021
CURRENT_LAW = 2
FISC_NO_NEWBORN_ADD_ON = 99022
FISC_NO_PHASE_OUT = 99023
FISC_NO_AGI_CAP = 99024
FISC_CTC_REPEAL_ONLY = 99025
YEARS = range(2026, 2036)
COMPARISONS = (
    (FISC, CURRENT_LAW, YEARS),
    (FISC_NO_BONUS, CURRENT_LAW, YEARS),
    (FISC, FISC_NO_BONUS, YEARS),
    (FISC, FISC_NO_NEWBORN_ADD_ON, (2026,)),
    (FISC, FISC_NO_PHASE_OUT, (2026,)),
    (FISC, FISC_NO_AGI_CAP, (2026,)),
    (FISC_CTC_REPEAL_ONLY, CURRENT_LAW, (2026,)),
    (FISC_NO_BONUS, FISC_CTC_REPEAL_ONLY, (2026,)),
)
API = "https://api.policyengine.org/us/economy"
POLL_SECONDS = 60
MAX_SECONDS = 4 * 3600
KEPT_OUTPUTS = (
    "budget",
    "detailed_budget",
    "decile",
    "intra_decile",
    "poverty",
    "inequality",
    "model_version",
    "data_version",
    "policyengine_bundle",
)


def fetch(policy: int, baseline: int, year: int) -> dict:
    url = f"{API}/{policy}/over/{baseline}?region=us&time_period={year}"
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + MAX_SECONDS
    while time.time() < deadline:
        waiting = 0
        for policy, baseline, years in COMPARISONS:
            for year in years:
                path = out / f"econ_{policy}_over_{baseline}_{year}.json"
                if path.exists():
                    continue
                reply = fetch(policy, baseline, year)
                if reply.get("status") == "ok" and reply.get("result"):
                    kept = {key: reply["result"][key] for key in KEPT_OUTPUTS}
                    path.write_text(json.dumps(kept, indent=1, sort_keys=True))
                    print(f"landed {path.name}", flush=True)
                else:
                    waiting += 1
        print(f"{waiting} comparisons still computing", flush=True)
        if not waiting:
            return
        time.sleep(POLL_SECONDS)
    raise TimeoutError("comparisons still computing at the deadline")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
