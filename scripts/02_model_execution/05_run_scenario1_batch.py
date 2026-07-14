#!/usr/bin/env python3
"""Step 5: run or resume the complete live Scenario 1 matrix on one warm GPU."""

from __future__ import annotations

import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.infrastructure.modal_qwen_runner import Qwen3Runner, app  # noqa: E402
from src.scenario1.batch import (  # noqa: E402
    build_live_batch,
    load_completed_batch_item,
    trajectory_turn_cost,
)
from src.scenario1.generator import ARTIFACT_ROOT, load_registries  # noqa: E402
from src.scenario1.orchestrator import (  # noqa: E402
    run_live_trajectory,
    write_live_trajectory,
    write_model_turn_result,
)


@app.local_entrypoint()
def run_scenario1_batch(
    thinking_modes: str = "off,on",
    action: str = "validate",
    output_root: str = str(Path(ARTIFACT_ROOT) / "trajectories"),
    max_new_trajectories: int = 0,
    confirm_paid_run: str = "",
) -> None:
    """Validate or resume both canonical match groups in one Modal app."""

    modes = [mode.strip() for mode in thinking_modes.split(",") if mode.strip()]
    registries = load_registries()
    plan = build_live_batch(
        registries,
        thinking_modes=modes,
        output_root=output_root,
    )
    completed: list[tuple[dict, dict]] = []
    pending = []
    legacy_existing = []
    for item in plan:
        record = load_completed_batch_item(item)
        if record is None:
            pending.append(item)
            if Path(item["output_path"]).exists():
                legacy_existing.append(item["trajectory_id"])
        else:
            completed.append((item, record))

    if max_new_trajectories < 0:
        raise ValueError("max_new_trajectories must be zero or greater")
    selected = pending[:max_new_trajectories] if max_new_trajectories else pending
    model_turns = sum(
        3 if item["condition_id"] == "2-hop" else 4 for item in selected
    )
    preview = {
        "action": action,
        "model_called": False,
        "gpu_started": False,
        "total_matrix_trajectories": len(plan),
        "completed_trajectories": len(completed),
        "pending_trajectories": len(pending),
        "legacy_existing_trajectories": legacy_existing,
        "selected_new_trajectories": len(selected),
        "selected_model_turns": model_turns,
        "thinking_modes": modes,
        "selected_ids": [item["trajectory_id"] for item in selected],
    }
    print(json.dumps(preview, indent=2), flush=True)

    if action == "validate":
        print("Batch validation passed. No remote function or GPU was started.")
        return
    if action != "run":
        raise ValueError("action must be validate or run")
    if confirm_paid_run != "RUN_H200_BATCH":
        raise ValueError(
            "paid batch execution requires --confirm-paid-run RUN_H200_BATCH"
        )
    if not selected:
        print("Nothing to run: every selected trajectory already exists and validates.")
        return

    runner = Qwen3Runner()
    new_results = []
    for index, item in enumerate(selected, start=1):
        print(
            f"[{index}/{len(selected)}] running {item['trajectory_id']}",
            flush=True,
        )
        live = run_live_trajectory(
            item["structural_record"],
            thinking_mode=item["thinking_mode"],
            generate_turn=runner.generate_agent_turn.remote,
            on_turn_complete=lambda _request, result: write_model_turn_result(
                result, output_root
            ),
        )
        path = write_live_trajectory(live, output_root)
        summary = {
            "trajectory_id": live["trajectory_id"],
            "output_path": str(path),
            "outcome_class": live["evaluation_labels"]["outcome_class"],
            "unsafe_action_executed": live["evaluation_labels"]["action_channel"][
                "unsafe_action_executed"
            ],
            "estimated_model_turn_h200_cost_usd": round(
                trajectory_turn_cost(live), 8
            ),
        }
        new_results.append(summary)
        print(json.dumps(summary, indent=2), flush=True)

    all_cost = sum(trajectory_turn_cost(record) for _item, record in completed)
    new_cost = sum(item["estimated_model_turn_h200_cost_usd"] for item in new_results)
    print(json.dumps({
        "completed_before_run": len(completed),
        "completed_in_this_run": len(new_results),
        "remaining_after_run": len(pending) - len(new_results),
        "existing_estimated_model_turn_h200_cost_usd": round(all_cost, 8),
        "new_estimated_model_turn_h200_cost_usd": round(new_cost, 8),
        "billing_note": (
            "Per-turn estimates include any cold-start time charged to the first "
            "remote call but exclude CPU, memory, storage, credits, and discounts. "
            "Modal billing is the final source."
        ),
    }, indent=2), flush=True)


__all__ = ["app", "run_scenario1_batch"]
