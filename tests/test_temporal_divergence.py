"""Tests for trajectory-aware Temporal Divergence aggregation."""

import pytest

from src.probes.temporal_divergence import (
    score_trajectory_temporal_divergence,
    temporal_divergence,
)


def test_detects_sustained_post_anchor_increase():
    result = temporal_divergence([0.10, 0.15, 0.70, 0.80], anchor_position=2)
    assert result.pre_anchor_mean == pytest.approx(0.125)
    assert result.post_anchor_mean == pytest.approx(0.75)
    assert result.divergence_score == pytest.approx(0.625)
    assert result.persistence_fraction == 1.0


def test_flat_clean_control_has_near_zero_divergence():
    result = temporal_divergence([0.20, 0.22, 0.21, 0.19], anchor_position=2)
    assert result.divergence_score == pytest.approx(-0.01)


def test_rejects_post_hoc_or_invalid_anchor():
    with pytest.raises(ValueError, match="pre- and post-anchor"):
        temporal_divergence([0.1, 0.9], anchor_position=0)
    with pytest.raises(ValueError, match="probabilities"):
        temporal_divergence([0.1, 1.2, 0.9], anchor_position=1)


def test_aligns_scores_to_injection_step():
    records = [
        {"step_index": 0, "node_id": "planner", "role": "planner", "injection_point": None},
        {"step_index": 1, "node_id": "worker", "role": "worker", "injection_point": "retrieval"},
        {"step_index": 2, "node_id": "executor", "role": "executor", "injection_point": None},
    ]
    result = score_trajectory_temporal_divergence(
        records,
        {0: 0.1, 1: 0.6, 2: 0.8},
    )
    assert result.anchor_step_index == 1
    assert result.divergence_score == pytest.approx(0.6)


def test_clean_control_requires_predeclared_matched_anchor():
    records = [
        {"step_index": 0, "node_id": "planner", "role": "planner"},
        {"step_index": 1, "node_id": "worker", "role": "worker"},
        {"step_index": 2, "node_id": "executor", "role": "executor"},
    ]
    with pytest.raises(ValueError, match="clean controls require"):
        score_trajectory_temporal_divergence(
            records,
            {0: 0.1, 1: 0.1, 2: 0.1},
        )
    result = score_trajectory_temporal_divergence(
        records,
        {0: 0.1, 1: 0.1, 2: 0.1},
        anchor_step_index=1,
    )
    assert result.divergence_score == 0.0


def test_missing_step_score_fails_closed():
    records = [
        {"step_index": 0, "node_id": "planner", "role": "planner"},
        {"step_index": 1, "node_id": "worker", "role": "worker", "injection_point": "retrieval"},
        {"step_index": 2, "node_id": "executor", "role": "executor"},
    ]
    with pytest.raises(ValueError, match="Missing probe scores"):
        score_trajectory_temporal_divergence(records, {0: 0.1, 1: 0.4})
