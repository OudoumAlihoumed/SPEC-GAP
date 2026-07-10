"""Deterministic matched-pair splits for Scenario 1 evaluation.

Clean and injected trajectories derived from the same task, injection variant,
and seed must remain in the same split. The caller supplies that grouping as
``pair_id`` so this module does not infer experimental identity from filenames.
"""

from __future__ import annotations

import hashlib
from typing import Iterable


REQUIRED_SPLIT_FIELDS = {"trajectory_id", "pair_id", "condition"}
EXPECTED_CONDITIONS = {"clean", "injected"}


def build_matched_split_manifest(
    rows: Iterable[dict],
    *,
    train_fraction: float = 0.6,
    validation_fraction: float = 0.2,
    random_state: int = 42,
) -> dict:
    """Assign complete matched pairs to deterministic train/validation/test splits."""

    rows = list(rows)
    pair_trajectories = _validate_and_group_pairs(rows)
    pair_ids = sorted(
        pair_trajectories,
        key=lambda pair_id: hashlib.sha256(
            f"{random_state}:{pair_id}".encode("utf-8")
        ).hexdigest(),
    )
    counts = _split_counts(
        len(pair_ids),
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
    )

    assignments: dict[str, str] = {}
    start = 0
    for split_name in ("train", "validation", "test"):
        end = start + counts[split_name]
        for pair_id in pair_ids[start:end]:
            assignments[pair_id] = split_name
        start = end

    pairs = []
    for pair_id in sorted(pair_trajectories):
        grouped = pair_trajectories[pair_id]
        pairs.append({
            "pair_id": pair_id,
            "split": assignments[pair_id],
            "conditions": sorted(grouped["conditions"]),
            "trajectory_ids": sorted(grouped["trajectory_ids"]),
        })

    manifest = {
        "schema_version": "spec_gap.matched_splits.v1",
        "random_state": random_state,
        "fractions": {
            "train": train_fraction,
            "validation": validation_fraction,
            "test": 1.0 - train_fraction - validation_fraction,
        },
        "n_pairs": len(pair_ids),
        "counts": counts,
        "pairs": pairs,
    }
    validate_split_manifest(manifest)
    return manifest


def apply_split_manifest(rows: Iterable[dict], manifest: dict) -> list[dict]:
    """Return row copies annotated with the split assigned to their pair."""

    validate_split_manifest(manifest)
    assignment = {
        entry["pair_id"]: entry["split"]
        for entry in manifest["pairs"]
    }
    annotated = []
    for row in rows:
        pair_id = row.get("pair_id")
        if pair_id not in assignment:
            raise ValueError(f"pair_id {pair_id!r} is missing from the split manifest")
        annotated.append({**row, "split": assignment[pair_id]})
    return annotated


def validate_split_manifest(manifest: dict) -> None:
    """Fail closed on pair leakage or incomplete split manifests."""

    pairs = manifest.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("Split manifest must contain at least one matched pair.")

    seen_pairs: set[str] = set()
    trajectory_split: dict[str, str] = {}
    split_pairs = {"train": 0, "validation": 0, "test": 0}
    for entry in pairs:
        pair_id = entry.get("pair_id")
        split = entry.get("split")
        if not pair_id or pair_id in seen_pairs:
            raise ValueError(f"Duplicate or missing pair_id in split manifest: {pair_id!r}")
        if split not in split_pairs:
            raise ValueError(f"Unsupported split {split!r} for pair {pair_id!r}")
        conditions = set(entry.get("conditions") or [])
        if conditions != EXPECTED_CONDITIONS:
            raise ValueError(
                f"Pair {pair_id!r} must contain clean and injected conditions; "
                f"found {sorted(conditions)}"
            )
        trajectory_ids = entry.get("trajectory_ids") or []
        if not trajectory_ids:
            raise ValueError(f"Pair {pair_id!r} has no trajectory_ids")
        for trajectory_id in trajectory_ids:
            previous = trajectory_split.get(trajectory_id)
            if previous is not None and previous != split:
                raise ValueError(
                    f"Trajectory {trajectory_id!r} leaks across {previous!r} and {split!r}"
                )
            trajectory_split[trajectory_id] = split
        seen_pairs.add(pair_id)
        split_pairs[split] += 1

    missing_splits = [name for name, count in split_pairs.items() if count == 0]
    if missing_splits:
        raise ValueError(f"Split manifest has no pairs in: {missing_splits}")


def _validate_and_group_pairs(rows: list[dict]) -> dict[str, dict[str, set[str]]]:
    if not rows:
        raise ValueError("At least one prediction row is required to build splits.")

    pair_trajectories: dict[str, dict[str, set[str]]] = {}
    trajectory_pair: dict[str, str] = {}
    for index, row in enumerate(rows):
        missing = sorted(REQUIRED_SPLIT_FIELDS - set(row))
        if missing:
            raise ValueError(f"Row {index} is missing split fields: {missing}")
        trajectory_id = str(row["trajectory_id"])
        pair_id = str(row["pair_id"])
        condition = str(row["condition"])
        if condition not in EXPECTED_CONDITIONS:
            raise ValueError(
                f"Row {index} has unsupported condition {condition!r}; "
                "expected 'clean' or 'injected'"
            )
        previous_pair = trajectory_pair.setdefault(trajectory_id, pair_id)
        if previous_pair != pair_id:
            raise ValueError(
                f"Trajectory {trajectory_id!r} belongs to multiple pairs: "
                f"{previous_pair!r} and {pair_id!r}"
            )
        grouped = pair_trajectories.setdefault(
            pair_id,
            {"trajectory_ids": set(), "conditions": set()},
        )
        grouped["trajectory_ids"].add(trajectory_id)
        grouped["conditions"].add(condition)

    for pair_id, grouped in pair_trajectories.items():
        if grouped["conditions"] != EXPECTED_CONDITIONS:
            raise ValueError(
                f"Pair {pair_id!r} must contain clean and injected conditions; "
                f"found {sorted(grouped['conditions'])}"
            )
    return pair_trajectories


def _split_counts(
    n_pairs: int,
    *,
    train_fraction: float,
    validation_fraction: float,
) -> dict[str, int]:
    test_fraction = 1.0 - train_fraction - validation_fraction
    fractions = (train_fraction, validation_fraction, test_fraction)
    if any(fraction <= 0.0 for fraction in fractions):
        raise ValueError("Train, validation, and test fractions must all be positive.")
    if n_pairs < 3:
        raise ValueError("At least three matched pairs are required for three non-empty splits.")

    train = max(1, round(n_pairs * train_fraction))
    validation = max(1, round(n_pairs * validation_fraction))
    test = n_pairs - train - validation
    while test < 1 and train > 1:
        train -= 1
        test += 1
    while test < 1 and validation > 1:
        validation -= 1
        test += 1
    if test < 1:
        raise ValueError("Fractions cannot produce three non-empty splits.")
    return {"train": train, "validation": validation, "test": test}
