"""Review controls for the Petroleum v2 package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "experiments" / "scenario1" / "inputs"
PETRO_ROOT = INPUTS / "fellow_packages" / "petro"
PETRO_REGISTRY_PATH = PETRO_ROOT / "registry_gen5000_v2.json"
AIHC_ROOT = INPUTS / "fellow_packages" / "aihc"
AIHC_REGISTRY_PATH = AIHC_ROOT / "registry.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _injected_thinking_off_case(preflight: dict) -> dict:
    case = next(
        item
        for item in preflight["cases"]
        if item["treatment"] == "injected" and item["thinking_mode"] == "off"
    )
    return case


def test_petroleum_injection_position_covariate_is_internally_consistent():
    registry = _load_json(PETRO_REGISTRY_PATH)
    audit = _load_json(
        INPUTS / registry["provenance"]["injection_position_audit"]
    )
    domains = audit["domains"]

    registry_paths = {
        "petro": PETRO_REGISTRY_PATH,
        "aihc": AIHC_REGISTRY_PATH,
    }
    for domain_id, registry_path in registry_paths.items():
        source = audit["comparison_inputs"][domain_id]
        source_registry_path = INPUTS / source["registry_file"]
        source_preflight_path = INPUTS / source["context_preflight_file"]
        source_preflight = _load_json(source_preflight_path)
        source_case = _injected_thinking_off_case(source_preflight)

        assert source_registry_path == registry_path
        assert _sha256(source_registry_path) == source["registry_sha256"]
        assert _sha256(source_preflight_path) == source["context_preflight_sha256"]
        assert source["source_planner_fixture_tokens"] == (
            source_preflight["planner_fixture"]["token_count"]
        )
        assert source["source_preflight_input_tokens"] == (
            source_case["input_token_count"]
        )
        assert domains[domain_id]["input_tokens"] == (
            source["source_preflight_input_tokens"]
            + audit["planner_fixture"]["token_count"]
            - source["source_planner_fixture_tokens"]
        )

    for metrics in domains.values():
        assert metrics["injection_token_count"] == (
            metrics["injection_end_token"] - metrics["injection_start_token"]
        )
        assert metrics["injection_mid_token"] == (
            metrics["injection_start_token"] + metrics["injection_end_token"]
        ) / 2
        assert metrics["mid_fraction_of_input"] == round(
            metrics["injection_mid_token"] / metrics["input_tokens"],
            9,
        )
        assert metrics["tokens_after_injection"] == (
            metrics["input_tokens"] - metrics["injection_end_token"]
        )
        assert metrics["post_injection_fraction"] == round(
            metrics["tokens_after_injection"] / metrics["input_tokens"],
            9,
        )


def test_petroleum_position_comparison_records_the_observed_direction():
    registry = _load_json(PETRO_REGISTRY_PATH)
    audit = _load_json(
        INPUTS / registry["provenance"]["injection_position_audit"]
    )
    petro = audit["domains"]["petro"]
    aihc = audit["domains"]["aihc"]
    comparison = audit["comparison"]

    assert petro["mid_fraction_of_input"] < aihc["mid_fraction_of_input"]
    assert petro["post_injection_fraction"] > aihc["post_injection_fraction"]
    assert comparison["petro_minus_aihc_mid_fraction"] == round(
        petro["mid_fraction_of_input"] - aihc["mid_fraction_of_input"],
        9,
    )
    assert comparison["petro_minus_aihc_post_fraction"] == round(
        petro["post_injection_fraction"] - aihc["post_injection_fraction"],
        9,
    )


def test_petroleum_tool_call_dual_review_is_explicitly_fail_closed():
    registry = _load_json(PETRO_REGISTRY_PATH)
    packet = _load_json(
        ROOT / registry["provenance"]["tool_call_dual_review_packet"]
    )
    empty_fields = (
        "reviewer_id",
        "label",
        "task_preserved",
        "rationale",
        "completed_at",
    )

    assert packet["status"] == "pending_two_independent_human_reviews"
    assert packet["priority_rank"] == 2
    assert packet["priority_case"]["observed_destination"] == "internal_review"
    assert packet["priority_case"]["ordinary_final_answer_wrapper_present"] is False
    assert packet["priority_case"]["task_comparison_present_in_tool_arguments"] is True
    assert len(packet["review_slots"]) == 2
    assert all(
        all(slot[field] is None for field in empty_fields)
        for slot in packet["review_slots"]
    )
    assert packet["adjudication"]["final_label"] is None
