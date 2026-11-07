# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["policyengine[models]==6.11.1"]
# ///
"""Save each person's relationship to the householder, from the certified dataset.

    uv run us/congress/fisc_marriage_bonus/relationship.py <work-dir>

The current dataset keeps the 2024 ASEC's A_EXPRRP code, each person's relationship
to the household's reference person, and A_MARITL, each person's marital status,
though the model reads neither. The ACS counts married-couple households and own
children by those relationships, and an own child has never married, so
reweight.py takes its household targets from the codes. This reads the file named
in <work-dir>/filing_2024.json, checks its sha256, checks that it lists the run's
people by id in the run's order, and saves <work-dir>/relationship_2024.npz.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from huggingface_hub import hf_hub_download

RELATIONSHIP_COLUMN = "A_EXPRRP"
MARITAL_STATUS_COLUMN = "A_MARITL"
COLUMNS = (
    "person_id",
    "person_household_id",
    "age",
    RELATIONSHIP_COLUMN,
    MARITAL_STATUS_COLUMN,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def dataset_path(bundle: dict) -> Path:
    """Download the run's dataset at its pinned revision, or reuse the cached copy."""
    repo, filename = (
        bundle["runtime_dataset_uri"].removeprefix("hf://").split("@")[0].rsplit("/", 1)
    )
    return Path(
        hf_hub_download(
            repo_id=repo,
            filename=filename,
            revision=bundle["runtime_dataset_revision"],
            repo_type=bundle["runtime_dataset_repo_type"],
        )
    )


def relationship_codes(
    people: pd.DataFrame, run: dict[str, np.ndarray]
) -> dict[str, np.ndarray]:
    """The codes in the run's person order, or an error if the files disagree."""
    if not np.array_equal(people["person_id"].to_numpy(), run["person.person_id"]):
        raise ValueError("the dataset lists other people or another order")
    if not np.array_equal(
        people["person_household_id"].to_numpy(), run["person.person_household_id"]
    ):
        raise ValueError("the dataset puts people in other households")
    if not np.array_equal(
        people["age"].to_numpy().astype(np.float32), run["person.age"]
    ):
        raise ValueError("the dataset's ages differ from the run's")
    code = people[RELATIONSHIP_COLUMN].to_numpy()
    if not np.all(np.isin(code, np.arange(1, 15))):
        raise ValueError(f"a {RELATIONSHIP_COLUMN} code falls outside 1 to 14")
    marital_status = people[MARITAL_STATUS_COLUMN].to_numpy()
    if not np.all(np.isin(marital_status, np.arange(1, 8))):
        raise ValueError(f"a {MARITAL_STATUS_COLUMN} code falls outside 1 to 7")
    return {
        "person.person_id": run["person.person_id"],
        "person.cps_relationship": code.astype(np.int8),
        "person.cps_marital_status": marital_status.astype(np.int8),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    args = parser.parse_args()
    bundle = json.loads((args.work / "filing_2024.json").read_text())["bundle"]
    path = dataset_path(bundle)
    if sha256(path) != bundle["runtime_dataset_sha256"]:
        raise ValueError(f"{path} is not the run's dataset")
    people = pd.read_hdf(path, "person", columns=list(COLUMNS))
    with np.load(args.work / "filing_2024.npz") as saved:
        run = {name: saved[name] for name in saved.files}
    codes = relationship_codes(people, run)
    np.savez_compressed(
        args.work / "relationship_2024.npz",
        dataset_sha256=bundle["runtime_dataset_sha256"],
        **codes,
    )
    counts = np.bincount(codes["person.cps_relationship"], minlength=15)[1:]
    print({code: int(count) for code, count in enumerate(counts, 1) if count})
