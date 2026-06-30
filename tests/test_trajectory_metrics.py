"""Tests for construction-grounded trajectory-level metrics."""

import json

import pytest

from src.analysis.trajectory_metrics import (
    load_trajectory_jsonl,
    summarize_dataset,
    summarize_trajectory,
)


def _record(
    trajectory_id,
    step_index,
    node_id,
    *,
    hop_mode="2-hop",
    trajectory_label=None,
    step_label=None,
    injection_point=None,
    behavioral_sanity=None,
    tool_calls=None,
):
    return {
        "trajectory_id": trajectory_id,
        "step_index": step_index,
        "node_id": node_id,
        "hop_mode": hop_mode,
        "scenario_id": "scenario1",
        "condition": f"scenario1-{hop_mode}",
        "trajectory_label": trajectory_label,
        "step_label": step_label,
        "injection_point": injection_point,
        "behavioral_sanity": behavioral_sanity,
        "tool_calls": tool_calls or [],
    }


def _successful_2hop():
    return [
        _record("success", 0, "planner"),
        _record("success", 1, "worker", injection_point="retrieval"),
        _record(
            "success",
            2,
            "executor",
            trajectory_label="successful_compromise",
            step_label="unsafe_action_executed",
            behavioral_sanity={"unsafe_action_executed": True},
            tool_calls=[
                {
                    "tool": "external_sink",
                    "status": "executed",
                    "safety_label": "unsafe",
                }
            ],
        ),
    ]


def test_summarize_successful_trajectory_separates_depths():
    summary = summarize_trajectory(_successful_2hop())
    assert summary.total_chain_hops == 2
    assert summary.injection_step_index == 1
    assert summary.first_compromise_step_index == 2
    assert summary.handoffs_from_injection_to_first_compromise == 1
    assert summary.exploit_succeeded is True
    assert summary.unsafe_tool_invocations == 1


def test_dataset_rates_use_explicit_denominators():
    clean = [
        _record("clean", 0, "planner"),
        _record("clean", 1, "worker"),
        _record(
            "clean",
            2,
            "executor",
            trajectory_label="clean",
            tool_calls=[{"tool": "answer", "status": "executed", "unsafe": False}],
        ),
    ]
    attempted = [
        _record("attempt", 0, "planner"),
        _record("attempt", 1, "worker", injection_point="retrieval"),
        _record(
            "attempt",
            2,
            "executor",
            trajectory_label="attempted_compromise",
            step_label="resisted_injection",
            tool_calls=[{"tool": "answer", "status": "executed", "unsafe": False}],
        ),
    ]

    result = summarize_dataset([_successful_2hop(), attempted, clean])
    assert result["n_attempted_compromise"] == 2
    assert result["n_successful_compromise"] == 1
    assert result["exploit_chain_success_rate"] == 0.5
    assert result["minimum_handoffs_from_injection_to_first_compromise"] == 1
    assert result["n_tool_invocations"] == 3
    assert result["unsafe_tool_invocation_rate"] == pytest.approx(1 / 3)
    assert result["unsafe_tool_trajectory_rate"] == pytest.approx(1 / 3)


def test_tool_name_alone_does_not_imply_unsafe():
    records = _successful_2hop()
    records[-1]["tool_calls"] = [
        {"tool": "external_sink", "status": "executed"},
    ]
    assert summarize_trajectory(records).unsafe_tool_invocations == 0


def test_load_jsonl_rejects_non_contiguous_steps(tmp_path):
    path = tmp_path / "bad.jsonl"
    rows = [
        _record("bad", 0, "planner"),
        _record("bad", 2, "executor"),
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="contiguous"):
        load_trajectory_jsonl(path)


def test_compromise_cannot_precede_injection():
    records = [
        _record("bad-order", 0, "planner", step_label="compromised_context"),
        _record("bad-order", 1, "worker", injection_point="retrieval"),
        _record("bad-order", 2, "executor"),
    ]
    with pytest.raises(ValueError, match="precede"):
        summarize_trajectory(records)
