"""Calibration analysis: reliability diagrams and ECE breakdown."""

import numpy as np
import matplotlib.pyplot as plt


def reliability_diagram(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
    ax: plt.Axes | None = None,
    title: str = "",
) -> plt.Axes:
    """Plot reliability diagram with gap shading."""
    if ax is None:
        _, ax = plt.subplots(1, 1, figsize=(5, 5))

    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)

    bin_accs, bin_confs, bin_counts = [], [], []
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        mask = (y_prob >= lo) & (y_prob <= hi) if i == n_bins - 1 else (y_prob >= lo) & (y_prob < hi)
        count = mask.sum()
        if count == 0:
            bin_accs.append(0)
            bin_confs.append((lo + hi) / 2)
            bin_counts.append(0)
        else:
            bin_accs.append(float(y_true[mask].mean()))
            bin_confs.append(float(y_prob[mask].mean()))
            bin_counts.append(int(count))

    bin_centers = [(bin_edges[i] + bin_edges[i + 1]) / 2 for i in range(n_bins)]
    width = 1.0 / n_bins

    ax.bar(bin_centers, bin_accs, width=width * 0.9, alpha=0.7, color="#2196F3", label="Accuracy")
    ax.plot([0, 1], [0, 1], "k--", label="Perfect calibration")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction of positives")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(fontsize=9)
    if title:
        ax.set_title(title)
    return ax


def calibration_summary(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> dict:
    """Return calibration metrics dict."""
    from src.probes.linear_probe import compute_ece
    from sklearn.metrics import brier_score_loss

    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    max_ce = 0.0
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        mask = (y_prob >= lo) & (y_prob <= hi) if i == n_bins - 1 else (y_prob >= lo) & (y_prob < hi)
        if mask.sum() > 0:
            gap = abs(y_true[mask].mean() - y_prob[mask].mean())
            max_ce = max(max_ce, gap)

    return {
        "brier_score": float(brier_score_loss(y_true, y_prob)),
        "ece": float(compute_ece(y_true, y_prob, n_bins)),
        "max_calibration_error": float(max_ce),
    }
