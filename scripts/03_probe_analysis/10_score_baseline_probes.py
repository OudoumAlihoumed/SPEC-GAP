#!/usr/bin/env python3
"""Create group-held-out per-step Goldowsky-Dill and LAT scores."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.depth_degradation import validate_prediction_rows  # noqa: E402
from src.analysis.probe_scoring import (  # noqa: E402
    generate_per_step_probe_scores,
    load_match_group_designs,
    summarize_per_step_probe_scores,
    write_per_step_probe_scores,
)
from src.extraction.saved_activations import load_activation_index  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Score saved last-input activations with group-held-out baseline probes. "
            "This is CPU-only and does not call Qwen or start a GPU."
        )
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=PROJECT_ROOT / "results/scenario1/activation_index.jsonl",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "experiments/scenario1/manifest.json",
    )
    parser.add_argument(
        "--label-target",
        choices=("injection_present", "unsafe_action_executed"),
        default="injection_present",
    )
    parser.add_argument(
        "--layers",
        default="all",
        help="Comma-separated layer indices, or 'all' (default).",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=PROJECT_ROOT / "results/scenario1/per_step_probe_scores.jsonl",
    )
    parser.add_argument(
        "--output-summary",
        type=Path,
        default=PROJECT_ROOT / "results/scenario1/per_step_probe_scores_summary.json",
    )
    parser.add_argument("--skip-checksums", action="store_true")
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--max-iter", type=int, default=1000)
    args = parser.parse_args()

    selected_layers = _parse_layers(args.layers)
    score_rows = generate_per_step_probe_scores(
        load_activation_index(args.index),
        match_group_designs=load_match_group_designs(args.manifest),
        label_target=args.label_target,
        layers=selected_layers,
        verify_checksums=not args.skip_checksums,
        random_state=args.random_state,
        max_iter=args.max_iter,
    )
    validate_prediction_rows(score_rows)
    write_per_step_probe_scores(score_rows, args.output_jsonl)

    summary = summarize_per_step_probe_scores(score_rows)
    summary.update({
        "activation_index": args.index.as_posix(),
        "scenario_manifest": args.manifest.as_posix(),
        "output_jsonl": args.output_jsonl.as_posix(),
    })
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


def _parse_layers(value: str) -> list[int] | None:
    if value.strip().lower() == "all":
        return None
    layers = []
    for item in value.split(","):
        try:
            layer = int(item.strip())
        except ValueError as error:
            raise ValueError(f"Invalid layer list {value!r}.") from error
        if layer < 0:
            raise ValueError("Layer indices must be non-negative.")
        layers.append(layer)
    if not layers:
        raise ValueError("At least one layer must be selected.")
    return list(dict.fromkeys(layers))


if __name__ == "__main__":
    main()
