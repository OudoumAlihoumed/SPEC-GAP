"""Tests for tier-safe provenance in the final probe-analysis entry point."""

from __future__ import annotations

import json
from pathlib import Path
import runpy


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts/03_probe_analysis/12_plot_probe_analysis.py"


def _trajectory(*, mode: str, tier: str, revision: str) -> dict:
    return {
        "trajectory_id": f"trajectory-{tier}-{mode}",
        "model": {
            "model_name": "Qwen/Qwen3-32B",
            "provider": "modal",
            "model_revision": revision,
            "tokenizer_name": "Qwen/Qwen3-32B",
            "tokenizer_revision": revision,
            "dtype": "bfloat16",
            "seed": 0,
            "num_hidden_layers": 64,
            "thinking_mode": mode,
            "decoding_settings": {"temperature": 0.6, "seed": 0},
        },
        "trajectory_trace": {
            "full_events": [
                {
                    "type": "agent_turn",
                    "model_execution_metadata": {"analysis_tier": tier},
                }
            ]
        },
    }


def _write_trajectory(root: Path, *, mode: str, tier: str, revision: str) -> None:
    destination = root / tier / mode / f"trajectory-{tier}-{mode}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(_trajectory(mode=mode, tier=tier, revision=revision)),
        encoding="utf-8",
    )


def test_model_config_loader_reads_only_selected_tier(tmp_path):
    for mode in ("off", "on"):
        _write_trajectory(
            tmp_path,
            mode=mode,
            tier="definitive",
            revision="definitive-revision",
        )
        _write_trajectory(
            tmp_path,
            mode=mode,
            tier="exploratory",
            revision="exploratory-revision",
        )
    namespace = runpy.run_path(
        str(SCRIPT_PATH),
        run_name="spec_gap_probe_reporting_test",
    )

    configs = namespace["_load_model_configs"](tmp_path, "definitive")

    assert {config["thinking_mode"] for config in configs} == {"off", "on"}
    assert {config["analysis_tier"] for config in configs} == {"definitive"}
    assert {config["model_revision"] for config in configs} == {"definitive-revision"}
