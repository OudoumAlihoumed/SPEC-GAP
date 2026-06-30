"""LAT-style representation-direction baseline for SPEC-GAP.

This module implements the Week 1-2 representation-engineering baseline as a
contrast direction in activation space. It is intentionally simple: learn the
positive-minus-negative centroid direction on the train split, project held-out
activations onto that direction, then calibrate the one-dimensional score.
"""

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from sklearn.decomposition import PCA
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut, StratifiedKFold
from sklearn.preprocessing import StandardScaler

from src.probes.linear_probe import CVResult, ProbeResult, compute_ece


class LATDirectionProbe:
    """Contrast-direction probe with one-dimensional logistic calibration."""

    def __init__(self, standardize: bool = True, random_state: int = 42):
        self.standardize = standardize
        self.random_state = random_state
        self.scaler: StandardScaler | None = None
        self.direction_: np.ndarray | None = None
        self.direction_norm_: float | None = None
        self.calibrator_: LogisticRegression | None = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LATDirectionProbe":
        """Fit the LAT contrast direction and calibration model."""
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y, dtype=int)
        if set(np.unique(y)) != {0, 1}:
            raise ValueError("LATDirectionProbe requires binary labels {0, 1}.")

        if self.standardize:
            self.scaler = StandardScaler()
            X_fit = self.scaler.fit_transform(X)
        else:
            self.scaler = None
            X_fit = X

        direction = X_fit[y == 1].mean(axis=0) - X_fit[y == 0].mean(axis=0)
        norm = float(np.linalg.norm(direction))
        if norm == 0.0:
            raise ValueError("Cannot fit LAT direction: class centroids are identical.")

        self.direction_ = direction / norm
        self.direction_norm_ = norm

        train_scores = X_fit @ self.direction_
        self.calibrator_ = LogisticRegression(random_state=self.random_state, solver="lbfgs")
        self.calibrator_.fit(train_scores.reshape(-1, 1), y)
        return self

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        """Project activations onto the learned contrast direction."""
        if self.direction_ is None:
            raise ValueError("LATDirectionProbe is not fitted.")
        X = np.asarray(X, dtype=np.float32)
        X_eval = self.scaler.transform(X) if self.scaler is not None else X
        return X_eval @ self.direction_

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return calibrated probabilities for the positive class."""
        if self.calibrator_ is None:
            raise ValueError("LATDirectionProbe is not fitted.")
        scores = self.decision_function(X).reshape(-1, 1)
        return self.calibrator_.predict_proba(scores)


class ContrastPairLATProbe:
    """LAT reading direction learned by PCA over matched contrast pairs.

    Every pair must contain exactly one negative and one positive activation.
    The first principal component of positive-minus-negative differences is
    oriented toward the positive class, then calibrated on training scores.
    """

    def __init__(self, standardize: bool = True, random_state: int = 42):
        self.standardize = standardize
        self.random_state = random_state
        self.scaler: StandardScaler | None = None
        self.pca_: PCA | None = None
        self.direction_: np.ndarray | None = None
        self.direction_norm_: float | None = None
        self.calibrator_: LogisticRegression | None = None

    @staticmethod
    def _pair_differences(X: np.ndarray, y: np.ndarray, pair_ids: np.ndarray) -> np.ndarray:
        differences = []
        for pair_id in np.unique(pair_ids):
            pair_mask = pair_ids == pair_id
            pair_y = y[pair_mask]
            if pair_mask.sum() != 2 or sorted(pair_y.tolist()) != [0, 1]:
                raise ValueError(
                    "Each contrast_pair_id must contain exactly one negative "
                    "and one positive activation."
                )
            pair_X = X[pair_mask]
            differences.append(pair_X[pair_y == 1][0] - pair_X[pair_y == 0][0])
        return np.asarray(differences, dtype=np.float32)

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        pair_ids: np.ndarray,
    ) -> "ContrastPairLATProbe":
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y, dtype=int)
        pair_ids = np.asarray(pair_ids)
        if not (len(X) == len(y) == len(pair_ids)):
            raise ValueError("X, y, and pair_ids must have the same length.")

        if self.standardize:
            self.scaler = StandardScaler()
            X_fit = self.scaler.fit_transform(X)
        else:
            self.scaler = None
            X_fit = X

        differences = self._pair_differences(X_fit, y, pair_ids)
        # PCA centers its input. Including both orientations makes the
        # contrast axis identifiable even when matched differences share a
        # common mean direction.
        symmetric_differences = np.concatenate([differences, -differences], axis=0)
        self.pca_ = PCA(n_components=1, random_state=self.random_state)
        self.pca_.fit(symmetric_differences)
        direction = self.pca_.components_[0].astype(np.float32, copy=True)
        if float(np.mean(differences @ direction)) < 0.0:
            direction *= -1.0
        norm = float(np.linalg.norm(direction))
        self.direction_ = direction / norm
        self.direction_norm_ = norm

        train_scores = X_fit @ self.direction_
        self.calibrator_ = LogisticRegression(
            random_state=self.random_state,
            solver="lbfgs",
        )
        self.calibrator_.fit(train_scores.reshape(-1, 1), y)
        return self

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        if self.direction_ is None:
            raise ValueError("ContrastPairLATProbe is not fitted.")
        X = np.asarray(X, dtype=np.float32)
        X_eval = self.scaler.transform(X) if self.scaler is not None else X
        return X_eval @ self.direction_

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.calibrator_ is None:
            raise ValueError("ContrastPairLATProbe is not fitted.")
        scores = self.decision_function(X).reshape(-1, 1)
        return self.calibrator_.predict_proba(scores)


@dataclass
class LATLayerResults:
    """LAT results across layers."""

    layer_results: dict[int, CVResult]
    directions: dict[int, np.ndarray]
    direction_norms: dict[int, float]


def _evaluate_fold(model: LATDirectionProbe, X_train, y_train, X_test, y_test) -> ProbeResult:
    """Fit LAT on one split and evaluate held-out examples."""
    model.fit(X_train, y_train)
    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)
    auroc = np.nan if len(np.unique(y_test)) < 2 else roc_auc_score(y_test, y_prob)
    return ProbeResult(
        auroc=auroc,
        accuracy=accuracy_score(y_test, y_pred),
        brier_score=brier_score_loss(y_test, y_prob),
        ece=compute_ece(y_test, y_prob),
        y_true=np.asarray(y_test),
        y_prob=y_prob,
    )


def _aggregate_fold_results(fold_results: list[ProbeResult]) -> CVResult:
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


def train_and_evaluate_lat(
    X: np.ndarray,
    y: np.ndarray,
    n_splits: int = 5,
    standardize: bool = True,
    random_state: int = 42,
) -> CVResult:
    """Stratified K-fold evaluation for the LAT baseline."""
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    fold_results = []
    for train_idx, test_idx in skf.split(X, y):
        model = LATDirectionProbe(standardize=standardize, random_state=random_state)
        fold_results.append(_evaluate_fold(model, X[train_idx], y[train_idx], X[test_idx], y[test_idx]))
    return _aggregate_fold_results(fold_results)


def train_and_evaluate_lat_leave_group_out(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    standardize: bool = True,
    random_state: int = 42,
) -> CVResult:
    """Leave-one-group-out evaluation for the LAT baseline."""
    logo = LeaveOneGroupOut()
    fold_results = []
    for train_idx, test_idx in logo.split(X, y, groups=groups):
        model = LATDirectionProbe(standardize=standardize, random_state=random_state)
        fold_results.append(_evaluate_fold(model, X[train_idx], y[train_idx], X[test_idx], y[test_idx]))
    return _aggregate_fold_results(fold_results)


def train_and_evaluate_contrast_pair_lat(
    X: np.ndarray,
    y: np.ndarray,
    pair_ids: np.ndarray,
    n_splits: int = 5,
    standardize: bool = True,
    random_state: int = 42,
) -> CVResult:
    """Pair-preserving cross-validation for contrast-pair LAT."""

    pair_ids = np.asarray(pair_ids)
    splitter = GroupKFold(n_splits=n_splits)
    fold_results = []
    for train_idx, test_idx in splitter.split(X, y, groups=pair_ids):
        model = ContrastPairLATProbe(
            standardize=standardize,
            random_state=random_state,
        )
        model.fit(X[train_idx], y[train_idx], pair_ids[train_idx])
        y_prob = model.predict_proba(X[test_idx])[:, 1]
        y_pred = (y_prob >= 0.5).astype(int)
        fold_results.append(ProbeResult(
            auroc=roc_auc_score(y[test_idx], y_prob),
            accuracy=accuracy_score(y[test_idx], y_pred),
            brier_score=brier_score_loss(y[test_idx], y_prob),
            ece=compute_ece(y[test_idx], y_prob),
            y_true=np.asarray(y[test_idx]),
            y_prob=y_prob,
        ))
    return _aggregate_fold_results(fold_results)


def train_and_evaluate_contrast_pair_lat_leave_group_out(
    X: np.ndarray,
    y: np.ndarray,
    pair_ids: np.ndarray,
    groups: np.ndarray,
    standardize: bool = True,
    random_state: int = 42,
) -> CVResult:
    """Leave one scenario out while learning LAT from training-only pairs."""

    pair_ids = np.asarray(pair_ids)
    groups = np.asarray(groups)
    splitter = LeaveOneGroupOut()
    fold_results = []
    for train_idx, test_idx in splitter.split(X, y, groups=groups):
        model = ContrastPairLATProbe(
            standardize=standardize,
            random_state=random_state,
        )
        model.fit(X[train_idx], y[train_idx], pair_ids[train_idx])
        y_prob = model.predict_proba(X[test_idx])[:, 1]
        y_pred = (y_prob >= 0.5).astype(int)
        fold_results.append(ProbeResult(
            auroc=roc_auc_score(y[test_idx], y_prob),
            accuracy=accuracy_score(y[test_idx], y_pred),
            brier_score=brier_score_loss(y[test_idx], y_prob),
            ece=compute_ece(y[test_idx], y_prob),
            y_true=np.asarray(y[test_idx]),
            y_prob=y_prob,
        ))
    return _aggregate_fold_results(fold_results)


def evaluate_contrast_pair_lat_all_layers(
    activations: dict[int, np.ndarray],
    labels: np.ndarray,
    pair_ids: np.ndarray,
    groups: np.ndarray | None = None,
    n_splits: int = 5,
    standardize: bool = True,
    leave_group_out: bool = False,
    random_state: int = 42,
) -> LATLayerResults:
    """Evaluate contrast-pair LAT across activation layers."""

    labels = np.asarray(labels)
    pair_ids = np.asarray(pair_ids)
    layer_cv: dict[int, CVResult] = {}
    directions: dict[int, np.ndarray] = {}
    norms: dict[int, float] = {}

    if leave_group_out and groups is None:
        raise ValueError("groups must be provided when leave_group_out=True")

    for layer, X in activations.items():
        if leave_group_out:
            layer_cv[layer] = train_and_evaluate_contrast_pair_lat_leave_group_out(
                X,
                labels,
                pair_ids,
                np.asarray(groups),
                standardize=standardize,
                random_state=random_state,
            )
        else:
            layer_cv[layer] = train_and_evaluate_contrast_pair_lat(
                X,
                labels,
                pair_ids,
                n_splits=n_splits,
                standardize=standardize,
                random_state=random_state,
            )
        full_model = ContrastPairLATProbe(
            standardize=standardize,
            random_state=random_state,
        ).fit(X, labels, pair_ids)
        directions[layer] = full_model.direction_.copy()
        norms[layer] = float(full_model.direction_norm_)

    return LATLayerResults(
        layer_results=layer_cv,
        directions=directions,
        direction_norms=norms,
    )


def evaluate_lat_all_layers(
    activations: dict[int, np.ndarray],
    labels: np.ndarray,
    groups: np.ndarray | None = None,
    n_splits: int = 5,
    standardize: bool = True,
    leave_group_out: bool = False,
    random_state: int = 42,
) -> LATLayerResults:
    """Evaluate LAT across activation layers."""
    labels = np.asarray(labels)
    layer_cv: dict[int, CVResult] = {}
    directions: dict[int, np.ndarray] = {}
    norms: dict[int, float] = {}

    if leave_group_out and groups is None:
        raise ValueError("groups must be provided when leave_group_out=True")

    for layer, X in activations.items():
        if leave_group_out:
            layer_cv[layer] = train_and_evaluate_lat_leave_group_out(
                X,
                labels,
                np.asarray(groups),
                standardize=standardize,
                random_state=random_state,
            )
        else:
            layer_cv[layer] = train_and_evaluate_lat(
                X,
                labels,
                n_splits=n_splits,
                standardize=standardize,
                random_state=random_state,
            )

        full_model = LATDirectionProbe(standardize=standardize, random_state=random_state).fit(X, labels)
        directions[layer] = full_model.direction_.copy()
        norms[layer] = float(full_model.direction_norm_)

    return LATLayerResults(layer_results=layer_cv, directions=directions, direction_norms=norms)


def lat_results_to_dict(layer_results: LATLayerResults) -> dict:
    """Convert LATLayerResults to a JSON-serializable dictionary."""
    out = {}
    for layer, cv in layer_results.layer_results.items():
        out[int(layer)] = {
            "auroc_mean": cv.auroc_mean,
            "auroc_std": cv.auroc_std,
            "accuracy_mean": cv.accuracy_mean,
            "accuracy_std": cv.accuracy_std,
            "brier_mean": cv.brier_mean,
            "brier_std": cv.brier_std,
            "ece_mean": cv.ece_mean,
            "ece_std": cv.ece_std,
            "lat_direction_norm": layer_results.direction_norms[layer],
        }
    return out
