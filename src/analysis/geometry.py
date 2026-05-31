"""Activation geometry analysis: PCA visualization and direction comparisons."""

import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA


def pca_scatter(
    X: np.ndarray,
    y: np.ndarray,
    n_components: int = 2,
    ax: plt.Axes | None = None,
    title: str = "",
    label_names: tuple[str, str] = ("Honest", "Colluder"),
) -> tuple[plt.Axes, PCA]:
    """PCA scatter plot colored by binary label."""
    if ax is None:
        _, ax = plt.subplots(1, 1, figsize=(6, 5))

    pca = PCA(n_components=n_components)
    X_2d = pca.fit_transform(X)
    ev = pca.explained_variance_ratio_

    ax.scatter(X_2d[y == 0, 0], X_2d[y == 0, 1], alpha=0.6, s=30, label=label_names[0], c="#4CAF50")
    ax.scatter(X_2d[y == 1, 0], X_2d[y == 1, 1], alpha=0.6, s=30, label=label_names[1], c="#F44336")
    ax.set_xlabel(f"PC1 ({ev[0]:.1%})")
    ax.set_ylabel(f"PC2 ({ev[1]:.1%})")
    if title:
        ax.set_title(title)
    ax.legend(fontsize=9)
    return ax, pca


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def layer_comparison_pca(
    activations: dict[int, np.ndarray],
    labels: np.ndarray,
    label_names: tuple[str, str] = ("Honest", "Colluder"),
) -> plt.Figure:
    """Side-by-side PCA scatter for all layers."""
    layers = sorted(activations.keys())
    fig, axes = plt.subplots(1, len(layers), figsize=(5 * len(layers), 4))
    if len(layers) == 1:
        axes = [axes]
    for ax, layer in zip(axes, layers):
        pca_scatter(activations[layer], labels, ax=ax, title=f"Layer {layer}", label_names=label_names)
    plt.suptitle("PCA of Residual Stream Activations", y=1.02)
    plt.tight_layout()
    return fig
