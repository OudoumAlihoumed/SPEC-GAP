"""Week 1-2 LAT baseline on saved runway activations.

This script reads the pre-fellowship collusion activation artifact and evaluates
a LAT-style representation-direction baseline across layers. It does not extract
new activations or run model inference.

Usage:
    python scripts/90_runway_reproduction/94_run_lat_baseline.py
    SPEC_GAP_ARTIFACT_ROOT=/path/to/artifacts \
      python scripts/90_runway_reproduction/94_run_lat_baseline.py
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.analysis.runway_artifacts import (  # noqa: E402
    find_artifact_root,
    load_runway_artifacts,
)
from src.probes.lat_baseline import evaluate_lat_all_layers, lat_results_to_dict


def run_lat_baseline(artifact_root: Path | None = None, output_path: Path | None = None) -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    artifact_root = artifact_root or find_artifact_root(repo_root)
    activations, labels, scenario_ids = load_runway_artifacts(artifact_root)

    print(f"Loaded {len(labels)} activation rows from {artifact_root}")
    print(f"Layers: {sorted(activations)}")
    print(f"Labels: positive={int(labels.sum())}, negative={int((labels == 0).sum())}")

    stratified = evaluate_lat_all_layers(activations, labels, n_splits=5)
    leave_scenario_out = evaluate_lat_all_layers(
        activations,
        labels,
        groups=scenario_ids,
        leave_group_out=True,
    )

    output = {
        "experiment": "week1_week2_lat_baseline",
        "method": "LAT-style contrast direction with one-dimensional logistic calibration",
        "date": datetime.now().isoformat(),
        "source_artifacts": {
            "activations": "02_collusion_probe/week2_collusion_probe_activations.npz",
            "responses": "02_collusion_probe/week2_collusion_probe_responses.json",
        },
        "n_prompts": int(len(labels)),
        "n_positive": int(labels.sum()),
        "n_negative": int((labels == 0).sum()),
        "layers": sorted(int(layer) for layer in activations),
        "stratified_cv": lat_results_to_dict(stratified),
        "leave_scenario_out_cv": lat_results_to_dict(leave_scenario_out),
    }

    if output_path is None:
        output_path = repo_root / "reports" / "week1_week2_lat_baseline_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))
    print(f"LAT baseline results saved to {output_path}")

    best_layer = max(output["stratified_cv"], key=lambda layer: output["stratified_cv"][layer]["auroc_mean"])
    best = output["stratified_cv"][best_layer]
    print(
        f"Best stratified LAT layer: {best_layer} "
        f"AUROC={best['auroc_mean']:.3f} +/- {best['auroc_std']:.3f} "
        f"Brier={best['brier_mean']:.3f} ECE={best['ece_mean']:.3f}"
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    run_lat_baseline(artifact_root=args.artifact_root, output_path=args.output)
