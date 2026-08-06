import matplotlib.pyplot as plt

from src.analysis.layer_scan_figures import (
    _mode_grid,
    save_activation_coverage_status_figure,
    save_layer_scan_figures,
)


def _result():
    layers = {
        str(layer): {
            "auroc_mean": 0.5 + 0.05 * layer,
        }
        for layer in range(3)
    }
    strata = []
    for mode, checkpoints in (
        ("off", ("last_input_token", "last_visible_answer_token")),
        (
            "on",
            (
                "last_input_token",
                "last_reasoning_token",
                "last_visible_answer_token",
            ),
        ),
    ):
        for agent_id, role in (
            ("planner_1", "planner"),
            ("worker_1", "worker"),
            ("worker_2", "worker"),
            ("executor_1", "executor"),
        ):
            for checkpoint in checkpoints:
                strata.append({
                    "status": "completed",
                    "thinking_mode": mode,
                    "agent_id": agent_id,
                    "agent_role": role,
                    "checkpoint": checkpoint,
                    "sample_count": 8,
                    "match_group_count": 2,
                    "layer_results": layers,
                })
    controls = [
        {
            "thinking_mode": mode,
            "checkpoint": checkpoint,
            "status": (
                "failed_spurious_separation"
                if checkpoint == "last_reasoning_token"
                else "passed"
            ),
        }
        for mode, checkpoints in (
            ("off", ("last_input_token", "last_visible_answer_token")),
            (
                "on",
                (
                    "last_input_token",
                    "last_reasoning_token",
                    "last_visible_answer_token",
                ),
            ),
        )
        for checkpoint in checkpoints
    ]
    return {
        "claim_scope": "Exploratory construction-label signal only.",
        "match_groups": ["group-a", "group-b"],
        "strata": strata,
        "pre_injection_negative_control": {"checkpoint_controls": controls},
    }


def test_save_layer_scan_figures(tmp_path):
    paths = save_layer_scan_figures(_result(), tmp_path, dpi=72)

    assert [path.name for path in paths] == [
        "construction_layer_scan_thinking_off.png",
        "construction_layer_scan_thinking_on.png",
        "planner_negative_controls.png",
    ]
    assert all(path.is_file() and path.stat().st_size > 1000 for path in paths)
    assert plt.get_fignums() == []


def test_single_group_figure_uses_preliminary_scope_note():
    result = _result()
    result["match_groups"] = ["aihc"]

    figure = _mode_grid(result, "off")

    assert any(
        text.get_text()
        == (
            "Preliminary AIHC validation only; layer selection deferred "
            "pending additional match groups."
        )
        for text in figure.texts
    )
    plt.close(figure)


def test_save_dated_activation_coverage_status_figure(tmp_path):
    result = _result()
    result["match_groups"] = ["aihc"]
    index_rows = [
        {
            "trajectory_id": f"aihc__{depth.replace('-', '')}__{treatment}",
            "step_index": 0,
            "match_group_id": "aihc",
            "thinking_mode": "off",
            "delegation_depth": depth,
            "treatment": treatment,
            "local_available": True,
            "layers": list(range(64)),
        }
        for depth in ("2-hop", "3-hop")
        for treatment in ("clean", "injected")
    ]

    path = save_activation_coverage_status_figure(
        index_rows,
        result,
        tmp_path,
        as_of_date="2026-07-29",
        dpi=72,
    )

    assert path.name == (
        "2026-07-29_aihc_activation_coverage_and_layer_selection_status.png"
    )
    assert path.is_file() and path.stat().st_size > 1000
    assert plt.get_fignums() == []
