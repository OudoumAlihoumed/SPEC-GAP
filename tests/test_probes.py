"""Tests for linear probe module on synthetic data (CPU, no GPU needed)."""

import json

import numpy as np
import pytest

from src.probes.linear_probe import (
    CVResult,
    LayerResults,
    compute_deception_direction,
    compute_diff_in_means,
    compute_ece,
    evaluate_all_layers,
    make_probe_pipeline,
    results_to_dict,
    train_and_evaluate,
    train_and_evaluate_leave_scenario_out,
)
from src.probes.lat_baseline import (
    ContrastPairLATProbe,
    LATDirectionProbe,
    evaluate_contrast_pair_lat_all_layers,
    evaluate_lat_all_layers,
    lat_results_to_dict,
    train_and_evaluate_lat,
    train_and_evaluate_lat_leave_group_out,
    train_and_evaluate_contrast_pair_lat,
    train_and_evaluate_contrast_pair_lat_leave_group_out,
)


@pytest.fixture(scope="module")
def separable_data():
    rng = np.random.RandomState(42)
    n = 100
    d = 100
    X_pos = rng.randn(n // 2, d).astype(np.float32) + 2.0
    X_neg = rng.randn(n // 2, d).astype(np.float32)
    X = np.vstack([X_pos, X_neg])
    y = np.array([1] * (n // 2) + [0] * (n // 2))
    return X, y


@pytest.fixture(scope="module")
def random_data():
    rng = np.random.RandomState(42)
    X = rng.randn(100, 100).astype(np.float32)
    y = rng.randint(0, 2, size=100)
    return X, y


class TestECE:
    def test_perfect_predictions(self):
        y_true = np.array([1, 1, 0, 0])
        y_prob = np.array([1.0, 1.0, 0.0, 0.0])
        assert compute_ece(y_true, y_prob) < 0.01

    def test_ece_range(self, separable_data):
        X, y = separable_data
        pipe = make_probe_pipeline()
        pipe.fit(X, y)
        y_prob = pipe.predict_proba(X)[:, 1]
        ece = compute_ece(y, y_prob)
        assert 0.0 <= ece <= 1.0

    def test_empty_input(self):
        assert compute_ece(np.array([]), np.array([])) == 0.0


class TestProbePipeline:
    def test_has_scaler(self):
        pipe = make_probe_pipeline()
        assert "scaler" in pipe.named_steps

    def test_has_pca_when_requested(self):
        pipe = make_probe_pipeline(pca_components=10)
        assert "pca" in pipe.named_steps

    def test_pca_uses_experiment_seed(self):
        pipe = make_probe_pipeline(pca_components=10, random_state=17)
        assert pipe.named_steps["pca"].random_state == 17

    def test_no_pca_by_default(self):
        pipe = make_probe_pipeline()
        assert "pca" not in pipe.named_steps

    def test_no_scaler_when_disabled(self):
        pipe = make_probe_pipeline(use_scaler=False)
        assert "scaler" not in pipe.named_steps


class TestTrainAndEvaluate:
    def test_separable_high_auroc(self, separable_data):
        X, y = separable_data
        result = train_and_evaluate(X, y, n_splits=5)
        assert result.auroc_mean > 0.9

    def test_random_near_chance(self, random_data):
        X, y = random_data
        result = train_and_evaluate(X, y, n_splits=5)
        assert 0.3 < result.auroc_mean < 0.7

    def test_result_fields(self, separable_data):
        X, y = separable_data
        result = train_and_evaluate(X, y)
        assert isinstance(result, CVResult)
        assert isinstance(result.auroc_mean, float)
        assert isinstance(result.auroc_std, float)
        assert isinstance(result.brier_mean, float)
        assert isinstance(result.ece_mean, float)

    def test_fold_count(self, separable_data):
        X, y = separable_data
        result = train_and_evaluate(X, y, n_splits=5)
        assert len(result.auroc_per_fold) == 5

    def test_brier_range(self, separable_data):
        X, y = separable_data
        result = train_and_evaluate(X, y)
        assert 0.0 <= result.brier_mean <= 1.0

    def test_with_pca(self, separable_data):
        X, y = separable_data
        result = train_and_evaluate(X, y, pca_components=10)
        assert result.auroc_mean > 0.8


class TestLeaveScenarioOut:
    def test_correct_fold_count(self, separable_data):
        X, y = separable_data
        scenario_ids = np.repeat(np.arange(25), 4)
        result = train_and_evaluate_leave_scenario_out(X, y, scenario_ids)
        assert len(result.auroc_per_fold) == 25

    def test_separable_reasonable_auroc(self, separable_data):
        X, y = separable_data
        scenario_ids = np.repeat(np.arange(25), 4)
        result = train_and_evaluate_leave_scenario_out(X, y, scenario_ids)
        assert result.auroc_mean > 0.7


class TestDeceptionDirection:
    def test_unit_norm(self, separable_data):
        X, y = separable_data
        direction, norm = compute_deception_direction(X, y)
        assert abs(np.linalg.norm(direction) - 1.0) < 1e-5

    def test_direction_shape(self, separable_data):
        X, y = separable_data
        direction, _ = compute_deception_direction(X, y)
        assert direction.shape == (X.shape[1],)

    def test_norm_positive(self, separable_data):
        _, y = separable_data
        X, _ = separable_data
        _, norm = compute_deception_direction(X, y)
        assert norm > 0


class TestDiffInMeans:
    def test_direction_shape(self, separable_data):
        X, y = separable_data
        direction, _ = compute_diff_in_means(X, y)
        assert direction.shape == (X.shape[1],)

    def test_norm_positive_for_separable(self, separable_data):
        X, y = separable_data
        _, norm = compute_diff_in_means(X, y)
        assert norm > 0


class TestEvaluateAllLayers:
    def test_with_dict_input(self, separable_data):
        X, y = separable_data
        activations = {16: X, 20: X, 24: X}
        result = evaluate_all_layers(activations, y)
        assert set(result.layer_results.keys()) == {16, 20, 24}
        assert set(result.deception_directions.keys()) == {16, 20, 24}
        assert set(result.diff_in_means.keys()) == {16, 20, 24}

    def test_leave_scenario_out_mode(self, separable_data):
        X, y = separable_data
        activations = {20: X}
        scenario_ids = np.repeat(np.arange(25), 4)
        meta = {"scenario_idx": scenario_ids}
        result = evaluate_all_layers(activations, y, metadata=meta, leave_scenario_out=True)
        assert 20 in result.layer_results

    def test_raises_without_metadata(self, separable_data):
        X, y = separable_data
        with pytest.raises(ValueError):
            evaluate_all_layers({20: X}, y, leave_scenario_out=True)


class TestResultsSerialization:
    def test_json_compatible(self, separable_data):
        X, y = separable_data
        activations = {16: X, 20: X}
        layer_results = evaluate_all_layers(activations, y)
        d = results_to_dict(layer_results)
        json.dumps(d)

    def test_has_expected_keys(self, separable_data):
        X, y = separable_data
        layer_results = evaluate_all_layers({20: X}, y)
        d = results_to_dict(layer_results)
        assert 20 in d
        assert "auroc_mean" in d[20]
        assert "brier_mean" in d[20]
        assert "ece_mean" in d[20]
        assert "deception_direction_norm" in d[20]
        assert "diff_in_means_norm" in d[20]


class TestLATBaseline:
    def test_lat_direction_probe_scores(self, separable_data):
        X, y = separable_data
        model = LATDirectionProbe().fit(X, y)
        scores = model.decision_function(X)
        probs = model.predict_proba(X)[:, 1]
        assert scores.shape == (len(y),)
        assert probs.shape == (len(y),)
        assert 0.0 <= probs.min() <= probs.max() <= 1.0
        assert abs(np.linalg.norm(model.direction_) - 1.0) < 1e-5

    def test_lat_separable_high_auroc(self, separable_data):
        X, y = separable_data
        result = train_and_evaluate_lat(X, y, n_splits=5)
        assert result.auroc_mean > 0.9

    def test_lat_leave_group_out(self, separable_data):
        X, y = separable_data
        groups = np.repeat(np.arange(25), 4)
        result = train_and_evaluate_lat_leave_group_out(X, y, groups)
        assert len(result.auroc_per_fold) == 25
        assert result.auroc_mean > 0.7

    def test_lat_all_layers_serializes(self, separable_data):
        X, y = separable_data
        result = evaluate_lat_all_layers({16: X, 20: X}, y)
        d = lat_results_to_dict(result)
        json.dumps(d)
        assert 16 in d
        assert "lat_direction_norm" in d[16]


class TestContrastPairLAT:
    @pytest.fixture
    def paired_data(self):
        rng = np.random.RandomState(7)
        n_pairs = 50
        d = 40
        base = rng.randn(n_pairs, d).astype(np.float32)
        signal = np.zeros(d, dtype=np.float32)
        signal[:5] = 2.0
        negative = base - signal / 2
        positive = base + signal / 2
        X = np.stack([negative, positive], axis=1).reshape(n_pairs * 2, d)
        y = np.tile([0, 1], n_pairs)
        pair_ids = np.repeat(np.arange(n_pairs), 2)
        return X, y, pair_ids

    def test_fit_scores_matched_pairs(self, paired_data):
        X, y, pair_ids = paired_data
        model = ContrastPairLATProbe().fit(X, y, pair_ids)
        scores = model.decision_function(X)
        assert scores[y == 1].mean() > scores[y == 0].mean()
        assert np.linalg.norm(model.direction_) == pytest.approx(1.0)

    def test_pair_preserving_cv(self, paired_data):
        X, y, pair_ids = paired_data
        result = train_and_evaluate_contrast_pair_lat(X, y, pair_ids)
        assert len(result.auroc_per_fold) == 5
        assert result.auroc_mean > 0.9

    def test_all_layers_serializes(self, paired_data):
        X, y, pair_ids = paired_data
        result = evaluate_contrast_pair_lat_all_layers(
            {16: X, 20: X},
            y,
            pair_ids,
        )
        payload = lat_results_to_dict(result)
        json.dumps(payload)
        assert set(payload) == {16, 20}

    def test_leave_group_out_preserves_training_pairs(self, paired_data):
        X, y, pair_ids = paired_data
        scenario_ids = np.repeat(np.arange(10), 10)
        result = train_and_evaluate_contrast_pair_lat_leave_group_out(
            X,
            y,
            pair_ids,
            scenario_ids,
        )
        assert len(result.auroc_per_fold) == 10
        assert result.auroc_mean > 0.9

    def test_rejects_unmatched_pair(self, paired_data):
        X, y, pair_ids = paired_data
        with pytest.raises(ValueError, match="exactly one negative"):
            ContrastPairLATProbe().fit(X[:-1], y[:-1], pair_ids[:-1])
