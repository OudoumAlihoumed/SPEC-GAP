#!/usr/bin/env python3
"""Build a compact, hash-bound snapshot of the Policy full-matrix run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "spec_gap.policy_full_matrix_evidence.v1"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_sha256(value: object) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def _model_events(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        event
        for event in trajectory["trajectory_trace"]["full_events"]
        if event.get("model_called") is True
    ]


def _text_hash(value: str | None) -> str | None:
    return None if value is None else _sha256_bytes(value.encode("utf-8"))


def _compact_turn(
    event: dict[str, Any],
    *,
    controlled_endpoint: str,
) -> dict[str, Any]:
    output = event["output"]
    cost = event["cost_metadata"]
    activation = event["activation_metadata"]
    requests = output.get("tool_call_requests", [])
    actions = output.get("actions", [])
    generated_text = "\n".join(
        value
        for value in (
            output.get("thinking_content"),
            output.get("final_content"),
        )
        if value
    )
    return {
        "step_index": event["step_index"],
        "agent_id": event["agent_id"],
        "agent_role": event["agent_role"],
        "finish_reason": output["finish_reason"],
        "truncated": output["truncated"],
        "thinking_complete": output["thinking_complete"],
        "input_token_count": cost["token_usage"]["input_tokens"],
        "generated_token_count": len(output["generated_token_ids"]),
        "thinking_token_count": cost["token_usage"]["thinking_tokens"],
        "final_output_token_count": cost["token_usage"]["final_output_tokens"],
        "rendered_prompt_sha256": event["input"]["rendered_prompt_hash"],
        "thinking_content": output.get("thinking_content"),
        "thinking_content_sha256": _text_hash(output.get("thinking_content")),
        "final_content": output.get("final_content"),
        "final_content_sha256": _text_hash(output.get("final_content")),
        "raw_generated_text_sha256": _text_hash(output["raw_generated_text"]),
        "generated_token_ids_canonical_sha256": _canonical_sha256(
            output["generated_token_ids"]
        ),
        "tool_call_requests": requests,
        "tool_call_requests_canonical_sha256": _canonical_sha256(requests),
        "tool_call_parse_errors": output["tool_call_parse_errors"],
        "actions": actions,
        "actions_canonical_sha256": _canonical_sha256(actions),
        "controlled_endpoint_occurrences_in_generated_text": (
            generated_text.count(controlled_endpoint)
        ),
        "cost": {
            "modal_input_id": cost["modal_input_id"],
            "modal_task_id": cost["modal_task_id"],
            "elapsed_seconds": cost["elapsed_seconds"],
            "estimated_h200_cost_usd": cost["estimated_h200_cost_usd"],
        },
        "activation": {
            "storage_path": activation["storage_path"],
            "storage_status": activation["storage_status"],
            "checksum_sha256": activation["layer_metadata"]["checksum_sha256"],
            "layer_count": len(activation["layers_extracted"]),
            "layers_extracted": activation["layers_extracted"],
            "checkpoint_names": [
                checkpoint["name"]
                for checkpoint in activation["checkpoint_positions"]
            ],
            "checkpoint_shapes": activation["checkpoint_shapes"],
        },
    }


def _compact_trajectory(path: Path) -> dict[str, Any]:
    source_bytes = path.read_bytes()
    trajectory = json.loads(source_bytes)
    endpoint = trajectory["controlled_endpoint"]
    turns = [
        _compact_turn(event, controlled_endpoint=endpoint)
        for event in _model_events(trajectory)
    ]
    worker = next(
        event
        for event in _model_events(trajectory)
        if event["agent_id"] == "worker_1"
    )
    alignment = worker["token_alignment"]
    return {
        "trajectory_id": trajectory["trajectory_id"],
        "matched_pair_id": trajectory["matched_pair_id"],
        "delegation_depth": trajectory["delegation_depth"],
        "thinking_mode": worker["model_execution_metadata"]["thinking_mode"],
        "treatment": trajectory["treatment"],
        "outcome_class": trajectory["evaluation_labels"]["outcome_class"],
        "output_adoption": trajectory["evaluation_labels"][
            "behavioral_channel"
        ]["output_adoption"],
        "unsafe_action_executed": trajectory["evaluation_labels"][
            "action_channel"
        ]["unsafe_action_executed"],
        "controlled_endpoint": endpoint,
        "source_artifact": {
            "path": _portable_path(path),
            "sha256": _sha256_bytes(source_bytes),
            "tracked": False,
        },
        "injection_exposure": {
            "present_in_prompt": alignment["injection_present_in_prompt"],
            "token_span": alignment.get("injection_token_span"),
            "char_span": alignment.get("char_span"),
            "rendered_prompt_hash": alignment["rendered_prompt_hash"],
            "truncation_removed_injection_tokens": alignment[
                "truncation_removed_injection_tokens"
            ],
        },
        "turns": turns,
    }


def _activation_evidence(
    index_path: Path,
    summary_path: Path,
) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in index_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    artifacts: dict[str, dict[str, Any]] = {}
    for row in rows:
        path = row["remote_storage_path"]
        current = artifacts.setdefault(path, {
            "trajectory_id": row["trajectory_id"],
            "step_index": row["step_index"],
            "agent_id": row["agent_id"],
            "checksum_sha256": row["checksum_sha256"],
            "shape": row["shape"],
            "dtype": row["dtype"],
            "layer_count": len(row["layers"]),
            "checkpoints": [],
            "local_available": row["local_available"],
        })
        if current["checksum_sha256"] != row["checksum_sha256"]:
            raise ValueError(f"activation checksum changed across rows: {path}")
        current["checkpoints"].append(row["checkpoint"])
    for artifact in artifacts.values():
        artifact["checkpoints"].sort()
    return {
        "index_source": {
            "path": _portable_path(index_path),
            "sha256": _sha256_file(index_path),
            "tracked": False,
        },
        "summary_source": {
            "path": _portable_path(summary_path),
            "sha256": _sha256_file(summary_path),
            "tracked": False,
        },
        "summary": summary,
        "artifacts": dict(sorted(artifacts.items())),
    }


def _cost_evidence(
    log_path: Path,
    summary_path: Path,
) -> dict[str, Any]:
    with log_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    compact_rows = [
        {
            "trajectory_id": row["trajectory_id"],
            "treatment": row["treatment"],
            "condition_id": row["condition_id"],
            "thinking_mode": row["thinking_mode"],
            "outcome_class": row["outcome_class"],
            "step_index": int(row["step_index"]),
            "agent_id": row["agent_id"],
            "input_tokens": int(row["input_tokens"]),
            "generated_tokens": int(row["generated_tokens"]),
            "thinking_tokens": int(row["thinking_tokens"]),
            "final_output_tokens": int(row["final_output_tokens"]),
            "finish_reason": row["finish_reason"],
            "truncated": row["truncated"] == "True",
            "estimated_h200_cost_usd": float(row["estimated_h200_cost_usd"]),
            "tool_request_count": int(row["tool_request_count"]),
            "controlled_endpoint_tool_request_count": int(
                row["controlled_endpoint_tool_request_count"]
            ),
            "controlled_endpoint_in_generation": (
                row["controlled_endpoint_in_generation"] == "True"
            ),
        }
        for row in rows
    ]
    return {
        "log_source": {
            "path": _portable_path(log_path),
            "sha256": _sha256_file(log_path),
            "tracked": False,
        },
        "summary_source": {
            "path": _portable_path(summary_path),
            "sha256": _sha256_file(summary_path),
            "tracked": False,
        },
        "rows": compact_rows,
        "summary": json.loads(summary_path.read_text(encoding="utf-8")),
    }


def _aggregate(trajectories: list[dict[str, Any]]) -> dict[str, Any]:
    turns = [turn for trajectory in trajectories for turn in trajectory["turns"]]
    requests = [
        {
            "trajectory_id": trajectory["trajectory_id"],
            "treatment": trajectory["treatment"],
            "thinking_mode": trajectory["thinking_mode"],
            "agent_id": turn["agent_id"],
            "name": request["name"],
            "destination": request["arguments"].get("destination"),
        }
        for trajectory in trajectories
        for turn in trajectory["turns"]
        for request in turn["tool_call_requests"]
    ]
    spans = {
        f"{trajectory['delegation_depth']}__{trajectory['thinking_mode']}": (
            trajectory["injection_exposure"]["token_span"]
        )
        for trajectory in trajectories
        if trajectory["treatment"] == "injected"
    }
    return {
        "trajectory_count": len(trajectories),
        "model_turn_count": len(turns),
        "outcome_counts": dict(Counter(
            trajectory["outcome_class"] for trajectory in trajectories
        )),
        "finish_reason_counts": dict(Counter(
            turn["finish_reason"] for turn in turns
        )),
        "truncated_turn_count": sum(turn["truncated"] for turn in turns),
        "maximum_generated_tokens": max(
            turn["generated_token_count"] for turn in turns
        ),
        "controlled_endpoint_occurrences_in_generated_text": sum(
            turn["controlled_endpoint_occurrences_in_generated_text"]
            for turn in turns
        ),
        "unsafe_action_trajectory_count": sum(
            trajectory["unsafe_action_executed"] for trajectory in trajectories
        ),
        "tool_requests": requests,
        "injected_worker_token_spans": spans,
    }


def build_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    paths = sorted(args.trajectory_root.rglob(
        "policy__*__gen_controlled_v2_5000__thinking_*.json"
    ))
    trajectories = [_compact_trajectory(path) for path in paths]
    if len(trajectories) != 8:
        raise ValueError(f"expected 8 Policy trajectories, found {len(trajectories)}")
    review_source = None
    if args.review_artifact is not None:
        review_source = {
            "path": _portable_path(args.review_artifact),
            "sha256": _sha256_file(args.review_artifact),
            "tracked": False,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": "2026-08-09",
        "domain_id": "policy",
        "generation_protocol_id": "controlled_v2_5000",
        "source_policy": (
            "Raw trajectories, activation tensors/indexes, cost ledgers, and "
            "retrieval-review HTML remain untracked because they are large or "
            "contain retrieved paper text. This tracked snapshot copies the "
            "generated reasoning/visible outputs and machine-readable fields "
            "needed to audit the report, and binds each source artifact by SHA-256."
        ),
        "aggregate": _aggregate(trajectories),
        "trajectories": trajectories,
        "activation_evidence": _activation_evidence(
            args.activation_index,
            args.activation_summary,
        ),
        "cost_evidence": _cost_evidence(args.cost_log, args.cost_summary),
        "retrieval_review_source": review_source,
    }


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory-root", type=_path, required=True)
    parser.add_argument("--activation-index", type=_path, required=True)
    parser.add_argument("--activation-summary", type=_path, required=True)
    parser.add_argument("--cost-log", type=_path, required=True)
    parser.add_argument("--cost-summary", type=_path, required=True)
    parser.add_argument("--review-artifact", type=_path)
    parser.add_argument("--out", type=_path, required=True)
    args = parser.parse_args()

    snapshot = build_snapshot(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
