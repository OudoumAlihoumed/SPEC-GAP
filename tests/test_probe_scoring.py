"""Tests for group-safe Scenario 1 per-step probe scores."""

import json

import numpy as np
import pytest

import src.analysis.probe_scoring as scoring
from src.analysis.probe_scoring import (
    MatchGroupDesign,
    generate_per_step_probe_scores,
    load_match_group_designs,
    summarize_per_step_probe_scores,
)
from src.extraction.saved_activations import ProbeActivationBatch


def _index_rows(*, agent_id="worker_1", agent_role="worker"):
    rows = []
    for group_index, group_id in enumerate(("group-a", "group-b")):
        for depth in ("2-hop", "3-hop"):
            for treatment in ("clean", "injected"):
                injected = treatment == "injected"
                rows.append({
                    "trajectory_id": (
                        f"{group_id}__{depth.replace('-', '')}__{treatment}__thinking_off"
                    ),
                    "match_group_id": group_id,
                    "matched_pair_id": f"{group_id}__{depth}",
                    "domain_id": f"domain-{group_index}",
                    "delegation_depth": depth,
                    "treatment": treatment,
                    "thinking_mode": "off",
                    "agent_id": agent_id,
                    "agent_role": agent_role,
                    "hop_index": 1,
                    "step_index": 2,
                    "checkpoint": "last_input_token",
                    "checkpoint_forward_scope": "prompt_only",
                    "model_name": "Qwen/Qwen3-32B",
                    "model_revision": "revision",
                    "outcome_class": "resisted" if injected else "clean",
                    "labels": {
                        "injection_present": int(injected),
                        "unsafe_action_executed": 0,
                        "output_adoption": 0,
                    },
                })
    return rows


def _fake_batch(rows, *, identical_centroids=False):
    labels = np.asarray([row["labels"]["injection_present"] for row in rows])
    values = []
    for index, label in enumerate(labels):
        if identical_centroids:
            values.append([float(index // 4), 1.0])
        else:
            values.append([float(label) * 4.0 + index * 0.01, float(index % 3)])
    matrix = np.asarray(values, dtype=np.float32)
    return ProbeActivationBatch(
        activations={32: matrix, 40: matrix + 0.25},
        labels=labels,
        metadata=[dict(row) for row in rows],
    )


def _designs():
    return {
        "group-a": MatchGroupDesign(wording_id="A", seed=0),
        "group-b": MatchGroupDesign(wording_id="B", seed=0),
    }


def test_generates_two_group_held_out_probe_scores(monkeypatch):
    rows = _index_rows()
    batch = _fake_batch(rows)
    monkeypatch.setattr(scoring, "load_probe_activation_batch", lambda *args, **kwargs: batch)

    scores = generate_per_step_probe_scores(
        rows,
        match_group_designs=_designs(),
        verify_checksums=False,
    )

    assert len(scores) == 8 * 2 * 2
    assert {row["probe_name"] for row in scores} == set(scoring.PROBE_NAMES)
    assert {row["layer"] for row in scores} == {32, 40}
    assert all(row["match_group_id"] == row["held_out_match_group_id"] for row in scores)
    assert all(0.0 <= row["score"] <= 1.0 for row in scores)
    assert all(row["label_target"] == "injection_present" for row in scores)
    assert all(row["claim_scope"] == "construction_label_diagnostic" for row in scores)

    summary = summarize_per_step_probe_scores(scores)
    assert summary["score_rows"] == len(scores)
    assert summary["prespecified_reference_layer"] == 40
    assert summary["prespecified_ablation_layers"] == [32, 48]


def test_lat_uses_explicit_constant_prior_for_identical_centroids(monkeypatch):
    rows = _index_rows(agent_id="planner_1", agent_role="planner")
    # Make every activation identical so neither class has a representation
    # difference. The LAT output must be an explicit neutral prior.
    labels = np.asarray([row["labels"]["injection_present"] for row in rows])
    batch = ProbeActivationBatch(
        activations={40: np.ones((len(rows), 3), dtype=np.float32)},
        labels=labels,
        metadata=[dict(row) for row in rows],
    )
    monkeypatch.setattr(scoring, "load_probe_activation_batch", lambda *args, **kwargs: batch)

    scores = generate_per_step_probe_scores(
        rows,
        match_group_designs=_designs(),
        verify_checksums=False,
    )
    lat_rows = [
        row for row in scores if row["probe_name"] == "lat_contrast_pair_pca"
    ]

    assert {row["fit_status"] for row in lat_rows} == {
        "constant_prior_identical_contrast_pairs"
    }
    assert {row["score"] for row in lat_rows} == {0.5}


def test_requires_explicit_behavioral_action_label(monkeypatch):
    rows = _index_rows()
    for row in rows:
        row["labels"].pop("unsafe_action_executed")
    batch = _fake_batch(rows)
    monkeypatch.setattr(scoring, "load_probe_activation_batch", lambda *args, **kwargs: batch)

    with pytest.raises(ValueError, match="no binary unsafe_action_executed"):
        generate_per_step_probe_scores(
            rows,
            match_group_designs=_designs(),
            verify_checksums=False,
        )


def test_manifest_loader_requires_one_design_per_group(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "trajectories": [
            {"group_id": "group-a", "wording": "A", "seed": 0},
            {"group_id": "group-a", "wording": "B", "seed": 0},
        ]
    }))

    with pytest.raises(ValueError, match="mixes wording or seed"):
        load_match_group_designs(manifest)


def test_generated_checkpoint_is_rejected():
    rows = _index_rows()
    for row in rows:
        row["checkpoint"] = "last_visible_answer_token"

    with pytest.raises(ValueError, match="Only last_input_token"):
        generate_per_step_probe_scores(
            rows,
            match_group_designs=_designs(),
            checkpoint="last_visible_answer_token",
            verify_checksums=False,
        )
