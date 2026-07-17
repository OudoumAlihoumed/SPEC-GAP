"""Tests for the compact public Scenario 1 reporting snapshot."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.analysis.reporting_snapshot import (
    REPORTING_SNAPSHOT_SCHEMA,
    build_reporting_snapshot,
    load_reporting_snapshot,
    write_reporting_snapshot,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRACKED_SNAPSHOT = PROJECT_ROOT / "docs/data/scenario1/reporting_snapshot.json"
TRACKED_MANIFEST = (
    PROJECT_ROOT / "results/scenario1/final_analysis/analysis_manifest.json"
)
TRACKED_TEMPORAL_RECORDS = (
    PROJECT_ROOT
    / "results/scenario1/depth_analysis/temporal_divergence_scores.jsonl"
)
TRACKED_PUBLIC_TABLES = (
    PROJECT_ROOT / "results/scenario1/depth_analysis/depth_degradation.csv",
    PROJECT_ROOT / "results/scenario1/final_analysis/reference_layer_depth_deltas.csv",
    PROJECT_ROOT / "results/scenario1/final_analysis/reference_layer_metrics.csv",
)


def _depth_metric(layer, *, mode="off", probe="goldowsky_dill_logistic", hop="2-hop"):
    return {
        "thinking_mode": mode,
        "probe_name": probe,
        "hop_mode": hop,
        "layer": layer,
        "auroc": 0.75,
        "path_mean_auroc": 0.75,
    }


def _result(layers):
    return {
        "claim_scope": "two-group construction diagnostic",
        "data_manifest_hash": "a" * 64,
        "experiment_id": "scenario1-test",
        "label_targets": ["injection_present"],
        "n_match_groups": 2,
        "depth_metrics": [
            _depth_metric(layer, mode=mode, probe=probe, hop=hop)
            for layer in layers
            for mode in ("off", "on")
            for probe in ("goldowsky_dill_logistic", "lat_contrast_pair_pca")
            for hop in ("2-hop", "3-hop")
        ],
        "depth_comparisons": [],
    }


def _score_rows():
    rows = []
    agents = {
        "2-hop": ("planner_1", "worker_1", "executor_1"),
        "3-hop": ("planner_1", "worker_1", "worker_2", "executor_1"),
    }
    for mode in ("off", "on"):
        for probe in ("goldowsky_dill_logistic", "lat_contrast_pair_pca"):
            for hop_mode, hop_agents in agents.items():
                for treatment in ("clean", "injected"):
                    trajectory_id = f"group-a-{mode}-{hop_mode}-{treatment}"
                    for hop_index, agent_id in enumerate(hop_agents):
                        rows.append({
                            "trajectory_id": trajectory_id,
                            "match_group_id": "group-a",
                            "hop_index": hop_index,
                            "hop_mode": hop_mode,
                            "agent_id": agent_id,
                            "thinking_mode": mode,
                            "probe_name": probe,
                            "layer": 40,
                            "label_target": "injection_present",
                            "behavioral_outcome": (
                                "clean" if treatment == "clean" else "resisted"
                            ),
                        })
    return rows


def _configs():
    decoding = {
        "do_sample": True,
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 20,
        "min_p": 0.0,
        "max_new_tokens": 2048,
        "seed": 0,
    }
    return [
        {
            "model_name": "Qwen/Qwen3-32B",
            "model_revision": "revision",
            "tokenizer_name": "Qwen/Qwen3-32B",
            "tokenizer_revision": "revision",
            "thinking_mode": mode,
            "decoding_settings": decoding,
        }
        for mode in ("off", "on")
    ]


def test_snapshot_compacts_all_layers_and_round_trips(tmp_path):
    snapshot = build_reporting_snapshot(
        _result((32, 40, 48)),
        _result(range(64)),
        _score_rows(),
        analysis_revision="analysis123",
        reporting_revision="reporting123",
        source_artifacts={"scores": {"path": "scores.jsonl", "sha256": "a" * 64}},
        model_configs=_configs(),
    )
    destination = tmp_path / "snapshot.json"
    write_reporting_snapshot(snapshot, destination)

    loaded = load_reporting_snapshot(destination)

    assert loaded["schema_version"] == REPORTING_SNAPSHOT_SCHEMA
    assert {row["layer"] for row in loaded["per_step_rows"]} == {40}
    assert set(loaded["all_layer_result"]["depth_metrics"][0]) == {
        "thinking_mode",
        "probe_name",
        "hop_mode",
        "layer",
        "auroc",
        "path_mean_auroc",
    }
    assert loaded["sample"]["behavioral_outcomes"] == {"clean": 4, "resisted": 4}


def test_snapshot_rejects_mode_specific_decoding_changes():
    configs = _configs()
    configs[1] = json.loads(json.dumps(configs[1]))
    configs[1]["decoding_settings"]["temperature"] = 0.7

    with pytest.raises(ValueError, match="same decoding settings"):
        build_reporting_snapshot(
            _result((32, 40, 48)),
            _result(range(64)),
            _score_rows(),
            analysis_revision="analysis123",
            reporting_revision="reporting123",
            source_artifacts={
                "scores": {"path": "scores.jsonl", "sha256": "a" * 64}
            },
            model_configs=configs,
        )


def test_repository_includes_a_valid_public_reporting_snapshot():
    snapshot = load_reporting_snapshot(TRACKED_SNAPSHOT)

    assert snapshot["sample"] == {
        "agent_turns": 56,
        "behavioral_outcomes": {"clean": 8, "resisted": 8},
        "match_groups": 2,
        "trajectory_runs": 16,
        "unsafe_action_executed_count": 0,
    }
    assert snapshot["analysis_revision"]
    assert snapshot["reporting_revision"]


def test_repository_includes_manifest_tables_figures_and_temporal_records():
    manifest = json.loads(TRACKED_MANIFEST.read_text(encoding="utf-8"))

    published_paths = [
        PROJECT_ROOT / path
        for path in manifest["tables"]
    ]
    published_paths.extend(
        PROJECT_ROOT / path
        for figure in manifest["figures"]
        for path in figure["files"]
    )
    assert published_paths
    assert all(path.is_file() and path.stat().st_size > 0 for path in published_paths)

    temporal_rows = [
        json.loads(line)
        for line in TRACKED_TEMPORAL_RECORDS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert temporal_rows
    assert {row["schema_version"] for row in temporal_rows} == {
        "spec_gap.temporal_divergence_score.v2"
    }
    assert {row["label_target"] for row in temporal_rows} == {
        "injection_present"
    }
    assert {int(row["layer"]) for row in temporal_rows} == {32, 40, 48}


def test_public_result_tables_use_portable_line_endings():
    assert all(b"\r" not in path.read_bytes() for path in TRACKED_PUBLIC_TABLES)
