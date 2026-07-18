"""Deterministic Matplotlib export helpers for tracked public figures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib


SVG_HASH_SALT = "spec-gap-public-figures-v1"


def normalize_svg(path: str | Path) -> None:
    """Remove renderer-added trailing spaces while preserving SVG content."""

    source = Path(path)
    lines = source.read_text(encoding="utf-8").splitlines()
    source.write_text(
        "\n".join(line.rstrip() for line in lines) + "\n",
        encoding="utf-8",
    )


def save_reproducible_figure(
    figure: Any,
    path: str | Path,
    *,
    metadata: dict[str, Any] | None = None,
    **savefig_kwargs: Any,
) -> None:
    """Save a figure without timestamps or randomized SVG element IDs."""

    destination = Path(path)
    suffix = destination.suffix.lower()
    stable_metadata = dict(metadata or {})
    if suffix == ".svg":
        author = stable_metadata.pop("Author", None)
        if author is not None:
            stable_metadata.setdefault("Creator", author)
        stable_metadata["Date"] = None
    elif suffix == ".pdf":
        stable_metadata["CreationDate"] = None
        stable_metadata["ModDate"] = None

    with matplotlib.rc_context({"svg.hashsalt": SVG_HASH_SALT}):
        figure.savefig(
            destination,
            metadata=stable_metadata,
            **savefig_kwargs,
        )
    if suffix == ".svg":
        normalize_svg(destination)
