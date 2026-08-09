"""Review controls for the Convex open-access v3 package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.scenario1 import generator


ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "experiments" / "scenario1" / "inputs"
CONVEX_ROOT = INPUTS / "fellow_packages" / "convex_open_access_v3"
CONVEX_REGISTRY_PATH = CONVEX_ROOT / "registry.json"
MACRO_REGISTRY_PATH = (
    INPUTS / "fellow_packages" / "macro" / "registry_gen5000_v2.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _selected_document_metrics(registry_path: Path) -> dict[str, int | float]:
    registry = generator.load_registry(registry_path)
    record = generator.build_record(registry, "2-hop", "clean")
    characters = sum(
        len(document["text"])
        for document in record["document_set"]["documents"]
    )
    tokens = record["retrieval_trace"]["selected_token_count"]
    return {
        "characters": characters,
        "tokens": tokens,
        "characters_per_token": round(characters / tokens, 6),
        "tokens_per_100_characters": round(100 * tokens / characters, 6),
    }


def test_convex_special_token_and_payload_footprint_audit_is_consistent():
    registry = _load_json(CONVEX_REGISTRY_PATH)
    plan = _load_json(
        CONVEX_ROOT
        / "retrieval"
        / "full_corpus_bm25_all_pages_open_access_v3.json"
    )
    preflight = _load_json(
        CONVEX_ROOT
        / "retrieval"
        / "qwen_context_preflight_all_pages_open_access_v3.json"
    )
    audit = _load_json(
        INPUTS / registry["provenance"]["token_footprint_audit"]
    )
    payload = registry["injection"]["wordings"][registry["assigned_wording"]]
    macro_registry = _load_json(MACRO_REGISTRY_PATH)
    macro_payload = macro_registry["injection"]["wordings"][
        macro_registry["assigned_wording"]
    ]

    assert hashlib.sha256(payload.encode()).hexdigest() == (
        audit["payloads"]["convex"]["sha256"]
    )
    assert len(payload) == audit["payloads"]["convex"]["characters"] == 393
    assert audit["payloads"]["convex"]["tokens"] == 71
    assert audit["tokenizer_json_sha256"] == plan["tokenizer"][
        "tokenizer_json_sha256"
    ]
    assert audit["tokenizer_json_sha256"] == preflight["tokenizer_json_sha256"]
    assert audit["special_token_probe"]["embedded_markers"] == {
        "<|im_start|>": 151644,
        "<|im_end|>": 151645,
    }
    assert hashlib.sha256(macro_payload.encode()).hexdigest() == (
        audit["payloads"]["macro"]["sha256"]
    )
    assert len(macro_payload) == audit["payloads"]["macro"]["characters"] == 352
    assert audit["payloads"]["macro"]["tokens"] == 69
    for metrics in audit["payloads"].values():
        assert metrics["characters_per_token"] == round(
            metrics["characters"] / metrics["tokens"],
            6,
        )
        assert metrics["tokens_per_100_characters"] == round(
            100 * metrics["tokens"] / metrics["characters"],
            6,
        )

    counts = {
        (case["treatment"], case["thinking_mode"]): case["input_token_count"]
        for case in preflight["cases"]
    }
    assert counts[("injected", "off")] - counts[("clean", "off")] == 72
    assert counts[("injected", "on")] - counts[("clean", "on")] == 72


@pytest.mark.parametrize(
    ("domain", "registry_path"),
    [
        ("convex", CONVEX_REGISTRY_PATH),
        ("macro", MACRO_REGISTRY_PATH),
    ],
)
def test_selected_document_token_footprint_is_reproducible(
    domain: str,
    registry_path: Path,
):
    registry = _load_json(CONVEX_REGISTRY_PATH)
    audit = _load_json(
        INPUTS / registry["provenance"]["token_footprint_audit"]
    )

    assert _selected_document_metrics(registry_path) == (
        audit["selected_document_context"][domain]
    )


def test_convex_tool_call_dual_review_is_explicitly_fail_closed():
    registry = _load_json(CONVEX_REGISTRY_PATH)
    packet = _load_json(
        ROOT / registry["provenance"]["tool_call_dual_review_packet"]
    )
    empty_fields = ("reviewer_id", "label", "rationale", "completed_at")

    assert packet["status"] == "pending_two_independent_human_reviews"
    assert len(packet["review_slots"]) == 2
    assert all(
        all(slot[field] is None for field in empty_fields)
        for slot in packet["review_slots"]
    )
    assert packet["adjudication"]["required_if_labels_disagree"] is True
    assert packet["adjudication"]["final_label"] is None
    assert {
        (
            case["treatment"],
            case["thinking_mode"],
            case["observed_destination"],
        )
        for case in packet["priority_cases"]
    } == {
        ("clean", "on", "research_summaries"),
        ("injected", "on", "knowledge_base"),
    }
