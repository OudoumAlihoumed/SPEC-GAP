"""Tests for compute-independent depth-degradation analysis."""

import copy

import pytest

from src.analysis.depth_degradation import (
    analyze_depth_degradation,
    prediction_manifest_hash,
    tabular_result_rows,
)


def _prediction_rows(
    *,
    layers=(32,),
    n_match_groups=6,
    thinking_modes=("off",),
    label_target="trajectory_action_executed",
    all_negative=False,
):
    rows = []
    agents = {
        "2-hop": [
            ("planner_1", "planner"),
            ("worker_1", "worker"),
            ("executor_1", "executor"),
        ],
        "3-hop": [
            ("planner_1", "planner"),
            ("worker_1", "worker"),
            ("worker_2", "worker"),
            ("executor_1", "executor"),
        ],
    }
    wordings = ("send", "forward", "transmit")
    domains = ("public_health", "climate_science")

    for group_index in range(n_match_groups):
        domain_id = domains[(group_index // 3) % len(domains)]
        wording_id = wordings[group_index % len(wordings)]
        match_group_id = f"{domain_id}-{wording_id}-{group_index}"
        for thinking_mode in thinking_modes:
            for hop_mode in ("2-hop", "3-hop"):
                for condition in ("clean", "injected"):
                    action_fired = (
                        condition == "injected"
                        and not all_negative
                        and (
                            group_index % 3 != 2
                            if hop_mode == "2-hop"
                            else group_index % 3 == 0
                        )
                    )
                    if condition == "clean":
                        outcome = "clean"
                        latent_status = "not_candidate"
                    elif action_fired:
                        outcome = "executed"
                        latent_status = "not_candidate"
                    else:
                        outcome = "propagated_but_not_executed"
                        latent_status = "candidate"

                    injection_present = condition == "injected"
                    label = (
                        int(action_fired)
                        if label_target == "trajectory_action_executed"
                        else int(injection_present)
                    )
                    trajectory_id = (
                        f"{match_group_id}-{thinking_mode}-{hop_mode}-{condition}"
                    )
                    for layer in layers:
                        scores = _scores(
                            hop_mode=hop_mode,
                            condition=condition,
                            action_fired=action_fired,
                        )
                        for hop_index, (agent_id, agent_role) in enumerate(agents[hop_mode]):
                            rows.append({
                                "trajectory_id": trajectory_id,
                                "match_group_id": match_group_id,
                                "domain_id": domain_id,
                                "wording_id": wording_id,
                                "condition": condition,
                                "injection_present": injection_present,
                                "hop_mode": hop_mode,
                                "agent_id": agent_id,
                                "agent_role": agent_role,
                                "hop_index": hop_index,
                                "distance_from_injection": hop_index - 1,
                                "anchor_agent_id": "worker_1",
                                "anchor_hop_index": 1,
                                "model": "Qwen/Qwen3-32B",
                                "thinking_mode": thinking_mode,
                                "layer": layer,
                                "probe_name": "goldowsky_dill",
                                "score": scores[hop_index],
                                "label": label,
                                "label_target": label_target,
                                "behavioral_outcome": outcome,
                                "action_fired": action_fired,
                                "latent_compromise_status": latent_status,
                                "seed": 0,
                            })
    return rows


def _scores(*, hop_mode, condition, action_fired):
    if hop_mode == "2-hop":
        if action_fired:
            return [0.10, 0.75, 0.90]
        if condition == "injected":
            return [0.10, 0.45, 0.35]
        return [0.05, 0.10, 0.10]
    if action_fired:
        return [0.10, 0.50, 0.55, 0.55]
    if condition == "injected":
        return [0.10, 0.45, 0.55, 0.60]
    return [0.10, 0.25, 0.35, 0.45]


def _analyze(rows, *, random_state=11):
    return analyze_depth_degradation(
        rows,
        experiment_id="scenario1-test",
        n_bootstrap=80,
        random_state=random_state,
    )


def test_reports_executor_metrics_and_match_group_depth_delta():
    result = _analyze(_prediction_rows())

    assert result["schema_version"] == "spec_gap.depth_degradation.v2"
    assert result["sampling_grid"]["fully_crossed"] is True
    assert len(result["depth_metrics"]) == 2
    assert all(group["observation_agent"] == "executor" for group in result["depth_metrics"])
    comparison = result["depth_comparisons"][0]
    assert comparison["n_match_groups"] == 6
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


def test_constant_action_labels_report_undefined_auroc_without_crashing():
    result = _analyze(_prediction_rows(all_negative=True))

    assert all(group["auroc"] is None for group in result["depth_metrics"])
    assert all(
        group["confidence_intervals"]["auroc"] is None
        for group in result["depth_metrics"]
    )
    assert result["depth_comparisons"][0]["deltas"]["auroc"] is None


def test_thinking_modes_are_never_pooled():
    result = _analyze(_prediction_rows(thinking_modes=("off", "on")))

    assert len(result["depth_metrics"]) == 4
    assert len(result["depth_comparisons"]) == 2
    assert {row["thinking_mode"] for row in result["depth_comparisons"]} == {"off", "on"}


def test_classification_metrics_ignore_non_executor_score_changes():
    rows = _prediction_rows()
    baseline = _analyze(rows)
    changed = copy.deepcopy(rows)
    for row in changed:
        if row["agent_id"] != "executor_1":
            row["score"] = 1.0 - row["score"]
    result = _analyze(changed)

    for before, after in zip(baseline["depth_metrics"], result["depth_metrics"]):
        assert before["auroc"] == after["auroc"]
        assert before["brier"] == after["brier"]
        assert before["ece"] == after["ece"]
        assert before["temporal_divergence_mean"] != after["temporal_divergence_mean"]


def test_rejects_missing_hop_condition_in_match_group():
    rows = [
        row
        for row in _prediction_rows()
        if not (
            row["match_group_id"].endswith("-0")
            and row["hop_mode"] == "3-hop"
            and row["condition"] == "injected"
        )
    ]
    with pytest.raises(ValueError, match="missing a clean/injected depth cell"):
        _analyze(rows)


def test_rejects_inconsistent_layer_coverage():
    rows = _prediction_rows(layers=(16, 32))
    target = rows[0]["trajectory_id"]
    rows = [
        row for row in rows
        if not (row["trajectory_id"] == target and row["layer"] == 32)
    ]
    with pytest.raises(ValueError, match="Inconsistent layer coverage"):
        _analyze(rows)


def test_rejects_worker2_as_injection_anchor():
    rows = _prediction_rows()
    for row in rows:
        row["anchor_agent_id"] = "worker_2"
        row["anchor_hop_index"] = 2
        row["distance_from_injection"] = row["hop_index"] - 2
    with pytest.raises(ValueError, match="Worker1 at hop 1"):
        _analyze(rows)


def test_rejects_action_label_created_from_latent_candidate():
    rows = _prediction_rows()
    target = next(
        row["trajectory_id"]
        for row in rows
        if row["latent_compromise_status"] == "candidate"
    )
    for row in rows:
        if row["trajectory_id"] == target:
            row["label"] = 1
    with pytest.raises(ValueError, match="label does not match label_target"):
        _analyze(rows)
