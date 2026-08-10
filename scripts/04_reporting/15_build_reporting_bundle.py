#!/usr/bin/env python3
"""Rebuild the paper and public-facing reporting outputs in dependency order."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTING_SNAPSHOT = PROJECT_ROOT / "results/scenario1/reporting_snapshot.json"
REPORTING_STAGES = (
    (
        PROJECT_ROOT / "scripts/03_probe_analysis/12_plot_probe_analysis.py",
        "--snapshot-input",
        REPORTING_SNAPSHOT,
    ),
    (PROJECT_ROOT / "scripts/04_reporting/13_plot_pipeline_overview.py",),
    (PROJECT_ROOT / "scripts/04_reporting/14_plot_investor_figures.py",),
)


def reporting_commands(
    python_executable: str | Path = sys.executable,
) -> tuple[tuple[str, ...], ...]:
    """Return the stable command sequence used to rebuild reporting outputs."""

    return tuple(
        (str(python_executable), *(str(part) for part in stage))
        for stage in REPORTING_STAGES
    )


def run_reporting_bundle(
    *,
    python_executable: str | Path = sys.executable,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> None:
    """Run each reporting stage and stop immediately if one stage fails."""

    for command in reporting_commands(python_executable):
        relative_script = Path(command[1]).relative_to(PROJECT_ROOT)
        print(f"Running {relative_script}", flush=True)
        runner(command, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    """Build the complete reporting bundle without starting a model or GPU."""

    run_reporting_bundle()
    print("Reporting bundle complete.")


if __name__ == "__main__":
    main()
