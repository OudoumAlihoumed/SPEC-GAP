#!/usr/bin/env python3
"""Compare injection wording with clean carrier text across two domains."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.scenario1.lexical_confounds import (  # noqa: E402
    build_lexical_confound_audit,
    build_lexical_package_snapshot,
    canonical_audit_json,
    canonical_package_snapshot_json,
    load_lexical_package,
    load_lexical_package_snapshot,
    render_lexical_confound_markdown,
)


DEFAULT_INPUTS_ROOT = PROJECT_ROOT / "experiments" / "scenario1" / "inputs"


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Measure lexical overlap between two Scenario 1 injections and "
            "their validated clean retrieval views."
        )
    )
    parser.add_argument("--focus-registry", type=_path, required=True)
    parser.add_argument("--focus-plan", type=_path, required=True)
    parser.add_argument("--reference-registry", type=_path)
    parser.add_argument("--reference-plan", type=_path)
    parser.add_argument("--reference-snapshot", type=_path)
    parser.add_argument(
        "--inputs-root",
        type=_path,
        default=DEFAULT_INPUTS_ROOT,
    )
    parser.add_argument("--reference-inputs-root", type=_path)
    parser.add_argument("--reference-project-root", type=_path)
    parser.add_argument("--reference-source-commit")
    parser.add_argument("--reference-snapshot-out", type=_path)
    parser.add_argument("--out-json", type=_path, required=True)
    parser.add_argument("--out-markdown", type=_path, required=True)
    args = parser.parse_args()

    has_reference_files = (
        args.reference_registry is not None or args.reference_plan is not None
    )
    if args.reference_snapshot is not None and has_reference_files:
        parser.error(
            "use either --reference-snapshot or the reference registry/plan"
        )
    if args.reference_snapshot is None and (
        args.reference_registry is None or args.reference_plan is None
    ):
        parser.error(
            "provide --reference-snapshot or both --reference-registry and "
            "--reference-plan"
        )
    if args.reference_snapshot is not None and (
        args.reference_inputs_root is not None
        or args.reference_project_root is not None
        or args.reference_source_commit is not None
        or args.reference_snapshot_out is not None
    ):
        parser.error(
            "snapshot generation options require a reference registry/plan"
        )
    if (args.reference_snapshot_out is None) != (
        args.reference_source_commit is None
    ):
        parser.error(
            "--reference-snapshot-out and --reference-source-commit must be "
            "provided together"
        )

    focus = load_lexical_package(
        args.focus_registry,
        args.focus_plan,
        inputs_root=args.inputs_root,
        project_root=PROJECT_ROOT,
    )
    if args.reference_snapshot is not None:
        reference = load_lexical_package_snapshot(
            args.reference_snapshot,
            project_root=PROJECT_ROOT,
        )
    else:
        reference = load_lexical_package(
            args.reference_registry,
            args.reference_plan,
            inputs_root=args.reference_inputs_root or args.inputs_root,
            project_root=args.reference_project_root or PROJECT_ROOT,
        )
        if args.reference_snapshot_out is not None:
            snapshot = build_lexical_package_snapshot(
                reference,
                source_commit=args.reference_source_commit,
            )
            args.reference_snapshot_out.parent.mkdir(parents=True, exist_ok=True)
            args.reference_snapshot_out.write_text(
                canonical_package_snapshot_json(snapshot),
                encoding="utf-8",
            )
            reference = load_lexical_package_snapshot(
                args.reference_snapshot_out,
                project_root=PROJECT_ROOT,
            )
    audit = build_lexical_confound_audit(focus, reference)

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(canonical_audit_json(audit), encoding="utf-8")
    args.out_markdown.write_text(
        render_lexical_confound_markdown(audit),
        encoding="utf-8",
    )
    print(f"wrote: {args.out_json}")
    print(f"wrote: {args.out_markdown}")


if __name__ == "__main__":
    main()
