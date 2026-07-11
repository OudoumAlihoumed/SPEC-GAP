"""Leakage-safe match-group splits for Scenario 1 evaluation."""

from __future__ import annotations

import hashlib
from typing import Iterable


REQUIRED_SPLIT_FIELDS = {
    "trajectory_id",
    "match_group_id",
    "condition",
    "hop_mode",
    "thinking_mode",
}
EXPECTED_CELLS = {
    ("clean", "2-hop"),
    ("injected", "2-hop"),
    ("clean", "3-hop"),
    ("injected", "3-hop"),
}


def build_match_group_split_manifest(
    rows: Iterable[dict],
    *,
    train_fraction: float = 0.6,
    validation_fraction: float = 0.2,
    random_state: int = 42,
) -> dict:
    """Assign complete four-trajectory match groups to train/validation/test."""

    grouped = _validate_and_group(rows)
    group_ids = _ordered_group_ids(grouped, random_state=random_state)
    counts = _split_counts(
        len(group_ids),
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
    )
    assignments = {}
    start = 0
    for split_name in ("train", "validation", "test"):
        end = start + counts[split_name]
        for match_group_id in group_ids[start:end]:
            assignments[match_group_id] = split_name
        start = end

    manifest = _manifest(
        grouped,
        assignments,
        mode="evaluation",
        random_state=random_state,
        fractions={
            "train": train_fraction,
            "validation": validation_fraction,
            "test": 1.0 - train_fraction - validation_fraction,
        },
        counts=counts,
        claim_scope="grouped train/validation/test evaluation",
    )
    validate_split_manifest(manifest)
    return manifest


def build_unsplit_manifest(rows: Iterable[dict]) -> dict:
    """Keep complete groups together without creating data splits."""

    grouped = _validate_and_group(rows)
    assignments = {match_group_id: "all" for match_group_id in grouped}
    manifest = _manifest(
        grouped,
        assignments,
        mode="unsplit",
        random_state=None,
        fractions=None,
        counts={"all": len(grouped)},
        claim_scope="all match groups retained without train/validation/test separation",
    )
    validate_split_manifest(manifest)
    return manifest


def build_matched_split_manifest(*args, **kwargs) -> dict:
    """Backward-compatible alias; new code should use match-group terminology."""

    return build_match_group_split_manifest(*args, **kwargs)


def apply_split_manifest(rows: Iterable[dict], manifest: dict) -> list[dict]:
    """Return row copies annotated with their match-group split."""

    validate_split_manifest(manifest)
    assignment = {
        entry["match_group_id"]: entry["split"]
        for entry in manifest["match_groups"]
    }
    annotated = []
    for row in rows:
        match_group_id = row.get("match_group_id")
        if match_group_id not in assignment:
            raise ValueError(
                f"match_group_id {match_group_id!r} is missing from the split manifest"
            )
        annotated.append({**row, "split": assignment[match_group_id]})
    return annotated


def validate_split_manifest(manifest: dict) -> None:
    """Fail closed on incomplete groups or trajectory leakage."""

    mode = manifest.get("mode")
    allowed_splits = (
        {"train", "validation", "test"}
        if mode == "evaluation"
        else {"all"}
        if mode == "unsplit"
        else set()
    )
    if not allowed_splits:
        raise ValueError(f"Unsupported split-manifest mode {mode!r}")

    groups = manifest.get("match_groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("Split manifest must contain at least one match group.")

    seen_groups: set[str] = set()
    trajectory_split: dict[str, str] = {}
    split_counts = {name: 0 for name in allowed_splits}
    for entry in groups:
        match_group_id = entry.get("match_group_id")
        split = entry.get("split")
        if not match_group_id or match_group_id in seen_groups:
            raise ValueError(
                f"Duplicate or missing match_group_id in split manifest: {match_group_id!r}"
            )
        if split not in allowed_splits:
            raise ValueError(f"Unsupported split {split!r} for match group {match_group_id!r}")
        cells = {
            (cell.get("thinking_mode"), cell.get("condition"), cell.get("hop_mode"))
            for cell in entry.get("cells") or []
        }
        thinking_modes = {thinking_mode for thinking_mode, _, _ in cells}
        expected_cells = {
            (thinking_mode, condition, hop_mode)
            for thinking_mode in thinking_modes
            for condition, hop_mode in EXPECTED_CELLS
        }
        if not thinking_modes or cells != expected_cells:
            raise ValueError(
                f"Match group {match_group_id!r} must contain clean/injected at both depths; "
                f"found {sorted(cells)}"
            )
        trajectory_ids = entry.get("trajectory_ids") or []
        expected_trajectories = 4 * len(thinking_modes)
        if (
            len(trajectory_ids) != expected_trajectories
            or len(set(trajectory_ids)) != expected_trajectories
        ):
            raise ValueError(
                f"Match group {match_group_id!r} must contain four trajectories per thinking mode"
            )
        for trajectory_id in trajectory_ids:
            previous = trajectory_split.get(trajectory_id)
            if previous is not None and previous != split:
                raise ValueError(
                    f"Trajectory {trajectory_id!r} leaks across {previous!r} and {split!r}"
                )
            trajectory_split[trajectory_id] = split
        seen_groups.add(match_group_id)
        split_counts[split] += 1

    if mode == "evaluation":
        missing = [name for name, count in split_counts.items() if count == 0]
        if missing:
            raise ValueError(f"Split manifest has no match groups in: {missing}")


def _validate_and_group(rows: Iterable[dict]) -> dict[str, dict]:
    rows = list(rows)
    if not rows:
        raise ValueError("At least one trajectory row is required to build splits.")

    groups: dict[str, dict] = {}
    trajectory_group: dict[str, str] = {}
    trajectory_cell: dict[str, tuple[str, str]] = {}
    for index, row in enumerate(rows):
        missing = sorted(REQUIRED_SPLIT_FIELDS - set(row))
        if missing:
            raise ValueError(f"Row {index} is missing split fields: {missing}")
        trajectory_id = str(row["trajectory_id"])
        match_group_id = str(row["match_group_id"])
        base_cell = (str(row["condition"]), str(row["hop_mode"]))
        if base_cell not in EXPECTED_CELLS:
            raise ValueError(f"Row {index} has unsupported match-group cell {base_cell!r}")
        cell = (str(row["thinking_mode"]), *base_cell)
        if not cell[0]:
            raise ValueError(f"Row {index} has unsupported match-group cell {cell!r}")

        previous_group = trajectory_group.setdefault(trajectory_id, match_group_id)
        if previous_group != match_group_id:
            raise ValueError(
                f"Trajectory {trajectory_id!r} belongs to multiple match groups: "
                f"{previous_group!r} and {match_group_id!r}"
            )
        previous_cell = trajectory_cell.setdefault(trajectory_id, cell)
        if previous_cell != cell:
            raise ValueError(f"Trajectory {trajectory_id!r} belongs to multiple cells")

        grouped = groups.setdefault(
            match_group_id,
            {"trajectory_ids": set(), "cell_trajectories": {}},
        )
        grouped["trajectory_ids"].add(trajectory_id)
        grouped["cell_trajectories"].setdefault(cell, set()).add(trajectory_id)

    for match_group_id, grouped in groups.items():
        cells = set(grouped["cell_trajectories"])
        thinking_modes = {thinking_mode for thinking_mode, _, _ in cells}
        expected_cells = {
            (thinking_mode, condition, hop_mode)
            for thinking_mode in thinking_modes
            for condition, hop_mode in EXPECTED_CELLS
        }
        if not thinking_modes or cells != expected_cells:
            raise ValueError(
                f"Match group {match_group_id!r} must contain clean/injected at both depths; "
                f"found {sorted(cells)}"
            )
        if any(len(ids) != 1 for ids in grouped["cell_trajectories"].values()):
            raise ValueError(
                f"Match group {match_group_id!r} must contain one trajectory per cell"
            )
        if len(grouped["trajectory_ids"]) != 4 * len(thinking_modes):
            raise ValueError(
                f"Match group {match_group_id!r} must contain four trajectories per thinking mode"
            )
    return groups


def _ordered_group_ids(grouped: dict[str, dict], *, random_state: int) -> list[str]:
    return sorted(
        grouped,
        key=lambda match_group_id: hashlib.sha256(
            f"{random_state}:{match_group_id}".encode("utf-8")
        ).hexdigest(),
    )


def _manifest(
    grouped: dict[str, dict],
    assignments: dict[str, str],
    *,
    mode: str,
    random_state: int | None,
    fractions: dict | None,
    counts: dict[str, int],
    claim_scope: str,
) -> dict:
    match_groups = []
    for match_group_id in sorted(grouped):
        group = grouped[match_group_id]
        cells = [
            {
                "thinking_mode": thinking_mode,
                "condition": condition,
                "hop_mode": hop_mode,
                "trajectory_id": next(
                    iter(group["cell_trajectories"][(thinking_mode, condition, hop_mode)])
                ),
            }
            for thinking_mode, condition, hop_mode in sorted(group["cell_trajectories"])
        ]
        match_groups.append({
            "match_group_id": match_group_id,
            "split": assignments[match_group_id],
            "cells": cells,
            "trajectory_ids": sorted(group["trajectory_ids"]),
        })
    return {
        "schema_version": "spec_gap.match_group_splits.v1",
        "mode": mode,
        "random_state": random_state,
        "fractions": fractions,
        "n_match_groups": len(grouped),
        "counts": counts,
        "claim_scope": claim_scope,
        "match_groups": match_groups,
    }


def _split_counts(
    n_match_groups: int,
    *,
    train_fraction: float,
    validation_fraction: float,
) -> dict[str, int]:
    test_fraction = 1.0 - train_fraction - validation_fraction
    fractions = (train_fraction, validation_fraction, test_fraction)
    if any(fraction <= 0.0 for fraction in fractions):
        raise ValueError("Train, validation, and test fractions must all be positive.")
    if n_match_groups < 3:
        raise ValueError(
            "At least three match groups are required for train/validation/test; "
            "use build_unsplit_manifest when train/validation/test splits are not appropriate."
        )

    train = max(1, round(n_match_groups * train_fraction))
    validation = max(1, round(n_match_groups * validation_fraction))
    test = n_match_groups - train - validation
    while test < 1 and train > 1:
        train -= 1
        test += 1
    while test < 1 and validation > 1:
        validation -= 1
        test += 1
    if test < 1:
        raise ValueError("Fractions cannot produce three non-empty splits.")
    return {"train": train, "validation": validation, "test": test}
