"""Tests for compute-independent depth-degradation analysis."""

import copy

import pytest

from src.analysis.depth_degradation import (
    analyze_depth_degradation,
    prediction_manifest_hash,
    tabular_result_rows,
)


def _prediction_rows(*, layers=(20,), n_pairs=4):
    rows = []
    scores = {
        "2-hop": {
            "clean": [0.05, 0.08, 0.10],
            "injected": [0.05, 0.85, 0.90],
        },
        "3-hop": {
            "clean": [0.10, 0.40, 0.45, 0.50],
            "injected": [0.10, 0.60, 0.55, 0.50],
        },
    }
    labels = {
        "2-hop": {
            "clean": [0, 0, 0],
            "injected": [0, 1, 1],
        },
        "3-hop": {
            "clean": [0, 0, 0, 0],
            "injected": [0, 1, 1, 1],
        },
    }
    agents = {
        "2-hop": ["planner", "worker", "executor"],
        "3-hop": ["planner", "worker", "worker2", "executor"],
    }

    for pair_index in range(n_pairs):
        pair_id = f"task-variant-{pair_index}"
        for hop_mode in ("2-hop", "3-hop"):
            for condition in ("clean", "injected"):
                trajectory_id = f"{pair_id}-{hop_mode}-{condition}"
                for layer in layers:
                    for hop_index, agent_id in enumerate(agents[hop_mode]):
                        rows.append({
                            "trajectory_id": trajectory_id,
                            "pair_id": pair_id,
                            "condition": condition,
                            "hop_mode": hop_mode,
                            "agent_id": agent_id,
                            "hop_index": hop_index,
                            "anchor_hop_index": 1,
                            "model": "meta-llama/Llama-3.1-8B-Instruct",
                            "layer": layer,
                            "probe_name": "goldowsky_dill",
                            "score": scores[hop_mode][condition][hop_index],
                            "label": labels[hop_mode][condition][hop_index],
                            "seed": 0,
                        })
    return rows


def _analyze(rows, *, random_state=11):
    return analyze_depth_degradation(
        rows,
        experiment_id="scenario1-test",
        n_bootstrap=80,
        random_state=random_state,
    )


def test_reports_depth_metrics_and_degradation_delta():
    result = _analyze(_prediction_rows())

    assert result["schema_version"] == "spec_gap.depth_degradation.v1"
    assert len(result["depth_metrics"]) == 2
    comparison = result["depth_comparisons"][0]
    assert comparison["n_matched_pairs"] == 4
    assert comparison["deltas"]["auroc"] < 0
    assert comparison["deltas"]["brier"] > 0
    assert comparison["confidence_intervals"]["brier"] is not None

    table = tabular_result_rows(result)
    assert {row["record_type"] for row in table} == {
        "depth_metric",
        "depth_comparison",
    }


def test_bootstrap_and_manifest_hash_are_reproducible():
    rows = _prediction_rows()
    first = _analyze(rows, random_state=123)
    second = _analyze(list(reversed(rows)), random_state=123)

    assert first == second
    assert prediction_manifest_hash(rows) == prediction_manifest_hash(reversed(rows))


def test_constant_labels_report_undefined_auroc_without_crashing():
    rows = _prediction_rows()
    for row in rows:
        row["label"] = 0
    result = _analyze(rows)

    assert all(group["auroc"] is None for group in result["depth_metrics"])
    assert all(
        group["confidence_intervals"]["auroc"] is None
        for group in result["depth_metrics"]
    )
    assert result["depth_comparisons"][0]["deltas"]["auroc"] is None


def test_rejects_missing_hop_condition():
    rows = [row for row in _prediction_rows() if row["hop_mode"] == "2-hop"]
    with pytest.raises(ValueError, match="Missing hop conditions"):
        _analyze(rows)


def test_rejects_inconsistent_layer_coverage():
    rows = _prediction_rows(layers=(16, 20))
    target = rows[0]["trajectory_id"]
    rows = [
        row for row in rows
        if not (row["trajectory_id"] == target and row["layer"] == 20)
    ]
    with pytest.raises(ValueError, match="Inconsistent layer coverage"):
        _analyze(rows)


def test_rejects_pair_mismatch_between_depths():
    rows = copy.deepcopy(_prediction_rows())
    for row in rows:
        if row["pair_id"] == "task-variant-0" and row["hop_mode"] == "3-hop":
            row["pair_id"] = "different-pair"
            row["trajectory_id"] = row["trajectory_id"].replace(
                "task-variant-0", "different-pair"
            )
    with pytest.raises(ValueError, match="identical matched pair coverage"):
        _analyze(rows)
