#!/usr/bin/env python3
"""Analyze depth degradation from precomputed probe-prediction JSONL rows."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.depth_degradation import (
    analyze_depth_degradation,
    load_prediction_jsonl,
    tabular_result_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path)
    parser.add_argument("--n-bootstrap", type=int, default=1000)
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--n-bins", type=int, default=10)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    result = analyze_depth_degradation(
        load_prediction_jsonl(args.predictions),
        experiment_id=args.experiment_id,
        n_bootstrap=args.n_bootstrap,
        confidence=args.confidence,
        n_bins=args.n_bins,
        random_state=args.random_state,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    if args.output_csv:
        rows = tabular_result_rows(result)
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = sorted({key for row in rows for key in row})
        with args.output_csv.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
