"""Tests for the publication-ready fixed-layer analysis builder."""

from __future__ import annotations

from pathlib import Path
import runpy


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    PROJECT_ROOT / "scripts/04_reporting/16_build_fixed_layer_analysis.py"
)


def _script_namespace() -> dict:
    return runpy.run_path(SCRIPT_PATH, run_name="spec_gap_fixed_layer_analysis")


def test_activation_catalog_has_one_row_per_tensor_file():
    namespace = _script_namespace()
    base = {
        "domain_id": "fin",
        "match_group_id": "fin",
        "trajectory_id": "finance__2hop__clean__thinking_off",
        "treatment": "clean",
        "delegation_depth": "2-hop",
        "thinking_mode": "off",
        "step_index": 2,
        "agent_id": "worker_1",
        "agent_role": "worker",
        "checksum_sha256": "a" * 64,
        "layers": list(range(64)),
        "remote_storage_path": (
            "activations/finance__2hop__clean__thinking_off/off/step_002.pt"
        ),
    }
    rows = [
        {**base, "checkpoint": "last_input_token"},
        {**base, "checkpoint": "last_visible_answer_token"},
    ]

    catalog = namespace["build_activation_artifact_catalog"](rows)

    assert len(catalog) == 1
    assert catalog[0]["domain"] == "Finance"
    assert catalog[0]["layer_count"] == 64
    assert catalog[0]["checkpoints"] == (
        "last_input_token;last_visible_answer_token"
    )
    assert catalog[0]["activation_file"].endswith("step_002.pt")


def test_activation_catalog_rejects_inconsistent_tensor_metadata():
    namespace = _script_namespace()
    base = {
        "domain_id": "aihc",
        "match_group_id": "aihc",
        "trajectory_id": "aihc__2hop__clean__thinking_off",
        "treatment": "clean",
        "delegation_depth": "2-hop",
        "thinking_mode": "off",
        "step_index": 0,
        "agent_id": "planner_1",
        "agent_role": "planner",
        "checkpoint": "last_input_token",
        "checksum_sha256": "b" * 64,
        "layers": [0, 1],
        "remote_storage_path": "activations/shared/off/step_000.pt",
    }

    conflicting = {**base, "treatment": "injected"}

    try:
        namespace["build_activation_artifact_catalog"]([base, conflicting])
    except ValueError as error:
        assert "inconsistent treatment" in str(error)
    else:
        raise AssertionError("Expected inconsistent tensor metadata to fail.")
