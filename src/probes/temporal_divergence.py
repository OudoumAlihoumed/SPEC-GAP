"""Trajectory-aware Temporal Divergence aggregation.

Temporal Divergence does not train a second representation probe. It aggregates
ordered per-step probabilities from a baseline probe around a predeclared
injection (or matched clean-control) anchor. The signed divergence is the
post-anchor path mean minus the pre-anchor mean. The post-anchor path mean is a
separate probability-valued classifier input; the signed difference is not.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class TemporalDivergenceResult:
    anchor_step_index: int
    n_pre_anchor: int
    n_post_anchor: int
    pre_anchor_mean: float
    post_anchor_mean: float
    divergence_score: float
    peak_shift: float
    persistence_fraction: float

    def to_dict(self) -> dict:
        return asdict(self)


def temporal_divergence(
    step_scores: list[float] | np.ndarray,
    anchor_position: int,
    *,
    persistence_margin: float = 0.0,
) -> TemporalDivergenceResult:
    """Compare the score trajectory before and from the anchor onward.

    `anchor_position` is an array position, not an arbitrary trajectory step
    identifier. Clean controls must use the matched node position from their
    injected pair rather than selecting an anchor after seeing scores.
    """

    scores = np.asarray(step_scores, dtype=float)
    if scores.ndim != 1 or len(scores) < 2:
        raise ValueError("step_scores must be a one-dimensional sequence of length >= 2.")
    if not np.isfinite(scores).all():
        raise ValueError("step_scores must contain only finite values.")
    if np.any((scores < 0.0) | (scores > 1.0)):
        raise ValueError("step_scores must be probabilities in [0, 1].")
    if anchor_position <= 0 or anchor_position >= len(scores):
        raise ValueError("anchor_position must leave at least one pre- and post-anchor step.")
    if persistence_margin < 0.0:
        raise ValueError("persistence_margin must be non-negative.")

    pre = scores[:anchor_position]
    post = scores[anchor_position:]
    pre_mean = float(pre.mean())
    post_mean = float(post.mean())
    return TemporalDivergenceResult(
        anchor_step_index=anchor_position,
        n_pre_anchor=len(pre),
        n_post_anchor=len(post),
        pre_anchor_mean=pre_mean,
        post_anchor_mean=post_mean,
        divergence_score=post_mean - pre_mean,
        peak_shift=float(post.max() - pre_mean),
        persistence_fraction=float(
            np.mean(post > (pre_mean + persistence_margin))
        ),
    )


def score_trajectory_temporal_divergence(
    records: list[dict],
    score_by_step_index: dict[int, float],
    *,
    anchor_step_index: int | None = None,
    persistence_margin: float = 0.0,
) -> TemporalDivergenceResult:
    """Align per-step probe scores to a trajectory and compute divergence."""

    ordered = sorted(
        (
            record for record in records
            if record.get("role") != "guard"
            and not str(record.get("node_id", "")).startswith("__")
        ),
        key=lambda record: record["step_index"],
    )
    if not ordered:
        raise ValueError("No agent steps were found in the trajectory.")

    if anchor_step_index is None:
        injection_steps = [
            record["step_index"] for record in ordered
            if record.get("injection_point")
            or any(
                call.get("tool") == "injection" or call.get("status") == "injected"
                for call in record.get("tool_calls", [])
            )
        ]
        if len(injection_steps) != 1:
            raise ValueError(
                "Injected trajectories must contain exactly one injection step; "
                "clean controls require an explicit matched anchor_step_index."
            )
        anchor_step_index = injection_steps[0]

    missing = [
        record["step_index"] for record in ordered
        if record["step_index"] not in score_by_step_index
    ]
    if missing:
        raise ValueError(f"Missing probe scores for trajectory steps: {missing}")

    ordered_indices = [record["step_index"] for record in ordered]
    if anchor_step_index not in ordered_indices:
        raise ValueError(f"Anchor step {anchor_step_index} is not an agent step.")
    anchor_position = ordered_indices.index(anchor_step_index)
    result = temporal_divergence(
        [score_by_step_index[index] for index in ordered_indices],
        anchor_position,
        persistence_margin=persistence_margin,
    )
    return TemporalDivergenceResult(
        anchor_step_index=anchor_step_index,
        n_pre_anchor=result.n_pre_anchor,
        n_post_anchor=result.n_post_anchor,
        pre_anchor_mean=result.pre_anchor_mean,
        post_anchor_mean=result.post_anchor_mean,
        divergence_score=result.divergence_score,
        peak_shift=result.peak_shift,
        persistence_fraction=result.persistence_fraction,
    )
