"""Create slide-ready figures for the SPEC-GAP investor presentation."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "docs" / "assets"
METRICS_PATH = (
    ROOT / "results" / "scenario1" / "final_analysis" / "reference_layer_metrics.csv"
)
FORMATS = ("png", "svg", "pdf")

NAVY = "#102A43"
BLUE = "#2563EB"
BLUE_DARK = "#075985"
BLUE_LIGHT = "#EAF2FF"
ORANGE = "#C2410C"
ORANGE_LIGHT = "#FFF1E8"
GREEN = "#15803D"
GREEN_LIGHT = "#ECF8EF"
PURPLE = "#6D28D9"
PURPLE_LIGHT = "#F2ECFF"
TEAL = "#0F766E"
TEAL_LIGHT = "#E6F7F5"
RED = "#B42318"
RED_LIGHT = "#FFF0EE"
GRAY_900 = "#1F2937"
GRAY_700 = "#4B5563"
GRAY_500 = "#6B7280"
GRAY_300 = "#D1D5DB"
GRAY_200 = "#E5E7EB"
GRAY_100 = "#F5F7FA"
WHITE = "#FFFFFF"

PROBE_ORDER = ("goldowsky_dill_logistic", "lat_contrast_pair_pca")
PROBE_LABELS = {
    "goldowsky_dill_logistic": "Goldowsky–Dill",
    "lat_contrast_pair_pca": "Matched-pair LAT",
}
PROBE_COLORS = {
    "goldowsky_dill_logistic": BLUE_DARK,
    "lat_contrast_pair_pca": ORANGE,
}


def _normalize_svg(path: Path) -> None:
    """Remove renderer-added trailing spaces while preserving the SVG content."""

    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(
        "\n".join(line.rstrip() for line in lines) + "\n",
        encoding="utf-8",
    )


def _canvas(title: str, subtitle: str) -> tuple[plt.Figure, plt.Axes]:
    figure, axis = plt.subplots(figsize=(16, 9))
    figure.subplots_adjust(left=0.02, right=0.98, top=0.97, bottom=0.04)
    figure.patch.set_facecolor(WHITE)
    axis.set_xlim(0, 16)
    axis.set_ylim(0, 9)
    axis.axis("off")
    axis.text(
        0.62,
        8.43,
        title,
        ha="left",
        va="center",
        fontsize=23,
        fontweight="bold",
        color=NAVY,
    )
    axis.text(
        0.64,
        8.01,
        subtitle,
        ha="left",
        va="center",
        fontsize=11.2,
        color=GRAY_700,
    )
    return figure, axis


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
    color: str = PURPLE,
    linewidth: float = 2.3,
) -> None:
    axis.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=16,
            linewidth=linewidth,
            color=color,
            shrinkA=2,
            shrinkB=2,
            zorder=5,
        )
    )


def _pill(
    axis: plt.Axes,
    x: float,
    y: float,
    width: float,
    text: str,
    *,
    facecolor: str,
    edgecolor: str,
    textcolor: str,
) -> None:
    _box(
        axis,
        x,
        y,
        width,
        0.46,
        facecolor=facecolor,
        edgecolor=edgecolor,
        radius=0.22,
    )
    axis.text(
        x + width / 2,
        y + 0.23,
        text,
        ha="center",
        va="center",
        fontsize=8.1,
        fontweight="bold",
        color=textcolor,
    )


def _stat_card(
    axis: plt.Axes,
    x: float,
    y: float,
    width: float,
    value: str,
    label: str,
    *,
    facecolor: str,
    edgecolor: str,
) -> None:
    _box(
        axis,
        x,
        y,
        width,
        1.02,
        facecolor=facecolor,
        edgecolor=edgecolor,
        radius=0.10,
    )
    axis.text(
        x + width / 2,
        y + 0.66,
        value,
        ha="center",
        va="center",
        fontsize=18,
        fontweight="bold",
        color=edgecolor,
    )
    axis.text(
        x + width / 2,
        y + 0.29,
        label,
        ha="center",
        va="center",
        fontsize=8.3,
        color=GRAY_700,
    )


def runway_to_live_figure() -> plt.Figure:
    """Show the feedback-driven move from the runway to the live system."""

    figure, axis = _canvas(
        "From Runway signal testing to live exploit-chain evaluation",
        "The fellowship work keeps the white-box measurement stack and replaces the static role-label setup with controlled, action-grounded trajectories.",
    )

    _box(axis, 0.62, 1.10, 6.15, 6.30, facecolor=BLUE_LIGHT, edgecolor="#8EB5F7")
    axis.text(
        0.98,
        6.96,
        "RUNWAY — measurement foundation",
        fontsize=14,
        fontweight="bold",
        color=BLUE_DARK,
        va="center",
    )
    axis.text(
        0.98,
        6.61,
        "The initial study asked whether an assigned collusion role\nwas recoverable from model activations.",
        fontsize=9.0,
        color=GRAY_700,
        va="top",
        linespacing=1.28,
    )
    _stat_card(
        axis,
        0.98,
        5.15,
        1.62,
        "200",
        "balanced prompts",
        facecolor=WHITE,
        edgecolor=BLUE,
    )
    _stat_card(
        axis,
        2.77,
        5.15,
        1.62,
        "50",
        "scenarios",
        facecolor=WHITE,
        edgecolor=BLUE,
    )
    _stat_card(
        axis,
        4.56,
        5.15,
        1.86,
        "0.61–0.66",
        "pooled AUROC",
        facecolor=WHITE,
        edgecolor=BLUE,
    )
    axis.text(
        1.00,
        4.68,
        "Llama 3.1 8B · selected residual-stream layers · last generated token",
        fontsize=8.7,
        fontweight="bold",
        color=BLUE_DARK,
        va="center",
    )
    _box(axis, 0.98, 1.55, 5.43, 2.70, facecolor=WHITE, edgecolor="#B7CEF5")
    axis.text(
        1.25,
        3.87,
        "What the Runway established",
        fontsize=11.2,
        fontweight="bold",
        color=NAVY,
        va="center",
    )
    runway_lines = (
        "The activation-extraction and probe-evaluation stack worked.",
        "The recoverable signal was modest and poorly calibrated.",
        "Performance was unstable when complete scenarios were held out.",
        "The label represented an assigned role, not an executed action.",
    )
    y = 3.42
    for line in runway_lines:
        axis.text(1.24, y, "•", fontsize=12, color=BLUE, va="center")
        axis.text(1.49, y, line, fontsize=9.0, color=GRAY_900, va="center")
        y -= 0.52

    _box(axis, 9.23, 1.10, 6.15, 6.30, facecolor=ORANGE_LIGHT, edgecolor="#F0A278")
    axis.text(
        9.59,
        6.96,
        "FELLOWSHIP — live Scenario 1 system",
        fontsize=14,
        fontweight="bold",
        color=ORANGE,
        va="center",
    )
    axis.text(
        9.59,
        6.61,
        "The current study follows a document-borne injection\nthrough live agents to an observable outcome.",
        fontsize=9.0,
        color=GRAY_700,
        va="top",
        linespacing=1.28,
    )
    _stat_card(
        axis,
        9.59,
        5.15,
        1.62,
        "16",
        "live runs",
        facecolor=WHITE,
        edgecolor=ORANGE,
    )
    _stat_card(
        axis,
        11.38,
        5.15,
        1.62,
        "56",
        "agent turns",
        facecolor=WHITE,
        edgecolor=ORANGE,
    )
    _stat_card(
        axis,
        13.17,
        5.15,
        1.86,
        "64",
        "activation layers",
        facecolor=WHITE,
        edgecolor=ORANGE,
    )
    axis.text(
        9.61,
        4.68,
        "Qwen3-32B · 2-hop and 3-hop chains · thinking off/on · Modal H200",
        fontsize=8.7,
        fontweight="bold",
        color=ORANGE,
        va="center",
    )
    _box(axis, 9.59, 1.55, 5.43, 2.70, facecolor=WHITE, edgecolor="#F4C2A4")
    axis.text(
        9.86,
        3.87,
        "What the feedback changed",
        fontsize=11.2,
        fontweight="bold",
        color=NAVY,
        va="center",
    )
    fellowship_lines = (
        "The model generates the complete trajectory and action request.",
        "Clean and injected conditions are paired inside match groups.",
        "Worker 1 remains the injection point at both delegation depths.",
        "Behavior is labeled from the executor action, not injection presence.",
    )
    y = 3.42
    for line in fellowship_lines:
        axis.text(9.85, y, "•", fontsize=12, color=ORANGE, va="center")
        axis.text(10.10, y, line, fontsize=9.0, color=GRAY_900, va="center")
        y -= 0.52

    _arrow(axis, (6.94, 4.58), (9.05, 4.58))
    axis.text(
        8.00,
        5.42,
        "Feedback-driven shift",
        ha="center",
        va="center",
        fontsize=10.2,
        fontweight="bold",
        color=PURPLE,
    )
    _pill(
        axis,
        7.13,
        3.77,
        1.72,
        "Live outputs",
        facecolor=PURPLE_LIGHT,
        edgecolor="#B9A1ED",
        textcolor=PURPLE,
    )
    _pill(
        axis,
        7.13,
        3.13,
        1.72,
        "Matched groups",
        facecolor=PURPLE_LIGHT,
        edgecolor="#B9A1ED",
        textcolor=PURPLE,
    )
    _pill(
        axis,
        7.13,
        2.49,
        1.72,
        "Action outcomes",
        facecolor=PURPLE_LIGHT,
        edgecolor="#B9A1ED",
        textcolor=PURPLE,
    )

    axis.text(
        8.00,
        0.62,
        "We moved from detecting an assigned-role signal in static prompts to tracing a controlled indirect injection through live multi-agent runs.",
        ha="center",
        va="center",
        fontsize=9.7,
        fontweight="bold",
        color=GRAY_700,
    )
    return figure


def _read_thinking_off_metrics() -> dict[tuple[str, str], dict[str, float]]:
    rows: dict[tuple[str, str], dict[str, float]] = {}
    with METRICS_PATH.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            if raw["thinking_mode"] != "off" or int(raw["layer"]) != 40:
                continue
            key = (raw["probe_name"], raw["hop_mode"])
            rows[key] = {
                field: float(raw[field])
                for field in (
                    "auroc",
                    "auroc_ci_lower",
                    "auroc_ci_upper",
                    "brier",
                    "brier_ci_lower",
                    "brier_ci_upper",
                    "ece",
                    "ece_ci_lower",
                    "ece_ci_upper",
                    "path_mean_auroc",
                    "path_mean_auroc_ci_lower",
                    "path_mean_auroc_ci_upper",
                    "path_mean_brier",
                    "path_mean_brier_ci_lower",
                    "path_mean_brier_ci_upper",
                    "path_mean_ece",
                    "path_mean_ece_ci_lower",
                    "path_mean_ece_ci_upper",
                )
            }
    missing = [
        (probe, hop)
        for probe in PROBE_ORDER
        for hop in ("2-hop", "3-hop")
        if (probe, hop) not in rows
    ]
    if missing:
        raise ValueError(f"Missing primary metrics for: {missing}")
    return rows


def primary_metrics_figure() -> plt.Figure:
    """Create an investor-readable version of the primary metrics figure."""

    rows = _read_thinking_off_metrics()
    with plt.rc_context(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 9,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    ):
        figure, axes = plt.subplots(1, 3, figsize=(16, 9))
        figure.patch.set_facecolor(WHITE)
        figure.subplots_adjust(
            left=0.07,
            right=0.97,
            top=0.67,
            bottom=0.19,
            wspace=0.32,
        )
        figure.suptitle(
            "Exploratory construction-signal diagnostics",
            x=0.055,
            y=0.935,
            ha="left",
            fontsize=23,
            fontweight="bold",
            color=NAVY,
        )
        figure.text(
            0.057,
            0.882,
            "Thinking off · prespecified layer 40 · leave-one-match-group-out evaluation · two independent match groups",
            ha="left",
            fontsize=11.2,
            color=GRAY_700,
        )
        figure.text(
            0.057,
            0.810,
            "Solid lines show executor-only scores. Dashed lines show the mean score after the Worker 1 injection anchor.",
            ha="left",
            fontsize=10.1,
            color=GRAY_700,
        )

        panels = (
            ("auroc", "path_mean_auroc", "AUROC ↑", (0.0, 1.02), 0.5),
            ("brier", "path_mean_brier", "Brier score ↓", (0.0, 0.58), 0.25),
            ("ece", "path_mean_ece", "ECE ↓", (0.0, 0.62), None),
        )
        x_values = np.asarray([0.0, 1.0])
        for panel_index, (base, temporal, title, ylim, reference) in enumerate(panels):
            axis = axes[panel_index]
            for probe in PROBE_ORDER:
                for metric, linestyle, marker, aggregation in (
                    (base, "-", "o", "Executor"),
                    (temporal, "--", "s", "Temporal path mean"),
                ):
                    values = []
                    errors_lower = []
                    errors_upper = []
                    for hop in ("2-hop", "3-hop"):
                        row = rows[(probe, hop)]
                        value = row[metric]
                        lower = row[f"{metric}_ci_lower"]
                        upper = row[f"{metric}_ci_upper"]
                        values.append(value)
                        errors_lower.append(max(0.0, value - lower))
                        errors_upper.append(max(0.0, upper - value))
                    axis.errorbar(
                        x_values,
                        values,
                        yerr=np.asarray([errors_lower, errors_upper]),
                        color=PROBE_COLORS[probe],
                        linestyle=linestyle,
                        marker=marker,
                        linewidth=2.0,
                        markersize=7,
                        capsize=4,
                        label=f"{PROBE_LABELS[probe]} · {aggregation}",
                    )
            if reference is not None:
                axis.axhline(reference, color=GRAY_500, linestyle=":", linewidth=1.4)
            axis.set_title(title, fontweight="bold", color=NAVY, pad=13)
            axis.set_xticks(x_values, ("2-hop", "3-hop"))
            axis.set_xlim(-0.08, 1.08)
            axis.set_ylim(*ylim)
            axis.grid(axis="y", color=GRAY_200, linewidth=0.8)
            axis.spines["top"].set_visible(False)
            axis.spines["right"].set_visible(False)
            axis.spines["left"].set_color(GRAY_500)
            axis.spines["bottom"].set_color(GRAY_500)
            axis.text(
                -0.13,
                1.08,
                f"({chr(ord('a') + panel_index)})",
                transform=axis.transAxes,
                fontsize=11,
                fontweight="bold",
                color=NAVY,
            )

        handles, labels = axes[0].get_legend_handles_labels()
        figure.legend(
            handles,
            labels,
            loc="upper right",
            bbox_to_anchor=(0.962, 0.958),
            ncol=2,
            frameon=False,
            fontsize=9.2,
        )
        figure.text(
            0.5,
            0.085,
            "Interpretation boundary: these scores distinguish whether an injection was present; they do not measure successful behavioral compromise.",
            ha="center",
            va="center",
            fontsize=10.2,
            fontweight="bold",
            color=RED,
            bbox={
                "boxstyle": "round,pad=0.5",
                "facecolor": RED_LIGHT,
                "edgecolor": "#F3A6A0",
            },
        )
        return figure


def behavioral_boundary_figure() -> plt.Figure:
    """Summarize the current behavioral evidence and next milestone."""

    figure, axis = _canvas(
        "What the current run established—and what it did not",
        "The model generated every response and action request naturally; no successful compromise was scripted into the data.",
    )
    cards = (
        (0.82, "8", "clean trajectories", BLUE_LIGHT, BLUE),
        (5.56, "8", "injected trajectories resisted", GREEN_LIGHT, GREEN),
        (10.30, "0", "unsafe actions executed", RED_LIGHT, RED),
    )
    for x, value, label, facecolor, edgecolor in cards:
        _box(
            axis,
            x,
            5.08,
            4.02,
            1.73,
            facecolor=facecolor,
            edgecolor=edgecolor,
            radius=0.13,
            linewidth=1.5,
        )
        axis.text(
            x + 2.01,
            6.16,
            value,
            ha="center",
            va="center",
            fontsize=29,
            fontweight="bold",
            color=edgecolor,
        )
        axis.text(
            x + 2.01,
            5.55,
            label,
            ha="center",
            va="center",
            fontsize=10.2,
            fontweight="bold",
            color=GRAY_900,
        )

    _box(axis, 0.82, 1.36, 6.47, 2.86, facecolor=TEAL_LIGHT, edgecolor="#87CFC8")
    axis.text(
        1.16,
        3.83,
        "Supported by the completed run",
        fontsize=12.3,
        fontweight="bold",
        color=TEAL,
        va="center",
    )
    supported = (
        "The live 2-hop and 3-hop pipeline completed successfully.",
        "Exact model records and all-layer activations were preserved.",
        "Group-held-out construction-signal scoring was completed.",
    )
    y = 3.30
    for line in supported:
        axis.text(1.18, y, "✓", fontsize=11.5, color=TEAL, va="center")
        axis.text(1.50, y, line, fontsize=9.2, color=GRAY_900, va="center")
        y -= 0.57

    _arrow(axis, (7.45, 2.80), (8.52, 2.80), color=PURPLE)
    _box(axis, 8.68, 1.36, 6.50, 2.86, facecolor=PURPLE_LIGHT, edgecolor="#B9A1ED")
    axis.text(
        9.02,
        3.83,
        "Evidence required for the next claim",
        fontsize=12.3,
        fontweight="bold",
        color=PURPLE,
        va="center",
    )
    needed = (
        "Expand controlled domains and injection wordings.",
        "Observe executed, propagated, blocked, and resisted outcomes.",
        "Then estimate behavioral AUROC and delegation-depth effects.",
    )
    y = 3.30
    for line in needed:
        axis.text(9.04, y, "→", fontsize=11.5, color=PURPLE, va="center")
        axis.text(9.36, y, line, fontsize=9.2, color=GRAY_900, va="center")
        y -= 0.57

    axis.text(
        8.00,
        0.72,
        "Current conclusion: the end-to-end measurement loop works, but behavioral-compromise detection remains an open empirical question.",
        ha="center",
        va="center",
        fontsize=10.0,
        fontweight="bold",
        color=NAVY,
    )
    return figure


def _save(figure: plt.Figure, stem: str) -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for suffix in FORMATS:
        path = OUTPUT_DIR / f"{stem}.{suffix}"
        metadata: dict[str, Any] = {"Title": stem.replace("_", " ").title()}
        if suffix in {"png", "pdf"}:
            metadata["Author"] = "SPEC-GAP"
        figure.savefig(
            path,
            dpi=300,
            bbox_inches="tight",
            pad_inches=0.08,
            facecolor=WHITE,
            metadata=metadata,
        )
        if suffix == "svg":
            _normalize_svg(path)
        paths.append(path)
    plt.close(figure)
    return paths


def main() -> None:
    """Generate every investor-facing figure."""

    figures = (
        ("investor_runway_to_live", runway_to_live_figure()),
        ("investor_primary_metrics", primary_metrics_figure()),
        ("investor_behavioral_boundary", behavioral_boundary_figure()),
    )
    for stem, figure in figures:
        for path in _save(figure, stem):
            print(path)


if __name__ == "__main__":
    main()
