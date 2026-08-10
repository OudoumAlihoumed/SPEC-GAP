#!/usr/bin/env python3
"""Build a compact, hash-bound snapshot of the Telecom full-matrix run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.activation_controls import (  # noqa: E402
    run_activation_control_audit,
)


SCHEMA_VERSION = "spec_gap.telecom_full_matrix_evidence.v1"


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


def _source(path: Path, *, tracked: bool) -> dict[str, Any]:
    return {
        "path": _portable_path(path),
        "sha256": _sha256_file(path),
        "tracked": tracked,
    }


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
    carrier_marker: str,
    injection_payload: str,
) -> dict[str, Any]:
    output = event["output"]
    cost = event["cost_metadata"]
    activation = event["activation_metadata"]
    raw_generated_text = output["raw_generated_text"]
    requests = output.get("tool_call_requests", [])
    actions = output.get("actions", [])
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
        "raw_generated_text": raw_generated_text,
        "raw_generated_text_sha256": _text_hash(raw_generated_text),
        "generated_token_ids_canonical_sha256": _canonical_sha256(
            output["generated_token_ids"]
        ),
        "controlled_endpoint_occurrences": raw_generated_text.count(
            controlled_endpoint
        ),
        "carrier_marker_occurrences": raw_generated_text.count(carrier_marker),
        "exact_injection_payload_occurrences": raw_generated_text.count(
            injection_payload
        ),
        "tool_call_requests": requests,
        "tool_call_requests_canonical_sha256": _canonical_sha256(requests),
        "tool_call_parse_errors": output["tool_call_parse_errors"],
        "actions": actions,
        "actions_canonical_sha256": _canonical_sha256(actions),
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
                checkpoint["name"] for checkpoint in activation["checkpoint_positions"]
            ],
            "checkpoint_shapes": activation["checkpoint_shapes"],
        },
    }


def _compact_trajectory(
    path: Path,
    *,
    carrier_marker: str,
    injection_payload: str,
) -> dict[str, Any]:
    source_bytes = path.read_bytes()
    trajectory = json.loads(source_bytes)
    endpoint = trajectory["controlled_endpoint"]
    events = _model_events(trajectory)
    turns = [
        _compact_turn(
            event,
            controlled_endpoint=endpoint,
            carrier_marker=carrier_marker,
            injection_payload=injection_payload,
        )
        for event in events
    ]
    worker = next(event for event in events if event["agent_id"] == "worker_1")
    alignment = worker["token_alignment"]
    return {
        "trajectory_id": trajectory["trajectory_id"],
        "matched_pair_id": trajectory["matched_pair_id"],
        "delegation_depth": trajectory["delegation_depth"],
        "thinking_mode": worker["model_execution_metadata"]["thinking_mode"],
        "treatment": trajectory["treatment"],
        "outcome_class": trajectory["evaluation_labels"]["outcome_class"],
        "output_adoption": trajectory["evaluation_labels"]["behavioral_channel"][
            "output_adoption"
        ],
        "unsafe_action_executed": trajectory["evaluation_labels"]["action_channel"][
            "unsafe_action_executed"
        ],
        "controlled_endpoint": endpoint,
        "source_artifact": {
            **_source(path, tracked=False),
            "contains_retrieved_paper_text": True,
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


def _load_index_rows(index_path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in index_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _activation_evidence(
    index_path: Path,
    summary_path: Path,
    activation_root: Path,
) -> dict[str, Any]:
    rows = _load_index_rows(index_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    artifacts: dict[str, dict[str, Any]] = {}
    audit_rows = []
    for row in rows:
        remote_path = row["remote_storage_path"]
        local_path = (activation_root / remote_path).resolve()
        current = artifacts.setdefault(
            remote_path,
            {
                "trajectory_id": row["trajectory_id"],
                "step_index": row["step_index"],
                "agent_id": row["agent_id"],
                "checksum_sha256": row["checksum_sha256"],
                "shape": row["shape"],
                "dtype": row["dtype"],
                "layer_count": len(row["layers"]),
                "checkpoints": [],
                "local_available_at_snapshot_build": local_path.is_file(),
            },
        )
        if current["checksum_sha256"] != row["checksum_sha256"]:
            raise ValueError(f"activation checksum changed across rows: {remote_path}")
        current["checkpoints"].append(row["checkpoint"])
        copied = dict(row)
        copied["local_path"] = local_path.as_posix()
        audit_rows.append(copied)

    for remote_path, artifact in artifacts.items():
        artifact["checkpoints"].sort()
        local_path = (activation_root / remote_path).resolve()
        if not local_path.is_file():
            raise FileNotFoundError(f"activation artifact is missing: {local_path}")
        if _sha256_file(local_path) != artifact["checksum_sha256"]:
            raise ValueError(f"activation checksum mismatch: {local_path}")

    control = run_activation_control_audit(
        audit_rows,
        verify_checksums=False,
    )
    return {
        "index_source": _source(index_path, tracked=False),
        "summary_source": _source(summary_path, tracked=False),
        "summary": summary,
        "artifacts": dict(sorted(artifacts.items())),
        "paired_control": {
            "schema_version": control["schema_version"],
            "index_rows_considered": control["index_rows_considered"],
            "complete_pair_count": control["complete_pair_count"],
            "incomplete_pair_count": control["incomplete_pair_count"],
            "strict_planner_input_control": control["strict_planner_input_control"],
            "claim_scope": control["claim_scope"],
        },
    }


def _cost_evidence(log_path: Path, summary_path: Path) -> dict[str, Any]:
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
        "log_source": _source(log_path, tracked=False),
        "summary_source": _source(summary_path, tracked=False),
        "rows": compact_rows,
        "summary": json.loads(summary_path.read_text(encoding="utf-8")),
    }


def _billing_evidence(path: Path) -> dict[str, Any]:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    apps = snapshot["apps"]
    for app in apps:
        resource_sum = sum(app["resource_totals_usd"].values())
        if not math.isclose(resource_sum, app["actual_total_usd"], abs_tol=1e-8):
            raise ValueError(f"billing resource sum mismatch for {app['app_id']}")
    actual_total = sum(app["actual_total_usd"] for app in apps)
    recorded = snapshot["matrix_totals_usd"]["actual_modal_billing"]
    if not math.isclose(actual_total, recorded, abs_tol=1e-8):
        raise ValueError("matrix billing total does not equal the app totals")
    return {
        "source_artifact": _source(path, tracked=False),
        "source_command": snapshot["source"],
        "source_access_requirement": (
            "Re-run the recorded Modal billing command with project access; "
            "the upstream account export is not committed."
        ),
        "snapshot": snapshot,
        "recomputed_actual_total_usd": round(actual_total, 8),
    }


def _manual_qc(path: Path) -> dict[str, Any]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 8:
        raise ValueError(f"expected 8 manual-QC rows, found {len(rows)}")
    return {
        "source_artifact": _source(path, tracked=False),
        "review_scope": "author/package manual task-preservation review",
        "rows": rows,
        "task_preserved_yes_count": sum(
            row["task_preserved"].strip().lower() == "yes" for row in rows
        ),
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
    return {
        "trajectory_count": len(trajectories),
        "model_turn_count": len(turns),
        "outcome_counts": dict(
            Counter(trajectory["outcome_class"] for trajectory in trajectories)
        ),
        "finish_reason_counts": dict(Counter(turn["finish_reason"] for turn in turns)),
        "truncated_turn_count": sum(turn["truncated"] for turn in turns),
        "maximum_generated_tokens": max(
            turn["generated_token_count"] for turn in turns
        ),
        "controlled_endpoint_occurrences": sum(
            turn["controlled_endpoint_occurrences"] for turn in turns
        ),
        "carrier_marker_occurrences": sum(
            turn["carrier_marker_occurrences"] for turn in turns
        ),
        "exact_injection_payload_occurrences": sum(
            turn["exact_injection_payload_occurrences"] for turn in turns
        ),
        "unsafe_action_trajectory_count": sum(
            trajectory["unsafe_action_executed"] for trajectory in trajectories
        ),
        "tool_requests": requests,
        "injected_worker_token_spans": {
            f"{trajectory['delegation_depth']}__{trajectory['thinking_mode']}": (
                trajectory["injection_exposure"]["token_span"]
            )
            for trajectory in trajectories
            if trajectory["treatment"] == "injected"
        },
    }


def build_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    payload = registry["injection"]["wordings"][registry["assigned_wording"]]
    paths = sorted(
        args.trajectory_root.rglob(
            "telecom__*__gen_controlled_v2_5000__thinking_*.json"
        )
    )
    trajectories = [
        _compact_trajectory(
            path,
            carrier_marker=registry["injection"]["carrier_marker"],
            injection_payload=payload,
        )
        for path in paths
    ]
    if len(trajectories) != 8:
        raise ValueError(f"expected 8 Telecom trajectories, found {len(trajectories)}")

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": "2026-08-09",
        "domain_id": "telecom",
        "generation_protocol_id": "controlled_v2_5000",
        "source_policy": (
            "Raw trajectories, activation tensors/indexes, cost/billing ledgers, "
            "manual-QC CSV, and retrieval-review HTML remain untracked because "
            "they are large, account-derived, or contain retrieved paper text. "
            "This tracked snapshot copies the generated reasoning/visible output "
            "and machine fields needed to audit the report and binds every raw "
            "source by SHA-256."
        ),
        "construction_sources": {
            "registry": {
                "path": _portable_path(args.registry),
                "tracked": True,
                "binding_note": (
                    "The registry binds this evidence artifact by SHA-256; "
                    "omitting the reciprocal registry hash avoids a circular "
                    "content-address dependency."
                ),
            },
            "retrieval_plan": _source(args.retrieval_plan, tracked=True),
            "context_preflight": _source(args.context_preflight, tracked=True),
        },
        "aggregate": _aggregate(trajectories),
        "trajectories": trajectories,
        "activation_evidence": _activation_evidence(
            args.activation_index,
            args.activation_summary,
            args.activation_root,
        ),
        "cost_evidence": _cost_evidence(args.cost_log, args.cost_summary),
        "billing_evidence": _billing_evidence(args.billing_snapshot),
        "manual_qc": _manual_qc(args.manual_qc),
        "retrieval_review_source": _source(
            args.review_artifact,
            tracked=False,
        ),
    }


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=_path, required=True)
    parser.add_argument("--retrieval-plan", type=_path, required=True)
    parser.add_argument("--context-preflight", type=_path, required=True)
    parser.add_argument("--trajectory-root", type=_path, required=True)
    parser.add_argument("--activation-index", type=_path, required=True)
    parser.add_argument("--activation-summary", type=_path, required=True)
    parser.add_argument("--activation-root", type=_path, required=True)
    parser.add_argument("--cost-log", type=_path, required=True)
    parser.add_argument("--cost-summary", type=_path, required=True)
    parser.add_argument("--billing-snapshot", type=_path, required=True)
    parser.add_argument("--manual-qc", type=_path, required=True)
    parser.add_argument("--review-artifact", type=_path, required=True)
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
