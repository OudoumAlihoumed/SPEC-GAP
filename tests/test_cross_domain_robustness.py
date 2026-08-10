"""Tests for the nine-domain construction-signal robustness helpers."""

from __future__ import annotations

import numpy as np
import pytest

from src.analysis.cross_domain_robustness import (
    paired_domain_score_deltas,
    refit_within_fold_permutation_null,
    summarize_held_out_scores,
)


def _score_rows() -> list[dict]:
    rows = []
    values = {
        "alpha": {"2-hop": (0.1, 0.7), "3-hop": (0.2, 0.8)},
        "beta": {"2-hop": (0.6, 0.4), "3-hop": (0.7, 0.5)},
    }
    for domain, depths in values.items():
        for depth, (clean, injected) in depths.items():
            for condition, score, label in (
                ("clean", clean, 0),
                ("injected", injected, 1),
            ):
                rows.append(
                    {
                        "domain_id": domain,
                        "held_out_match_group_id": domain,
                        "hop_mode": depth,
                        "condition": condition,
                        "trajectory_id": f"{domain}__{depth}__{condition}",
                        "label": label,
                        "score": score,
                    }
                )
    return rows


def test_score_summary_equal_weights_held_out_domains():
    summary = summarize_held_out_scores(_score_rows())

    assert summary["n_predictions"] == 8
    assert summary["n_folds"] == 2
    assert summary["mean_fold_auroc"] == 0.5
    assert [row["auroc"] for row in summary["folds"]] == [1.0, 0.0]


def test_paired_deltas_keep_both_depths_visible():
    rows = paired_domain_score_deltas(_score_rows())
    alpha = next(row for row in rows if row["domain_id"] == "alpha")
    beta = next(row for row in rows if row["domain_id"] == "beta")

    assert alpha["mean_injected_minus_clean"] == pytest.approx(0.6)
    assert [row["delegation_depth"] for row in alpha["pairs"]] == [
        "2-hop",
        "3-hop",
    ]
    assert beta["mean_injected_minus_clean"] == pytest.approx(-0.2)


def test_end_to_end_permutation_null_is_deterministic_and_refitted():
    groups = np.repeat(np.asarray(["a", "b", "c"]), 4)
    labels = np.tile(np.asarray([0, 1, 0, 1]), 3)
    group_offsets = np.repeat(np.asarray([0.0, 10.0, 20.0]), 4)
    X = np.column_stack((labels * 3.0 + group_offsets, labels * 2.0))

    first = refit_within_fold_permutation_null(
        X,
        labels,
        groups,
        n_permutations=11,
        random_state=7,
    )
    second = refit_within_fold_permutation_null(
        X,
        labels,
        groups,
        n_permutations=11,
        random_state=7,
    )

    assert first == second
    assert first["observed"]["mean_fold_auroc"] == 1.0
    assert first["observations_per_fold"] == {"a": 4, "b": 4, "c": 4}
    assert len(first["mean_fold_auroc_null"]["null_values"]) == 11
    assert 0.0 < first["mean_fold_auroc_null"]["add_one_p_value"] <= 1.0


def test_residualized_permutation_uses_declared_train_only_transform():
    groups = np.repeat(np.asarray(["a", "b", "c"]), 4)
    labels = np.tile(np.asarray([0, 1, 0, 1]), 3)
    X = np.column_stack((labels * 2.0, np.arange(12, dtype=float)))

    result = refit_within_fold_permutation_null(
        X,
        labels,
        groups,
        n_permutations=3,
        random_state=3,
        activation_preprocessing="train_domain_mean_residualized",
    )

    assert result["activation_preprocessing"] == ("train_domain_mean_residualized")
