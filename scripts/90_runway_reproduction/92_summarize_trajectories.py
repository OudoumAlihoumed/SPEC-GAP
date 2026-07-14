"""Summarize construction-grounded safety metrics from trajectory JSONL files.

Usage:
    python scripts/90_runway_reproduction/92_summarize_trajectories.py trajectories/
    python scripts/90_runway_reproduction/92_summarize_trajectories.py \
        run1.jsonl run2.jsonl --output summary.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.analysis.trajectory_metrics import (  # noqa: E402
    load_trajectory_jsonl,
    summarize_dataset,
)


def _resolve_jsonl_paths(inputs: list[Path]) -> list[Path]:
    paths = []
    for item in inputs:
        if item.is_dir():
            paths.extend(sorted(item.glob("*.jsonl")))
        elif item.suffix == ".jsonl" and item.is_file():
            paths.append(item)
        else:
            raise ValueError(f"Not a trajectory JSONL file or directory: {item}")
    unique_paths = list(dict.fromkeys(path.resolve() for path in paths))
    if not unique_paths:
        raise ValueError("No trajectory JSONL files were found.")
    return unique_paths


def main(inputs: list[Path], output: Path | None = None) -> dict:
    paths = _resolve_jsonl_paths(inputs)
    summary = summarize_dataset([load_trajectory_jsonl(path) for path in paths])
    summary["source_files"] = [str(path) for path in paths]
    payload = json.dumps(summary, indent=2) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload)
    else:
        print(payload, end="")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    main(args.inputs, output=args.output)
