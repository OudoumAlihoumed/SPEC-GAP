"""Tests for deterministic matched-pair split construction."""

import copy

import pytest

from src.analysis.splits import (
    apply_split_manifest,
    build_matched_split_manifest,
    validate_split_manifest,
)


def _pair_rows(n_pairs=5):
    rows = []
    for pair_index in range(n_pairs):
        pair_id = f"pair-{pair_index}"
        for condition in ("clean", "injected"):
            rows.append({
                "trajectory_id": f"{pair_id}-{condition}",
                "pair_id": pair_id,
                "condition": condition,
            })
    return rows


def test_builds_reproducible_non_leaking_splits():
    rows = _pair_rows()
    first = build_matched_split_manifest(rows, random_state=7)
    second = build_matched_split_manifest(reversed(rows), random_state=7)

    assert first == second
    assert first["counts"] == {"train": 3, "validation": 1, "test": 1}

    annotated = apply_split_manifest(rows, first)
    split_by_pair = {}
    for row in annotated:
        split_by_pair.setdefault(row["pair_id"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in split_by_pair.values())


def test_rejects_incomplete_clean_injected_pair():
    rows = _pair_rows()
    rows = [
        row for row in rows
        if not (row["pair_id"] == "pair-0" and row["condition"] == "clean")
    ]
    with pytest.raises(ValueError, match="clean and injected"):
        build_matched_split_manifest(rows)


def test_rejects_trajectory_leakage_in_manifest():
    manifest = build_matched_split_manifest(_pair_rows())
    corrupted = copy.deepcopy(manifest)
    first = corrupted["pairs"][0]
    other = next(entry for entry in corrupted["pairs"] if entry["split"] != first["split"])
    other["trajectory_ids"].append(first["trajectory_ids"][0])

    with pytest.raises(ValueError, match="leaks across"):
        validate_split_manifest(corrupted)


def test_requires_enough_pairs_for_three_splits():
    with pytest.raises(ValueError, match="At least three"):
        build_matched_split_manifest(_pair_rows(n_pairs=2))
