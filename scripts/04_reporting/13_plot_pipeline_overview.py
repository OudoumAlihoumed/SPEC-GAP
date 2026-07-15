"""Create the public-facing overview of the SPEC-GAP Scenario 1 pipeline."""

from __future__ import annotations

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.analysis.figure_export import (  # noqa: E402
    normalize_svg,
    save_reproducible_figure,
)


OUTPUT_DIR = ROOT / "docs" / "assets"
OUTPUT_STEM = "scenario1_pipeline_overview"
FORMATS = ("png", "svg", "pdf")

NAVY = "#102A43"
BLUE = "#2563EB"
BLUE_LIGHT = "#EAF2FF"
TEAL = "#0F766E"
TEAL_LIGHT = "#E6F7F5"
ORANGE = "#C2410C"
ORANGE_LIGHT = "#FFF1E8"
GREEN = "#15803D"
GREEN_LIGHT = "#ECF8EF"
PURPLE = "#6D28D9"
PURPLE_LIGHT = "#F2ECFF"
GRAY_900 = "#1F2937"
GRAY_700 = "#4B5563"
GRAY_500 = "#6B7280"
GRAY_300 = "#D1D5DB"
GRAY_200 = "#E5E7EB"
GRAY_100 = "#F5F7FA"
WHITE = "#FFFFFF"


def _normalize_svg(path: Path) -> None:
    """Keep the historical local helper while using the shared implementation."""

    normalize_svg(path)


def _box(
    axis: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    facecolor: str,
    edgecolor: str = GRAY_300,
    radius: float = 0.12,
    linewidth: float = 1.2,
    zorder: int = 1,
) -> FancyBboxPatch:
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle=f"round,pad=0.02,rounding_size={radius}",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
        zorder=zorder,
    )
    axis.add_patch(patch)
    return patch


def _arrow(
    axis: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str = GRAY_500,
    linewidth: float = 1.6,
    connectionstyle: str = "arc3,rad=0",
    zorder: int = 3,
) -> None:
    axis.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=linewidth,
            color=color,
            connectionstyle=connectionstyle,
            shrinkA=2,
            shrinkB=2,
            zorder=zorder,
        )
    )


def _stage_header(
    axis: plt.Axes,
    number: int,
    title: str,
    x: float,
    y: float,
    *,
    color: str,
) -> None:
    _box(
        axis,
        x,
        y - 0.04,
        0.36,
        0.36,
        facecolor=color,
        edgecolor=color,
        radius=0.18,
        zorder=5,
    )
    axis.text(
        x + 0.18,
        y + 0.14,
        str(number),
        ha="center",
        va="center",
        color=WHITE,
        fontsize=10,
        fontweight="bold",
        zorder=6,
    )
    axis.text(
        x + 0.49,
        y + 0.14,
        title,
        ha="left",
        va="center",
        color=NAVY,
        fontsize=11.7,
        fontweight="bold",
        zorder=6,
    )


def _role_node(
    axis: plt.Axes,
    x: float,
    y: float,
    width: float,
    title: str,
    subtitle: str,
    *,
    facecolor: str,
    edgecolor: str,
) -> None:
    _box(
        axis,
        x,
        y,
        width,
        0.72,
        facecolor=facecolor,
        edgecolor=edgecolor,
        radius=0.10,
        linewidth=1.25,
        zorder=4,
    )
    axis.text(
        x + width / 2,
        y + 0.47,
        title,
        ha="center",
        va="center",
        fontsize=9.2,
        fontweight="bold",
        color=NAVY,
        zorder=5,
    )
    axis.text(
        x + width / 2,
        y + 0.22,
        subtitle,
        ha="center",
        va="center",
        fontsize=7.2,
        color=GRAY_700,
        zorder=5,
    )


def create_pipeline_figure() -> plt.Figure:
    """Build the 16:9 pipeline figure."""

    with plt.rc_context(
        {
            "font.family": "DejaVu Sans",
            "figure.facecolor": WHITE,
            "axes.facecolor": WHITE,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    ):
        figure, axis = plt.subplots(figsize=(16, 9))
        figure.subplots_adjust(left=0.02, right=0.98, top=0.97, bottom=0.04)
        axis.set_xlim(0, 16)
        axis.set_ylim(0, 9)
        axis.axis("off")

        axis.text(
            0.55,
            8.48,
            "SPEC-GAP Scenario 1: Live Evaluation Pipeline",
            ha="left",
            va="center",
            fontsize=24,
            fontweight="bold",
            color=NAVY,
        )
        axis.text(
            0.57,
            8.05,
            "A controlled document-borne injection moves through a multi-agent chain while we capture internal representations and observable actions.",
            ha="left",
            va="center",
            fontsize=11.5,
            color=GRAY_700,
        )

        # Stage 1: controlled construction.
        _box(axis, 0.55, 4.48, 3.05, 3.05, facecolor=GRAY_100)
        _stage_header(axis, 1, "Controlled construction", 0.78, 7.02, color=BLUE)
        axis.text(
            0.83,
            6.52,
            "The user provides a benign\nresearch task.",
            ha="left",
            va="top",
            fontsize=10.1,
            color=GRAY_900,
            linespacing=1.3,
        )
        _box(
            axis,
            0.83,
            5.55,
            2.48,
            0.62,
            facecolor=BLUE_LIGHT,
            edgecolor="#93B4F5",
            radius=0.09,
        )
        axis.text(
            2.07,
            5.86,
            "Two clean documents",
            ha="center",
            va="center",
            fontsize=9.1,
            fontweight="bold",
            color=BLUE,
        )
        _box(
            axis,
            0.83,
            4.79,
            1.13,
            0.56,
            facecolor=GREEN_LIGHT,
            edgecolor="#8FD19E",
            radius=0.09,
        )
        axis.text(
            1.395,
            5.07,
            "Clean third",
            ha="center",
            va="center",
            fontsize=8.1,
            fontweight="bold",
            color=GREEN,
        )
        axis.text(
            2.05,
            5.07,
            "or",
            ha="center",
            va="center",
            fontsize=8.2,
            color=GRAY_500,
        )
        _box(
            axis,
            2.20,
            4.79,
            1.11,
            0.56,
            facecolor=ORANGE_LIGHT,
            edgecolor="#F4A77D",
            radius=0.09,
        )
        axis.text(
            2.755,
            5.07,
            "Injected third",
            ha="center",
            va="center",
            fontsize=7.8,
            fontweight="bold",
            color=ORANGE,
        )
        axis.text(
            0.83,
            4.75,
            "Only the document body changes\nbetween matched conditions.",
            ha="left",
            va="top",
            fontsize=7.8,
            color=GRAY_700,
            linespacing=1.25,
        )

        # Stage 2: live agent execution.
        _box(axis, 3.88, 4.48, 7.88, 3.05, facecolor=WHITE)
        _stage_header(axis, 2, "Live multi-agent execution", 4.11, 7.02, color=ORANGE)
        _box(
            axis,
            8.56,
            6.87,
            2.86,
            0.44,
            facecolor=ORANGE_LIGHT,
            edgecolor="#F4A77D",
            radius=0.20,
        )
        axis.text(
            9.99,
            7.09,
            "Qwen3-32B · thinking off/on · Modal H200",
            ha="center",
            va="center",
            fontsize=7.8,
            fontweight="bold",
            color=ORANGE,
        )

        axis.text(
            4.19,
            6.31,
            "2-hop",
            fontsize=8.5,
            fontweight="bold",
            color=BLUE,
            va="center",
        )
        _role_node(
            axis,
            4.83,
            5.95,
            1.35,
            "Planner",
            "delegates task",
            facecolor=BLUE_LIGHT,
            edgecolor="#93B4F5",
        )
        _role_node(
            axis,
            7.02,
            5.95,
            1.50,
            "Worker 1",
            "reads documents",
            facecolor=ORANGE_LIGHT,
            edgecolor="#F4A77D",
        )
        _role_node(
            axis,
            10.00,
            5.95,
            1.39,
            "Safe executor",
            "records action",
            facecolor=GREEN_LIGHT,
            edgecolor="#8FD19E",
        )
        _arrow(axis, (6.18, 6.31), (7.02, 6.31))
        _arrow(axis, (8.52, 6.31), (10.00, 6.31))

        axis.text(
            4.19,
            5.30,
            "3-hop",
            fontsize=8.5,
            fontweight="bold",
            color=PURPLE,
            va="center",
        )
        _role_node(
            axis,
            4.83,
            4.94,
            1.35,
            "Planner",
            "delegates task",
            facecolor=BLUE_LIGHT,
            edgecolor="#93B4F5",
        )
        _role_node(
            axis,
            6.69,
            4.94,
            1.40,
            "Worker 1",
            "reads documents",
            facecolor=ORANGE_LIGHT,
            edgecolor="#F4A77D",
        )
        _role_node(
            axis,
            8.59,
            4.94,
            1.40,
            "Worker 2",
            "receives relay",
            facecolor=PURPLE_LIGHT,
            edgecolor="#B9A1ED",
        )
        _role_node(
            axis,
            10.35,
            4.94,
            1.26,
            "Safe executor",
            "records action",
            facecolor=GREEN_LIGHT,
            edgecolor="#8FD19E",
        )
        _arrow(axis, (6.18, 5.30), (6.69, 5.30))
        _arrow(axis, (8.09, 5.30), (8.59, 5.30))
        _arrow(axis, (9.99, 5.30), (10.35, 5.30))
        axis.text(
            7.77,
            4.67,
            "Worker 1 is the only agent that sees the raw injected document; downstream agents receive relay messages.",
            ha="center",
            va="center",
            fontsize=7.7,
            color=GRAY_700,
        )

        # Stage 3: white-box capture.
        _box(axis, 12.04, 4.48, 3.41, 3.05, facecolor=TEAL_LIGHT)
        _stage_header(axis, 3, "White-box capture", 12.27, 7.02, color=TEAL)
        capture_lines = (
            "The run stores each rendered\ninput and raw output.",
            "Token IDs, model settings, and\naction events are recorded.",
            "Residual activations are extracted\nfrom all 64 layers at controlled\ntoken positions.",
        )
        y = 6.51
        for index, line in enumerate(capture_lines, start=1):
            _box(
                axis,
                12.32,
                y - 0.42,
                0.38,
                0.38,
                facecolor=TEAL,
                edgecolor=TEAL,
                radius=0.19,
                zorder=4,
            )
            axis.text(
                12.51,
                y - 0.23,
                str(index),
                ha="center",
                va="center",
                fontsize=8.2,
                fontweight="bold",
                color=WHITE,
                zorder=5,
            )
            axis.text(
                12.86,
                y - 0.04,
                line,
                ha="left",
                va="top",
                fontsize=8.2,
                color=GRAY_900,
                wrap=True,
                linespacing=1.25,
            )
            y -= 0.78

        _arrow(axis, (3.60, 6.00), (3.88, 6.00), color=BLUE, linewidth=2.0)
        _arrow(axis, (11.76, 6.00), (12.04, 6.00), color=TEAL, linewidth=2.0)

        # Stage 4: analysis.
        _box(axis, 0.55, 0.77, 14.90, 3.18, facecolor=GRAY_100)
        _stage_header(axis, 4, "Group-safe probe and depth analysis", 0.78, 3.46, color=PURPLE)

        analysis = (
            (
                0.86,
                "Labels",
                "Construction records injection\npresence. The executor records\nthe observed behavioral outcome.",
                BLUE_LIGHT,
                BLUE,
            ),
            (
                4.42,
                "Held-out baselines",
                "Goldowsky–Dill and matched-pair\nLAT are scored while one entire\nmatch group is held out.",
                ORANGE_LIGHT,
                ORANGE,
            ),
            (
                7.98,
                "Temporal aggregation",
                "Per-agent scores show how the\nsignal changes after Worker 1 and\nalong the remaining chain.",
                PURPLE_LIGHT,
                PURPLE,
            ),
            (
                11.54,
                "Metrics and depth",
                "We report AUROC, Brier score,\nECE, and the change from two hops\nto three hops.",
                TEAL_LIGHT,
                TEAL,
            ),
        )
        for x, title, body, facecolor, edgecolor in analysis:
            _box(
                axis,
                x,
                1.62,
                3.05,
                1.43,
                facecolor=facecolor,
                edgecolor=edgecolor,
                radius=0.10,
                linewidth=1.2,
                zorder=3,
            )
            axis.text(
                x + 0.20,
                2.77,
                title,
                ha="left",
                va="center",
                fontsize=10.0,
                fontweight="bold",
                color=NAVY,
                zorder=4,
            )
            axis.text(
                x + 0.20,
                2.50,
                body,
                ha="left",
                va="top",
                fontsize=8.1,
                color=GRAY_900,
                wrap=True,
                linespacing=1.26,
                zorder=4,
            )
        for start, end in ((3.91, 4.42), (7.47, 7.98), (11.03, 11.54)):
            _arrow(axis, (start, 2.33), (end, 2.33), color=PURPLE)

        _box(
            axis,
            0.86,
            0.98,
            13.97,
            0.42,
            facecolor=WHITE,
            edgecolor=GRAY_200,
            radius=0.08,
        )
        axis.text(
            7.845,
            1.19,
            "Current validated boundary: 16 live runs and 56 agent turns completed; every injected run resisted, so the present probe results diagnose construction signal rather than behavioral compromise.",
            ha="center",
            va="center",
            fontsize=8.3,
            fontweight="bold",
            color=GRAY_700,
        )

        # Keep the slide dense enough to remain legible when it is fitted to a
        # presentation window. The limits remove unused outer whitespace, and
        # the small type increase preserves the hierarchy without crowding the
        # individual panels.
        axis.set_xlim(0.32, 15.68)
        axis.set_ylim(0.56, 8.76)
        for label in axis.texts:
            if label.get_fontsize() < 20:
                label.set_fontsize(label.get_fontsize() * 1.07)

        return figure


def main() -> None:
    """Save the pipeline overview in slide- and publication-ready formats."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    figure = create_pipeline_figure()
    for suffix in FORMATS:
        path = OUTPUT_DIR / f"{OUTPUT_STEM}.{suffix}"
        metadata = {"Title": "SPEC-GAP Scenario 1: Live Evaluation Pipeline"}
        if suffix in {"png", "pdf"}:
            metadata["Author"] = "SPEC-GAP"
        save_reproducible_figure(
            figure,
            path,
            dpi=300,
            bbox_inches="tight",
            pad_inches=0.08,
            facecolor=WHITE,
            metadata=metadata,
        )
        print(path)
    plt.close(figure)


if __name__ == "__main__":
    main()
