"""Goldowsky-Dill linear probing for SPEC-GAP activation analysis."""

from dataclasses import dataclass, field
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold, LeaveOneGroupOut
from sklearn.metrics import roc_auc_score, brier_score_loss, accuracy_score
from sklearn.decomposition import PCA


@dataclass
class ProbeResult:
    """Single evaluation result."""
    auroc: float
    accuracy: float
    brier_score: float
    ece: float
    y_true: np.ndarray
    y_prob: np.ndarray


@dataclass
class CVResult:
    """Cross-validated evaluation result."""
    auroc_mean: float
    auroc_std: float
    auroc_per_fold: list[float]
    accuracy_mean: float
    accuracy_std: float
    brier_mean: float
    brier_std: float
    ece_mean: float
    ece_std: float


@dataclass
class LayerResults:
    """Results across all layers."""
    layer_results: dict[int, CVResult]
    deception_directions: dict[int, np.ndarray]
    diff_in_means: dict[int, np.ndarray]


def compute_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error with equal-width bins."""
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    if n == 0:
        return 0.0
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        if i < n_bins - 1:
            mask = (y_prob >= lo) & (y_prob < hi)
        else:
            mask = (y_prob >= lo) & (y_prob <= hi)
        count = mask.sum()
        if count == 0:
            continue
        avg_confidence = y_prob[mask].mean()
        avg_accuracy = y_true[mask].mean()
        ece += (count / n) * abs(avg_accuracy - avg_confidence)
    return float(ece)


def make_probe_pipeline(
    C: float = 1.0,
    max_iter: int = 1000,
    use_scaler: bool = True,
    pca_components: int | None = None,
    random_state: int = 42,
) -> Pipeline:
    """Create sklearn Pipeline with optional scaler, PCA, and logistic regression."""
    steps = []
    if use_scaler:
        steps.append(("scaler", StandardScaler()))
    if pca_components is not None:
        steps.append(("pca", PCA(n_components=pca_components)))
    steps.append((
        "clf",
        LogisticRegression(C=C, max_iter=max_iter, random_state=random_state, solver="lbfgs"),
    ))
    return Pipeline(steps)


def _evaluate_fold(pipeline: Pipeline, X_train, y_train, X_test, y_test) -> ProbeResult:
    """Fit pipeline on train split and evaluate on test split."""
    pipeline.fit(X_train, y_train)
    y_prob = pipeline.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)
    n_classes = len(np.unique(y_test))
    if n_classes < 2:
        auroc = np.nan
    else:
        auroc = roc_auc_score(y_test, y_prob)
    return ProbeResult(
        auroc=auroc,
        accuracy=accuracy_score(y_test, y_pred),
        brier_score=brier_score_loss(y_test, y_prob),
        ece=compute_ece(y_test, y_prob),
        y_true=np.asarray(y_test),
        y_prob=y_prob,
    )


def _aggregate_fold_results(fold_results: list[ProbeResult]) -> CVResult:
    """Aggregate per-fold ProbeResults into a CVResult."""
    aurocs = [r.auroc for r in fold_results]
    accuracies = [r.accuracy for r in fold_results]
    briers = [r.brier_score for r in fold_results]
    eces = [r.ece for r in fold_results]
    return CVResult(
        auroc_mean=float(np.nanmean(aurocs)),
        auroc_std=float(np.nanstd(aurocs)),
        auroc_per_fold=aurocs,
        accuracy_mean=float(np.mean(accuracies)),
        accuracy_std=float(np.std(accuracies)),
        brier_mean=float(np.mean(briers)),
        brier_std=float(np.std(briers)),
        ece_mean=float(np.mean(eces)),
        ece_std=float(np.std(eces)),
    )


def train_and_evaluate(
    X: np.ndarray,
    y: np.ndarray,
    n_splits: int = 5,
    C: float = 1.0,
    max_iter: int = 1000,
    pca_components: int | None = None,
    random_state: int = 42,
) -> CVResult:
    """Stratified K-fold cross-validated probe evaluation."""
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    fold_results = []
    for train_idx, test_idx in skf.split(X, y):
        pipe = make_probe_pipeline(C=C, max_iter=max_iter, pca_components=pca_components, random_state=random_state)
        result = _evaluate_fold(pipe, X[train_idx], y[train_idx], X[test_idx], y[test_idx])
        fold_results.append(result)
    return _aggregate_fold_results(fold_results)


def train_and_evaluate_leave_scenario_out(
    X: np.ndarray,
    y: np.ndarray,
    scenario_ids: np.ndarray,
    C: float = 1.0,
    max_iter: int = 1000,
    pca_components: int | None = None,
    random_state: int = 42,
) -> CVResult:
    """Leave-one-group-out CV using scenario_ids as groups."""
    logo = LeaveOneGroupOut()
    fold_results = []
    for train_idx, test_idx in logo.split(X, y, groups=scenario_ids):
        pipe = make_probe_pipeline(C=C, max_iter=max_iter, pca_components=pca_components, random_state=random_state)
        result = _evaluate_fold(pipe, X[train_idx], y[train_idx], X[test_idx], y[test_idx])
        fold_results.append(result)
    return _aggregate_fold_results(fold_results)


def compute_deception_direction(
    X: np.ndarray,
    y: np.ndarray,
    C: float = 1.0,
    max_iter: int = 1000,
    random_state: int = 42,
) -> tuple[np.ndarray, float]:
    """Train probe on full data and extract normalized coefficient vector."""
    pipe = make_probe_pipeline(C=C, max_iter=max_iter, use_scaler=True, random_state=random_state)
    pipe.fit(X, y)
    coef = pipe.named_steps["clf"].coef_[0].copy()
    scaler = pipe.named_steps["scaler"]
    coef = coef / scaler.scale_
    norm = float(np.linalg.norm(coef))
    direction = coef / norm if norm > 0 else coef
    return direction, norm


def compute_diff_in_means(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    """Difference-in-means direction between positive and negative class."""
    y = np.asarray(y)
    direction = X[y == 1].mean(axis=0) - X[y == 0].mean(axis=0)
    norm = float(np.linalg.norm(direction))
    return direction, norm


def evaluate_all_layers(
    activations: dict[int, np.ndarray],
    labels: np.ndarray,
    metadata: dict | None = None,
    n_splits: int = 5,
    C: float = 1.0,
    max_iter: int = 1000,
    pca_components: int | None = None,
    leave_scenario_out: bool = False,
    random_state: int = 42,
) -> LayerResults:
    """Run probe training across all layers in activations dict."""
    labels = np.asarray(labels)
    layer_cv: dict[int, CVResult] = {}
    directions: dict[int, np.ndarray] = {}
    dim_dirs: dict[int, np.ndarray] = {}

    scenario_ids = None
    if leave_scenario_out:
        if metadata is None or "scenario_idx" not in metadata:
            raise ValueError("metadata must contain 'scenario_idx' when leave_scenario_out=True")
        scenario_ids = np.asarray(metadata["scenario_idx"])

    for layer, X in activations.items():
        if leave_scenario_out:
            layer_cv[layer] = train_and_evaluate_leave_scenario_out(
                X, labels, scenario_ids, C=C, max_iter=max_iter,
                pca_components=pca_components, random_state=random_state,
            )
        else:
            layer_cv[layer] = train_and_evaluate(
                X, labels, n_splits=n_splits, C=C, max_iter=max_iter,
                pca_components=pca_components, random_state=random_state,
            )
        direction, _ = compute_deception_direction(X, labels, C=C, max_iter=max_iter, random_state=random_state)
        directions[layer] = direction
        dim_dir, _ = compute_diff_in_means(X, labels)
        dim_dirs[layer] = dim_dir

    return LayerResults(
        layer_results=layer_cv,
        deception_directions=directions,
        diff_in_means=dim_dirs,
    )


def results_to_dict(layer_results: LayerResults) -> dict:
    """Convert LayerResults to a JSON-serializable dict."""
    out = {}
    for layer, cv in layer_results.layer_results.items():
        dec_norm = float(np.linalg.norm(layer_results.deception_directions[layer]))
        dim_norm = float(np.linalg.norm(layer_results.diff_in_means[layer]))
        out[int(layer)] = {
            "auroc_mean": cv.auroc_mean,
            "auroc_std": cv.auroc_std,
            "accuracy_mean": cv.accuracy_mean,
            "accuracy_std": cv.accuracy_std,
            "brier_mean": cv.brier_mean,
            "brier_std": cv.brier_std,
            "ece_mean": cv.ece_mean,
            "ece_std": cv.ece_std,
            "deception_direction_norm": dec_norm,
            "diff_in_means_norm": dim_norm,
        }
    return out
