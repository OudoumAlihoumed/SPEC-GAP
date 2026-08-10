#!/usr/bin/env python3
"""Run the portable Scenario 1 smoke test without starting a GPU.

The local check builds and validates both supported construction cohorts in a
temporary directory: the two shared core fixtures and the nine active fellow
packages. The optional Modal check authenticates against the contributor's
selected workspace with read-only CLI calls, without running the production
app, building its image, calling the model, or allocating a GPU.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from importlib import import_module
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

_generator = import_module("src.scenario1.generator")
_validator = import_module("src.scenario1.validator")
DEFAULT_REGISTRY_PATHS = _generator.DEFAULT_REGISTRY_PATHS
build_request_plan = _generator.build_request_plan
generate_all = _generator.generate_all
load_registries = _generator.load_registries
validate_payload = _validator.validate_payload

FELLOW_PACKAGE_ROOT = (
    PROJECT_ROOT / "experiments" / "scenario1" / "inputs" / "fellow_packages"
)
MODAL_CONNECT_TIMEOUT_SECONDS = 60


def active_fellow_registry_paths(
    package_root: Path = FELLOW_PACKAGE_ROOT,
) -> tuple[Path, ...]:
    """Return only canonical active package registries, never archived pilots."""

    paths = tuple(sorted(package_root.glob("*/domain_config.json")))
    if not paths:
        raise RuntimeError(f"no active fellow registries found under {package_root}")
    return paths


def _run_cohort(
    cohort_id: str,
    registry_paths: Iterable[Path],
    output_root: Path,
) -> dict[str, Any]:
    registries = load_registries(registry_paths)
    records, written_paths = generate_all(registries, str(output_root))

    validation_failures = {
        record["trajectory_id"]: errors
        for record in records
        if (errors := validate_payload(record))
    }
    if validation_failures:
        raise RuntimeError(
            f"{cohort_id} generated invalid trajectories: "
            f"{json.dumps(validation_failures, sort_keys=True)}"
        )

    request_plan = build_request_plan(
        records,
        analysis_tier="exploratory",
    )
    if any(request.get("analysis_tier") != "exploratory" for request in request_plan):
        raise RuntimeError(f"{cohort_id} did not preserve the exploratory tier")
    if not all(Path(path).is_file() for path in written_paths):
        raise RuntimeError(f"{cohort_id} did not write every dry-run trajectory")

    return {
        "cohort_id": cohort_id,
        "domain_count": len(registries),
        "trajectory_count": len(records),
        "schema_validated_trajectory_count": len(records),
        "modal_request_template_count": len(request_plan),
        "analysis_tier": "exploratory",
    }


def run_local_smoke(output_root: Path) -> dict[str, Any]:
    """Build and validate every active package without model or network calls."""

    output_root = output_root.resolve()
    if output_root.exists():
        if not output_root.is_dir():
            raise RuntimeError(f"smoke output root is not a directory: {output_root}")
        if any(output_root.iterdir()):
            raise RuntimeError(
                "smoke output root must be new or empty; refusing to overwrite "
                f"existing files under {output_root}"
            )
    else:
        output_root.mkdir(parents=True)
    cohorts = [
        _run_cohort(
            "shared_core",
            (Path(path) for path in DEFAULT_REGISTRY_PATHS),
            output_root / "shared_core",
        ),
        _run_cohort(
            "active_fellow_packages",
            active_fellow_registry_paths(),
            output_root / "active_fellow_packages",
        ),
    ]
    return {
        "status": "passed",
        "model_called": False,
        "gpu_started": False,
        "cohorts": cohorts,
        "domain_count": sum(item["domain_count"] for item in cohorts),
        "trajectory_count": sum(item["trajectory_count"] for item in cohorts),
        "schema_validated_trajectory_count": sum(
            item["schema_validated_trajectory_count"] for item in cohorts
        ),
        "modal_request_template_count": sum(
            item["modal_request_template_count"] for item in cohorts
        ),
    }


def modal_executable() -> str:
    """Find Modal beside the running Python first, then fall back to PATH."""

    executable_names = ("modal.exe", "modal") if os.name == "nt" else ("modal",)
    for name in executable_names:
        candidate = Path(sys.executable).with_name(name)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    detected = shutil.which("modal")
    if detected:
        return detected
    raise RuntimeError(
        "Modal CLI not found. Install the project with `python -m pip install "
        '-e ".[dev,modal]"` and retry.'
    )


def run_modal_connectivity_check(command: str | None = None) -> dict[str, Any]:
    """Verify Modal access without registering or running an application."""

    modal_command = command or modal_executable()
    try:
        credential_check = subprocess.run(
            [modal_command, "token", "info"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=False,
            text=True,
            timeout=MODAL_CONNECT_TIMEOUT_SECONDS,
        )
        completed = (
            subprocess.run(
                [modal_command, "app", "list", "--json"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                check=False,
                text=True,
                timeout=MODAL_CONNECT_TIMEOUT_SECONDS,
            )
            if credential_check.returncode == 0
            else credential_check
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            "Modal did not respond within 60 seconds. Check network access and "
            "the selected workspace, then retry."
        ) from error
    combined_output = "\n".join(
        part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
    )
    if completed.returncode != 0:
        if "Token not found" in combined_output:
            raise RuntimeError(
                "Modal authentication is missing. Run `modal setup` (or "
                "`python -m modal setup`), select the intended workspace, and retry."
            )
        if "Could not connect to the Modal server" in combined_output:
            raise RuntimeError(
                "Could not reach the Modal service. Check network access, run "
                "`modal token info`, and use `modal setup` if credentials are missing."
            )
        raise RuntimeError(
            "Modal connectivity check failed"
            + (f": {combined_output}" if combined_output else ".")
        )
    return {
        "status": "passed",
        "authenticated": True,
        "workspace_access_verified": True,
        "remote_app_started": False,
        "image_build_started": False,
        "model_called": False,
        "gpu_started": False,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build and validate every active Scenario 1 package in temporary "
            "storage; optionally check authenticated Modal connectivity."
        )
    )
    parser.add_argument(
        "--check-modal",
        action="store_true",
        help=(
            "Verify Modal credentials without running the app, building its "
            "image, calling the model, or starting a GPU; uses read-only CLI calls."
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        help=(
            "Keep generated dry-run files at this path for inspection. By "
            "default they are created in temporary storage and removed. The "
            "provided path must be new or empty."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        if args.output_root is None:
            with tempfile.TemporaryDirectory(prefix="spec-gap-smoke-") as temp_dir:
                summary = run_local_smoke(Path(temp_dir))
                summary["temporary_output_removed"] = True
        else:
            summary = run_local_smoke(args.output_root)
            summary["temporary_output_removed"] = False
            summary["output_root"] = str(args.output_root.resolve())
        summary["modal_connectivity"] = (
            run_modal_connectivity_check()
            if args.check_modal
            else {"status": "not_requested"}
        )
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"Portable smoke test failed: {error}") from error
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
