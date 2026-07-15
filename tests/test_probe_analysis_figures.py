"""Tests for final Scenario 1 probe-analysis figures."""

import matplotlib.pyplot as plt

from src.analysis.probe_analysis_figures import (
    PROBE_ORDER,
    figure_catalog,
    save_probe_analysis_figures,
)


def _metric_row(mode, probe, layer, hop_mode):
    metrics = {
        "auroc": 0.75,
        "brier": 0.22,
        "ece": 0.18,
        "temporal_auroc": 0.80,
        "temporal_brier": 0.20,
        "temporal_ece": 0.15,
        "temporal_pre_anchor_mean": 0.25,
        "temporal_post_anchor_mean": 0.60,
        "temporal_divergence_mean": 0.35,
        "temporal_peak_shift_mean": 0.45,
        "temporal_persistence_mean": 0.75,
    }
    return {
        "model": "Qwen/Qwen3-32B",
        "thinking_mode": mode,
        "label_target": "injection_present",
        "probe_name": probe,
        "layer": layer,
        "seed": 0,
        "hop_mode": hop_mode,
        "n_match_groups": 2,
        "n_trajectories": 4,
        **metrics,
        "confidence_intervals": {
            metric: {
                "lower": max(0.0, value - 0.1),
                "upper": min(1.0, value + 0.1),
            }
            for metric, value in metrics.items()
        },
    }


def _comparison_row(mode, probe, layer):
    deltas = {
        "auroc": -0.10,
        "brier": 0.02,
        "ece": 0.01,
        "temporal_auroc": -0.05,
        "temporal_brier": 0.01,
        "temporal_ece": 0.02,
        "temporal_pre_anchor_mean": 0.0,
        "temporal_post_anchor_mean": -0.03,
        "temporal_divergence_mean": -0.03,
        "temporal_peak_shift_mean": -0.02,
        "temporal_persistence_mean": -0.05,
    }
    return {
        "model": "Qwen/Qwen3-32B",
        "thinking_mode": mode,
        "label_target": "injection_present",
        "probe_name": probe,
        "layer": layer,
        "seed": 0,
        "comparison": "3-hop_minus_2-hop",
        "n_match_groups": 2,
        "deltas": deltas,
        "confidence_intervals": {
            metric: {"lower": value - 0.1, "upper": value + 0.1}
            for metric, value in deltas.items()
        },
    }


def _result(layers):
    return {
        "claim_scope": "group-held-out exploratory analysis with only two groups",
        "label_targets": ["injection_present"],
        "n_match_groups": 2,
        "depth_metrics": [
            _metric_row(mode, probe, layer, hop_mode)
            for mode in ("off", "on")
            for probe in PROBE_ORDER
            for layer in layers
            for hop_mode in ("2-hop", "3-hop")
        ],
        "depth_comparisons": [
            _comparison_row(mode, probe, layer)
            for mode in ("off", "on")
            for probe in PROBE_ORDER
            for layer in layers
        ],
    }


def _score_rows():
    rows = []
    agents = {
        "2-hop": (("planner_1", "planner"), ("worker_1", "worker"), ("executor_1", "executor")),
        "3-hop": (
            ("planner_1", "planner"),
            ("worker_1", "worker"),
            ("worker_2", "worker"),
            ("executor_1", "executor"),
        ),
    }
    for mode in ("off", "on"):
        for probe in PROBE_ORDER:
            for group_index in range(2):
                for hop_mode, hop_agents in agents.items():
                    for condition in ("clean", "injected"):
                        trajectory_id = (
                            f"group-{group_index}-{mode}-{hop_mode}-{condition}"
                        )
                        for hop_index, (agent_id, role) in enumerate(hop_agents):
                            score = (
                                0.2 + hop_index * 0.05
                                if condition == "clean"
                                else 0.2 + hop_index * 0.2
                            )
                            rows.append({
                                "trajectory_id": trajectory_id,
                                "match_group_id": f"group-{group_index}",
                                "thinking_mode": mode,
                                "probe_name": probe,
                                "layer": 40,
                                "label_target": "injection_present",
                                "hop_mode": hop_mode,
                                "condition": condition,
                                "agent_id": agent_id,
                                "agent_role": role,
                                "hop_index": hop_index,
                                "score": min(score, 0.95),
                                "behavioral_outcome": (
                                    "clean" if condition == "clean" else "resisted"
                                ),
                            })
    return rows


def test_saves_primary_sensitivity_and_appendix_figures(tmp_path):
    paths = save_probe_analysis_figures(
        _result((32, 40, 48)),
        _result(range(64)),
        _score_rows(),
        tmp_path,
        dpi=72,
    )

    assert len(paths) == 18
    assert {path.suffix for path in paths} == {".png", ".svg", ".pdf"}
    assert {path.stem for path in paths} == {
        entry["stem"] for entry in figure_catalog()
    }
    assert all(path.is_file() and path.stat().st_size > 1000 for path in paths)
    assert plt.get_fignums() == []
