"""Depth-degradation analysis over precomputed trajectory probe scores.

This module is intentionally compute-backend agnostic. It consumes JSON-like
prediction rows after activation extraction and probe scoring have completed.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
from sklearn.metrics import brier_score_loss, roc_auc_score

from src.probes.linear_probe import compute_ece
from src.probes.temporal_divergence import temporal_divergence


REQUIRED_FIELDS = {
    "trajectory_id",
    "pair_id",
    "condition",
    "hop_mode",
    "agent_id",
    "hop_index",
    "anchor_hop_index",
    "model",
    "layer",
    "probe_name",
    "score",
    "label",
    "seed",
}
HOP_MODES = {"2-hop", "3-hop"}
CONDITIONS = {"clean", "injected"}
METRIC_NAMES = ("auroc", "brier", "ece", "temporal_divergence_mean")


def analyze_depth_degradation(
    rows: Iterable[dict],
    *,
    experiment_id: str,
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
    n_bins: int = 10,
    random_state: int = 42,
) -> dict:
    """Summarize metrics by depth and compute paired 3-hop minus 2-hop deltas."""

    rows = [dict(row) for row in rows]
    validate_prediction_rows(rows)
    if not experiment_id.strip():
        raise ValueError("experiment_id must be non-empty")
    if n_bootstrap < 1:
        raise ValueError("n_bootstrap must be at least 1")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")
    if n_bins < 1:
        raise ValueError("n_bins must be at least 1")

    group_fields = ("model", "probe_name", "layer", "seed", "hop_mode")
    grouped = _group_rows(rows, group_fields)
    rng = np.random.default_rng(random_state)
    group_results = []
    for key in sorted(grouped, key=_sortable_key):
        group_rows = grouped[key]
        metrics = _metric_snapshot(group_rows, n_bins=n_bins)
        intervals = _bootstrap_intervals(
            group_rows,
            cluster_field="trajectory_id",
            n_bootstrap=n_bootstrap,
            confidence=confidence,
            n_bins=n_bins,
            rng=rng,
        )
        values = dict(zip(group_fields, key))
        group_results.append({
            **values,
            "n_predictions": len(group_rows),
            "n_trajectories": len({row["trajectory_id"] for row in group_rows}),
            "n_positive": sum(int(row["label"]) for row in group_rows),
            "n_negative": sum(1 - int(row["label"]) for row in group_rows),
            **metrics,
            "confidence_intervals": intervals,
        })

    comparison_fields = ("model", "probe_name", "layer", "seed")
    by_configuration = _group_rows(rows, comparison_fields)
    comparisons = []
    for key in sorted(by_configuration, key=_sortable_key):
        config_rows = by_configuration[key]
        by_hop = _group_rows(config_rows, ("hop_mode",))
        missing_hops = HOP_MODES - {hop_key[0] for hop_key in by_hop}
        if missing_hops:
            values = dict(zip(comparison_fields, key))
            raise ValueError(
                f"Missing hop conditions {sorted(missing_hops)} for configuration {values}"
            )
        two_hop = by_hop[("2-hop",)]
        three_hop = by_hop[("3-hop",)]
        two_metrics = _metric_snapshot(two_hop, n_bins=n_bins)
        three_metrics = _metric_snapshot(three_hop, n_bins=n_bins)
        deltas = {
            metric: _difference(three_metrics[metric], two_metrics[metric])
            for metric in METRIC_NAMES
        }
        delta_intervals, n_matched_pairs = _bootstrap_delta_intervals(
            two_hop,
            three_hop,
            n_bootstrap=n_bootstrap,
            confidence=confidence,
            n_bins=n_bins,
            rng=rng,
        )
        comparisons.append({
            **dict(zip(comparison_fields, key)),
            "comparison": "3-hop_minus_2-hop",
            "n_matched_pairs": n_matched_pairs,
            "deltas": deltas,
            "confidence_intervals": delta_intervals,
            "interpretation": {
                "auroc": "negative indicates worse discrimination at 3-hop",
                "brier": "positive indicates worse probabilistic accuracy at 3-hop",
                "ece": "positive indicates worse calibration at 3-hop",
                "temporal_divergence_mean": (
                    "signed change; interpret relative to the declared probe direction"
                ),
            },
        })

    return {
        "schema_version": "spec_gap.depth_degradation.v1",
        "experiment_id": experiment_id,
        "data_manifest_hash": prediction_manifest_hash(rows),
        "analysis_config": {
            "n_bootstrap": n_bootstrap,
            "confidence": confidence,
            "n_bins": n_bins,
            "random_state": random_state,
            "delta_definition": "3-hop minus 2-hop",
            "bootstrap_unit": "trajectory for depth metrics; matched pair for depth deltas",
        },
        "depth_metrics": group_results,
        "depth_comparisons": comparisons,
    }


def validate_prediction_rows(rows: list[dict]) -> None:
    """Validate the analysis contract and fail closed on incomplete trajectories."""

    if not rows:
        raise ValueError("At least one prediction row is required.")

    seen_rows: set[tuple] = set()
    trajectory_identity: dict[str, tuple] = {}
    trajectory_anchor: dict[str, int] = {}
    trajectory_layers: dict[tuple, set[int]] = defaultdict(set)
    trajectory_hops: dict[tuple, set[int]] = defaultdict(set)
    for index, row in enumerate(rows):
        missing = sorted(REQUIRED_FIELDS - set(row))
        if missing:
            raise ValueError(f"Row {index} is missing prediction fields: {missing}")
        if row["hop_mode"] not in HOP_MODES:
            raise ValueError(f"Row {index} has unsupported hop_mode {row['hop_mode']!r}")
        if row["condition"] not in CONDITIONS:
            raise ValueError(f"Row {index} has unsupported condition {row['condition']!r}")
        if row["label"] not in (0, 1, False, True):
            raise ValueError(f"Row {index} label must be binary")
        score = float(row["score"])
        if not np.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError(f"Row {index} score must be a finite probability in [0, 1]")
        if not isinstance(row["hop_index"], int) or not isinstance(row["anchor_hop_index"], int):
            raise ValueError(f"Row {index} hop indices must be integers")
        if not isinstance(row["layer"], int):
            raise ValueError(f"Row {index} layer must be an integer")

        trajectory_id = str(row["trajectory_id"])
        identity = (
            str(row["pair_id"]),
            str(row["condition"]),
            str(row["hop_mode"]),
            str(row["model"]),
            int(row["seed"]),
        )
        previous_identity = trajectory_identity.setdefault(trajectory_id, identity)
        if previous_identity != identity:
            raise ValueError(f"Trajectory {trajectory_id!r} has inconsistent identity metadata")
        anchor = int(row["anchor_hop_index"])
        previous_anchor = trajectory_anchor.setdefault(trajectory_id, anchor)
        if previous_anchor != anchor:
            raise ValueError(f"Trajectory {trajectory_id!r} has inconsistent anchor metadata")

        row_key = (
            trajectory_id,
            row["model"],
            row["probe_name"],
            row["layer"],
            row["seed"],
            row["hop_index"],
        )
        if row_key in seen_rows:
            raise ValueError(f"Duplicate prediction row: {row_key}")
        seen_rows.add(row_key)

        coverage_key = (
            trajectory_id,
            str(row["model"]),
            str(row["probe_name"]),
            int(row["seed"]),
        )
        trajectory_layers[coverage_key].add(int(row["layer"]))
        hop_key = (*coverage_key, int(row["layer"]))
        if row["hop_index"] in trajectory_hops[hop_key]:
            raise ValueError(f"Duplicate hop_index in trajectory/layer group: {hop_key}")
        trajectory_hops[hop_key].add(int(row["hop_index"]))

    expected_layers: dict[tuple, set[int]] = {}
    for coverage_key, layers in trajectory_layers.items():
        _, model, probe_name, seed = coverage_key
        config_key = (model, probe_name, seed)
        expected = expected_layers.setdefault(config_key, set(layers))
        if expected != layers:
            raise ValueError(
                f"Inconsistent layer coverage for {config_key}: "
                f"expected {sorted(expected)}, found {sorted(layers)}"
            )

    for hop_key, hop_indices in trajectory_hops.items():
        ordered = sorted(hop_indices)
        if ordered != list(range(len(ordered))):
            raise ValueError(
                f"Hop indices must be contiguous from zero for {hop_key}; found {ordered}"
            )
        trajectory_id = hop_key[0]
        anchor = trajectory_anchor[trajectory_id]
        if anchor <= 0 or anchor >= len(ordered):
            raise ValueError(
                f"Trajectory {trajectory_id!r} anchor must leave pre- and post-anchor steps"
            )


def prediction_manifest_hash(rows: Iterable[dict]) -> str:
    """Hash normalized input rows so reported results identify their exact inputs."""

    normalized = sorted(
        (dict(row) for row in rows),
        key=lambda row: (
            str(row.get("trajectory_id")),
            str(row.get("model")),
            str(row.get("probe_name")),
            int(row.get("layer", -1)),
            int(row.get("seed", -1)),
            int(row.get("hop_index", -1)),
        ),
    )
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_prediction_jsonl(path: str | Path) -> list[dict]:
    """Load prediction rows from JSON Lines."""

    rows = []
    with Path(path).open() as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} of {path}") from exc
    validate_prediction_rows(rows)
    return rows


def tabular_result_rows(result: dict) -> list[dict]:
    """Flatten group metrics and depth deltas for CSV/DataFrame export."""

    rows = []
    for group in result["depth_metrics"]:
        row = {key: value for key, value in group.items() if key != "confidence_intervals"}
        row["record_type"] = "depth_metric"
        for metric, interval in group["confidence_intervals"].items():
            row[f"{metric}_ci_lower"] = interval["lower"] if interval else None
            row[f"{metric}_ci_upper"] = interval["upper"] if interval else None
        rows.append(row)
    for comparison in result["depth_comparisons"]:
        row = {
            key: value
            for key, value in comparison.items()
            if key not in {"deltas", "confidence_intervals", "interpretation"}
        }
        row["record_type"] = "depth_comparison"
        for metric, value in comparison["deltas"].items():
            row[f"{metric}_delta"] = value
            interval = comparison["confidence_intervals"][metric]
            row[f"{metric}_delta_ci_lower"] = interval["lower"] if interval else None
            row[f"{metric}_delta_ci_upper"] = interval["upper"] if interval else None
        rows.append(row)
    return rows


def _metric_snapshot(rows: list[dict], *, n_bins: int) -> dict:
    labels = np.asarray([int(row["label"]) for row in rows], dtype=int)
    scores = np.asarray([float(row["score"]) for row in rows], dtype=float)
    auroc = float(roc_auc_score(labels, scores)) if len(np.unique(labels)) == 2 else None
    temporal_values = list(_temporal_values_by_trajectory(rows).values())
    return {
        "auroc": auroc,
        "brier": float(brier_score_loss(labels, scores)),
        "ece": float(compute_ece(labels, scores, n_bins=n_bins)),
        "temporal_divergence_mean": float(np.mean(temporal_values)),
    }


def _temporal_values_by_trajectory(rows: list[dict]) -> dict[str, float]:
    grouped = _group_rows(rows, ("trajectory_id",))
    values = {}
    for (trajectory_id,), trajectory_rows in grouped.items():
        ordered = sorted(trajectory_rows, key=lambda row: row["hop_index"])
        anchor = int(ordered[0]["anchor_hop_index"])
        anchor_position = [row["hop_index"] for row in ordered].index(anchor)
        result = temporal_divergence(
            [float(row["score"]) for row in ordered],
            anchor_position=anchor_position,
        )
        values[str(trajectory_id)] = result.divergence_score
    return values


def _bootstrap_intervals(
    rows: list[dict],
    *,
    cluster_field: str,
    n_bootstrap: int,
    confidence: float,
    n_bins: int,
    rng: np.random.Generator,
) -> dict:
    cluster_ids = sorted({str(row[cluster_field]) for row in rows})
    samples = {metric: [] for metric in METRIC_NAMES}
    for _ in range(n_bootstrap):
        selected = rng.choice(cluster_ids, size=len(cluster_ids), replace=True).tolist()
        snapshot = _resampled_snapshot(
            rows,
            selected,
            cluster_field=cluster_field,
            n_bins=n_bins,
        )
        for metric in METRIC_NAMES:
            if snapshot[metric] is not None:
                samples[metric].append(snapshot[metric])
    return {
        metric: _confidence_interval(values, confidence)
        for metric, values in samples.items()
    }


def _bootstrap_delta_intervals(
    two_hop: list[dict],
    three_hop: list[dict],
    *,
    n_bootstrap: int,
    confidence: float,
    n_bins: int,
    rng: np.random.Generator,
) -> tuple[dict, int]:
    two_pairs = {str(row["pair_id"]) for row in two_hop}
    three_pairs = {str(row["pair_id"]) for row in three_hop}
    matched_pairs = sorted(two_pairs & three_pairs)
    if not matched_pairs:
        raise ValueError("Depth comparison requires at least one pair present at both depths")
    if two_pairs != three_pairs:
        raise ValueError(
            "Depth comparison requires identical matched pair coverage at 2-hop and 3-hop"
        )

    samples = {metric: [] for metric in METRIC_NAMES}
    for _ in range(n_bootstrap):
        selected = rng.choice(matched_pairs, size=len(matched_pairs), replace=True).tolist()
        two_snapshot = _resampled_snapshot(
            two_hop,
            selected,
            cluster_field="pair_id",
            n_bins=n_bins,
        )
        three_snapshot = _resampled_snapshot(
            three_hop,
            selected,
            cluster_field="pair_id",
            n_bins=n_bins,
        )
        for metric in METRIC_NAMES:
            delta = _difference(three_snapshot[metric], two_snapshot[metric])
            if delta is not None:
                samples[metric].append(delta)
    return (
        {
            metric: _confidence_interval(values, confidence)
            for metric, values in samples.items()
        },
        len(matched_pairs),
    )


def _resampled_snapshot(
    rows: list[dict],
    selected_clusters: list[str],
    *,
    cluster_field: str,
    n_bins: int,
) -> dict:
    rows_by_cluster: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        rows_by_cluster[str(row[cluster_field])].append(row)
    sampled_rows = [
        row
        for cluster_id in selected_clusters
        for row in rows_by_cluster[cluster_id]
    ]
    labels = np.asarray([int(row["label"]) for row in sampled_rows], dtype=int)
    scores = np.asarray([float(row["score"]) for row in sampled_rows], dtype=float)

    temporal_by_trajectory = _temporal_values_by_trajectory(rows)
    temporal_by_cluster: dict[str, list[float]] = defaultdict(list)
    trajectory_cluster = {
        str(row["trajectory_id"]): str(row[cluster_field])
        for row in rows
    }
    for trajectory_id, value in temporal_by_trajectory.items():
        temporal_by_cluster[trajectory_cluster[trajectory_id]].append(value)
    sampled_temporal = [
        value
        for cluster_id in selected_clusters
        for value in temporal_by_cluster[cluster_id]
    ]
    return {
        "auroc": (
            float(roc_auc_score(labels, scores))
            if len(np.unique(labels)) == 2
            else None
        ),
        "brier": float(brier_score_loss(labels, scores)),
        "ece": float(compute_ece(labels, scores, n_bins=n_bins)),
        "temporal_divergence_mean": float(np.mean(sampled_temporal)),
    }


def _confidence_interval(values: list[float], confidence: float) -> dict | None:
    if not values:
        return None
    alpha = (1.0 - confidence) / 2.0
    return {
        "lower": float(np.quantile(values, alpha)),
        "upper": float(np.quantile(values, 1.0 - alpha)),
    }


def _difference(three_hop: float | None, two_hop: float | None) -> float | None:
    if three_hop is None or two_hop is None:
        return None
    return float(three_hop - two_hop)


def _group_rows(rows: list[dict], fields: tuple[str, ...]) -> dict[tuple, list[dict]]:
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row[field] for field in fields)].append(row)
    return dict(grouped)


def _sortable_key(key: tuple) -> tuple[str, ...]:
    return tuple(str(value) for value in key)
