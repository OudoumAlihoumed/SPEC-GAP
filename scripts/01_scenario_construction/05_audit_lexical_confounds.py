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
    canonical_audit_json,
    load_lexical_package,
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
    parser.add_argument("--reference-registry", type=_path, required=True)
    parser.add_argument("--reference-plan", type=_path, required=True)
    parser.add_argument(
        "--inputs-root",
        type=_path,
        default=DEFAULT_INPUTS_ROOT,
    )
    parser.add_argument("--out-json", type=_path, required=True)
    parser.add_argument("--out-markdown", type=_path, required=True)
    args = parser.parse_args()

    focus = load_lexical_package(
        args.focus_registry,
        args.focus_plan,
        inputs_root=args.inputs_root,
        project_root=PROJECT_ROOT,
    )
    reference = load_lexical_package(
        args.reference_registry,
        args.reference_plan,
        inputs_root=args.inputs_root,
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
