"""Tests for deterministic match-group split construction."""

import copy

import pytest

from src.analysis.splits import (
    apply_split_manifest,
    build_match_group_split_manifest,
    build_unsplit_manifest,
    validate_split_manifest,
)


def _group_rows(n_match_groups=5, thinking_modes=("off",)):
    rows = []
    for group_index in range(n_match_groups):
        match_group_id = f"group-{group_index}"
        for thinking_mode in thinking_modes:
            for hop_mode in ("2-hop", "3-hop"):
                for condition in ("clean", "injected"):
                    rows.append({
                        "trajectory_id": (
                            f"{match_group_id}-{thinking_mode}-{hop_mode}-{condition}"
                        ),
                        "match_group_id": match_group_id,
                        "thinking_mode": thinking_mode,
                        "hop_mode": hop_mode,
                        "condition": condition,
                    })
    return rows


def test_builds_reproducible_non_leaking_splits():
    rows = _group_rows()
    first = build_match_group_split_manifest(rows, random_state=7)
    second = build_match_group_split_manifest(reversed(rows), random_state=7)

    assert first == second
    assert first["counts"] == {"train": 3, "validation": 1, "test": 1}
    assert first["n_match_groups"] == 5

    annotated = apply_split_manifest(rows, first)
    split_by_group = {}
    for row in annotated:
        split_by_group.setdefault(row["match_group_id"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in split_by_group.values())


def test_keeps_both_thinking_modes_in_one_group_split():
    rows = _group_rows(thinking_modes=("off", "on"))
    manifest = build_match_group_split_manifest(rows)

    assert all(len(entry["trajectory_ids"]) == 8 for entry in manifest["match_groups"])
    annotated = apply_split_manifest(rows, manifest)
    for match_group_id in {row["match_group_id"] for row in rows}:
        splits = {
            row["split"]
            for row in annotated
            if row["match_group_id"] == match_group_id
        }
        assert len(splits) == 1


def test_rejects_incomplete_four_trajectory_group():
    rows = [
        row
        for row in _group_rows()
        if not (
            row["match_group_id"] == "group-0"
            and row["condition"] == "clean"
            and row["hop_mode"] == "3-hop"
        )
    ]
    with pytest.raises(ValueError, match="clean/injected at both depths"):
        build_match_group_split_manifest(rows)


def test_rejects_trajectory_leakage_in_manifest():
    manifest = build_match_group_split_manifest(_group_rows())
    corrupted = copy.deepcopy(manifest)
    first = corrupted["match_groups"][0]
    other = next(
        entry
        for entry in corrupted["match_groups"]
        if entry["split"] != first["split"]
    )
    other["trajectory_ids"].append(first["trajectory_ids"][0])

    with pytest.raises(ValueError, match="four trajectories per thinking mode"):
        validate_split_manifest(corrupted)


def test_two_group_data_uses_unsplit_manifest():
    rows = _group_rows(n_match_groups=2)
    with pytest.raises(ValueError, match="build_unsplit_manifest"):
        build_match_group_split_manifest(rows)

    manifest = build_unsplit_manifest(rows)
    assert manifest["mode"] == "unsplit"
    assert manifest["counts"] == {"all": 2}
    assert "without train/validation/test separation" in manifest["claim_scope"]
