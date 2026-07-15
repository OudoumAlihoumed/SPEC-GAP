"""Regression tests for byte-stable public figure exports."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.analysis.figure_export import save_reproducible_figure


def _figure():
    figure, axis = plt.subplots(figsize=(2.0, 1.5))
    axis.plot((0, 1), (0.25, 0.75))
    axis.set_title("Stable figure")
    return figure


def test_svg_and_pdf_exports_are_byte_stable_and_omit_dates(tmp_path):
    for suffix in ("svg", "pdf"):
        first = tmp_path / f"first.{suffix}"
        second = tmp_path / f"second.{suffix}"
        first_figure = _figure()
        second_figure = _figure()
        metadata = {"Title": "Stable SPEC-GAP figure", "Author": "SPEC-GAP"}

        save_reproducible_figure(
            first_figure,
            first,
            metadata=metadata,
            dpi=72,
            bbox_inches="tight",
        )
        save_reproducible_figure(
            second_figure,
            second,
            metadata=metadata,
            dpi=72,
            bbox_inches="tight",
        )
        plt.close(first_figure)
        plt.close(second_figure)

        assert first.read_bytes() == second.read_bytes()
        payload = first.read_bytes()
        assert b"CreationDate" not in payload
        assert b"ModDate" not in payload
        assert b"<dc:date>" not in payload
