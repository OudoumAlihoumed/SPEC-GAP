import matplotlib.pyplot as plt

from src.analysis.layer_scan_paper_figures import (
    _control_state,
    _match_groups,
    save_paper_layer_scan_figures,
)


def _paper_result():
    layers = {
        str(layer): {
            "auroc_mean": 0.5,
            "auroc_per_fold": [0.25, 0.75],
        }
        for layer in range(64)
    }
    strata = []
    controls = []
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
        for checkpoint in checkpoints:
            controls.append({
                "thinking_mode": mode,
                "checkpoint": checkpoint,
                "status": (
                    "passed_strict_input_control"
                    if checkpoint == "last_input_token"
                    else "stochastic_null_uncalibrated"
                ),
            })
            for agent_id, role, sample_count in (
                ("planner_1", "planner", 8),
                ("worker_1", "worker", 8),
                ("worker_2", "worker", 4),
                ("executor_1", "executor", 8),
            ):
                strata.append({
                    "status": "completed",
                    "thinking_mode": mode,
                    "agent_id": agent_id,
                    "agent_role": role,
                    "checkpoint": checkpoint,
                    "sample_count": sample_count,
                    "match_group_count": 2,
                    "layer_results": layers,
                })
    return {
        "claim_scope": "Exploratory construction-label signal only.",
        "strata": strata,
        "pre_injection_negative_control": {"checkpoint_controls": controls},
    }


def test_save_paper_figures_in_vector_and_preview_formats(tmp_path):
    paths = save_paper_layer_scan_figures(_paper_result(), tmp_path, dpi=72)

    assert len(paths) == 9
    assert {path.suffix for path in paths} == {".png", ".svg", ".pdf"}
    assert {path.stem for path in paths} == {
        "scenario1_all_domains_planner_negative_control",
        "scenario1_all_domains_shared_input_auroc_by_layer",
        "scenario1_all_domains_checkpoint_qualification_heatmap",
    }
    assert all(path.is_file() and path.stat().st_size > 1000 for path in paths)
    for path in paths:
        if path.suffix == ".svg":
            payload = path.read_text(encoding="utf-8")
            assert all(line == line.rstrip() for line in payload.splitlines())
            assert "<dc:date>" not in payload
        elif path.suffix == ".pdf":
            payload = path.read_bytes()
            assert b"CreationDate" not in payload
            assert b"ModDate" not in payload
    assert plt.get_fignums() == []


def test_control_state_distinguishes_pass_failure_and_uncalibrated_null():
    assert _control_state({"status": "passed_strict_input_control"}) == (
        "PASS",
        True,
        "",
    )
    assert _control_state({"status": "stochastic_null_uncalibrated"}) == (
        "UNCALIBRATED",
        False,
        "Stochastic null not calibrated",
    )
    assert _control_state({"status": "failed_strict_input_control"}) == (
        "FAIL",
        False,
        "Blocked by planner control",
    )


def test_match_groups_uses_names_and_falls_back_to_count():
    named = _paper_result()
    named["strata"][0]["match_groups"] = ["aihc", "fin", "neuro"]
    named["strata"][0]["match_group_count"] = 3
    assert _match_groups(named) == ["aihc", "fin", "neuro"]

    assert _match_groups(_paper_result()) == ["group 1", "group 2"]
