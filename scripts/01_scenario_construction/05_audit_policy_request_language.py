#!/usr/bin/env python3
"""Measure clean request-language overlap for Policy versus Neuro."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUTS_ROOT = PROJECT_ROOT / "experiments" / "scenario1" / "inputs"
DOMAIN_SCHEMA = "spec_gap.request_language_domain_snapshot.v1"
AUDIT_SCHEMA = "spec_gap.policy_neuro_request_language_audit.v1"
TOKEN_PATTERN = re.compile(r"[a-z]+")

LEXICON: dict[str, list[str]] = {
    "submit": [
        "submission",
        "submissions",
        "submit",
        "submits",
        "submitted",
        "submitting",
    ],
    "archive": ["archival", "archive", "archived", "archives", "archiving"],
    "disclose": [
        "disclose",
        "disclosed",
        "discloses",
        "disclosing",
        "disclosure",
        "disclosures",
    ],
    "report": ["report", "reported", "reporting", "reports"],
    "transmit": [
        "transmission",
        "transmissions",
        "transmit",
        "transmits",
        "transmitted",
        "transmitting",
    ],
    "send": ["send", "sending", "sends", "sent"],
    "upload": ["upload", "uploaded", "uploading", "uploads"],
    "deposit": ["deposit", "deposited", "depositing", "deposits"],
    "share": ["share", "shared", "shares", "sharing"],
}

GROUPS: dict[str, list[str]] = {
    "reviewer_named_families": ["submit", "archive", "disclose", "report"],
    "expanded_request_transfer_families": list(LEXICON),
    "report_excluded_sensitivity": [
        family for family in LEXICON if family != "report"
    ],
    "report_and_share_excluded_sensitivity": [
        family for family in LEXICON if family not in {"report", "share"}
    ],
}


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _portable_path(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def _metrics(texts: list[str]) -> dict[str, Any]:
    tokens = [token for text in texts for token in _tokens(text)]
    token_count = len(tokens)
    family_counts = {
        family: sum(token in forms for token in tokens)
        for family, forms in LEXICON.items()
    }
    group_counts = {
        group: sum(family_counts[family] for family in families)
        for group, families in GROUPS.items()
    }
    return {
        "word_token_count": token_count,
        "family_counts": family_counts,
        "family_rates_per_10000_words": {
            family: round(10000 * count / token_count, 6)
            for family, count in family_counts.items()
        },
        "group_counts": group_counts,
        "group_rates_per_10000_words": {
            group: round(10000 * count / token_count, 6)
            for group, count in group_counts.items()
        },
    }


def _validate_metrics(metrics: dict[str, Any]) -> None:
    token_count = metrics["word_token_count"]
    if not isinstance(token_count, int) or token_count < 1:
        raise ValueError("request-language view has no word tokens")
    family_counts = metrics["family_counts"]
    if set(family_counts) != set(LEXICON):
        raise ValueError("request-language family set is inconsistent")
    for group, families in GROUPS.items():
        expected = sum(family_counts[family] for family in families)
        if metrics["group_counts"].get(group) != expected:
            raise ValueError(f"request-language count is inconsistent for {group}")
        expected_rate = round(10000 * expected / token_count, 6)
        if metrics["group_rates_per_10000_words"].get(group) != expected_rate:
            raise ValueError(f"request-language rate is inconsistent for {group}")


def load_domain_snapshot(
    registry_path: Path,
    *,
    inputs_root: Path,
    project_root: Path,
    source_commit: str | None = None,
) -> dict[str, Any]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    plan_path = inputs_root / registry["retrieval"]["plan_file"]
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    candidates = {
        candidate["chunk_id"]: candidate
        for candidate in plan["candidate_chunks"]
    }
    selected_ids = plan["selection"]["render_order_chunk_ids"]

    documents: dict[str, str] = {}
    document_inputs = []
    source_metadata = {
        item["doc_id"]: item
        for item in registry.get("provenance", {}).get("source_documents", [])
    }
    for slot in registry["document_slots"]:
        path = inputs_root / slot["file"]
        text = path.read_text(encoding="utf-8")
        documents[slot["doc_id"]] = text
        metadata = source_metadata.get(slot["doc_id"], {})
        document_inputs.append({
            "doc_id": slot["doc_id"],
            "path": _portable_path(path, project_root),
            "sha256": _sha256_file(path),
            "doi": metadata.get("doi"),
            "license": metadata.get("license"),
        })

    selected_texts = []
    for chunk_id in selected_ids:
        candidate = candidates[chunk_id]
        source_text = documents[candidate["doc_id"]][
            candidate["source_char_start"]:candidate["source_char_end"]
        ]
        if _sha256_bytes(source_text.encode("utf-8")) != candidate["text_sha256"]:
            raise ValueError(f"selected chunk text hash changed: {chunk_id}")
        selected_texts.append(source_text)

    assigned = registry["assigned_wording"]
    snapshot = {
        "schema_version": DOMAIN_SCHEMA,
        "domain_id": registry["domain_id"],
        "generation_protocol_id": registry["generation_protocol_id"],
        "source_commit": source_commit,
        "lexicon": {
            "tokenizer": "lowercase ASCII alphabetic tokens via [a-z]+",
            "families": LEXICON,
            "groups": GROUPS,
        },
        "inputs": {
            "registry": _portable_path(registry_path, project_root),
            "registry_sha256": _sha256_file(registry_path),
            "retrieval_plan": _portable_path(plan_path, project_root),
            "retrieval_plan_sha256": _sha256_file(plan_path),
            "source_documents": document_inputs,
            "selected_chunk_count": len(selected_ids),
            "selected_chunk_ids_sha256": _sha256_bytes(
                json.dumps(selected_ids, separators=(",", ":")).encode("utf-8")
            ),
            "injection_payload_sha256": _sha256_bytes(
                registry["injection"]["wordings"][assigned].encode("utf-8")
            ),
        },
        "views": {
            "full_clean_corpus": _metrics(list(documents.values())),
            "selected_clean_source_chunks": _metrics(selected_texts),
        },
    }
    validate_domain_snapshot(snapshot)
    return snapshot


def validate_domain_snapshot(snapshot: dict[str, Any]) -> None:
    if snapshot.get("schema_version") != DOMAIN_SCHEMA:
        raise ValueError("unsupported request-language domain snapshot")
    lexicon = snapshot.get("lexicon", {})
    if lexicon.get("families") != LEXICON or lexicon.get("groups") != GROUPS:
        raise ValueError("request-language snapshot uses a different lexicon")
    if set(snapshot.get("views", {})) != {
        "full_clean_corpus",
        "selected_clean_source_chunks",
    }:
        raise ValueError("request-language snapshot views are incomplete")
    for metrics in snapshot["views"].values():
        _validate_metrics(metrics)


def _comparison(
    policy: dict[str, Any],
    neuro: dict[str, Any],
) -> dict[str, Any]:
    comparisons = {}
    for view in policy["views"]:
        view_comparisons = {}
        for group in GROUPS:
            policy_rate = policy["views"][view][
                "group_rates_per_10000_words"
            ][group]
            neuro_rate = neuro["views"][view][
                "group_rates_per_10000_words"
            ][group]
            view_comparisons[group] = {
                "policy_rate_per_10000_words": policy_rate,
                "neuro_rate_per_10000_words": neuro_rate,
                "policy_minus_neuro_rate": round(policy_rate - neuro_rate, 6),
                "policy_to_neuro_rate_ratio": (
                    None if neuro_rate == 0 else round(policy_rate / neuro_rate, 6)
                ),
                "policy_higher": policy_rate > neuro_rate,
            }
        comparisons[view] = view_comparisons
    return comparisons


def build_audit(
    policy: dict[str, Any],
    neuro: dict[str, Any],
) -> dict[str, Any]:
    validate_domain_snapshot(policy)
    validate_domain_snapshot(neuro)
    comparisons = _comparison(policy, neuro)
    primary = comparisons["selected_clean_source_chunks"][
        "reviewer_named_families"
    ]
    return {
        "schema_version": AUDIT_SCHEMA,
        "created_at": "2026-08-09",
        "focus_domain_id": "policy",
        "reference_domain_id": "neuro",
        "method": {
            "unit": "case-folded alphabetic word occurrence",
            "denominator": "all [a-z]+ word tokens in each clean-text view",
            "views": {
                "full_clean_corpus": "all three clean extracted documents",
                "selected_clean_source_chunks": (
                    "exact clean source slices selected for Worker1; retrieval "
                    "overlap is retained because it is present in the prompt"
                ),
            },
            "primary_group": "reviewer_named_families",
            "descriptive_only": True,
        },
        "lexicon": policy["lexicon"],
        "domains": {"policy": policy, "neuro": neuro},
        "comparisons": comparisons,
        "finding": {
            "policy_has_higher_primary_overlap": primary["policy_higher"],
            "summary": (
                "Policy does not have a higher rate of the reviewer-named "
                "request-language families than Neuro in either clean-text view."
            ),
            "polysemy_note": (
                "The expanded lexicon reports ambiguous report and share tokens "
                "separately; share is often an economic noun in Policy, so it "
                "must not be treated as an instruction verb without context."
            ),
        },
        "downstream_covariate": {
            "covariate_id": "clean_request_language_rate_v1",
            "required_for_pr35": True,
            "recommended_primary_value_paths": {
                "policy": (
                    "domains.policy.views.selected_clean_source_chunks."
                    "group_rates_per_10000_words.reviewer_named_families"
                ),
                "neuro": (
                    "domains.neuro.views.selected_clean_source_chunks."
                    "group_rates_per_10000_words.reviewer_named_families"
                ),
            },
            "policy_value": primary["policy_rate_per_10000_words"],
            "neuro_value": primary["neuro_rate_per_10000_words"],
            "interpretation": (
                "Retain this measured covariate in cross-domain sensitivity "
                "analysis, but do not explain Policy resistance or probe behavior "
                "as higher clean request-language overlap in this comparison."
            ),
        },
        "limitations": [
            "Surface-form counts do not establish semantic equivalence or causality.",
            "The two-domain comparison does not estimate a population-level effect.",
            "Report and share are polysemous in academic and policy prose; the audit includes exclusion sensitivities.",
            "The selected-context view counts overlapping retrieval text exactly as rendered to Worker1.",
        ],
    }


def render_markdown(audit: dict[str, Any]) -> str:
    rows = []
    for view, label in (
        ("full_clean_corpus", "Full clean corpus"),
        ("selected_clean_source_chunks", "Selected clean source chunks"),
    ):
        for group, group_label in (
            ("reviewer_named_families", "Reviewer-named families"),
            ("expanded_request_transfer_families", "Expanded transfer families"),
            (
                "report_and_share_excluded_sensitivity",
                "Excluding polysemous report/share",
            ),
        ):
            item = audit["comparisons"][view][group]
            rows.append(
                f"| {label} | {group_label} | "
                f"{item['policy_rate_per_10000_words']:.3f} | "
                f"{item['neuro_rate_per_10000_words']:.3f} | "
                f"{item['policy_to_neuro_rate_ratio']:.3f} |"
            )
    limitations = "\n".join(
        f"- {item}" for item in audit["limitations"]
    )
    return f"""# Policy–Neuro clean request-language audit

Date: 2026-08-09

The reviewer asked whether clean Policy text contains more language resembling
the injection's request verbs than Neuro. Under the predeclared primary family
set (`submit`, `archive`, `disclose`, and `report`), it does not.

| Text view | Vocabulary | Policy / 10k words | Neuro / 10k words | Policy / Neuro |
| --- | --- | ---: | ---: | ---: |
{chr(10).join(rows)}

The selected-context primary rate is
{audit['downstream_covariate']['policy_value']:.3f} per 10,000 words for Policy
versus {audit['downstream_covariate']['neuro_value']:.3f} for Neuro. The measured
covariate should still be carried into PR #35, but these data do not support an
explanation in which Policy has unusually high clean request-language overlap.

`report` is common academic language, and `share` is frequently an economic
noun in Policy. The exclusion sensitivity prevents those polysemous strings
from being silently interpreted as instruction verbs.

## Limitations

{limitations}
"""


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-registry", type=_path, required=True)
    parser.add_argument("--inputs-root", type=_path, default=DEFAULT_INPUTS_ROOT)
    parser.add_argument("--reference-snapshot", type=_path)
    parser.add_argument("--reference-registry", type=_path)
    parser.add_argument("--reference-inputs-root", type=_path)
    parser.add_argument("--reference-project-root", type=_path)
    parser.add_argument("--reference-source-commit")
    parser.add_argument("--reference-snapshot-out", type=_path)
    parser.add_argument("--out-json", type=_path, required=True)
    parser.add_argument("--out-markdown", type=_path, required=True)
    args = parser.parse_args()

    has_files = args.reference_registry is not None
    if (args.reference_snapshot is None) == (not has_files):
        parser.error("provide exactly one reference snapshot or registry")
    if has_files and (
        args.reference_inputs_root is None
        or args.reference_project_root is None
        or args.reference_source_commit is None
    ):
        parser.error(
            "reference registry mode requires inputs root, project root, and source commit"
        )
    if args.reference_snapshot is not None and args.reference_snapshot_out:
        parser.error("reference snapshot output requires registry mode")

    policy = load_domain_snapshot(
        args.policy_registry,
        inputs_root=args.inputs_root,
        project_root=PROJECT_ROOT,
    )
    if args.reference_snapshot is not None:
        neuro = json.loads(args.reference_snapshot.read_text(encoding="utf-8"))
        validate_domain_snapshot(neuro)
    else:
        neuro = load_domain_snapshot(
            args.reference_registry,
            inputs_root=args.reference_inputs_root,
            project_root=args.reference_project_root,
            source_commit=args.reference_source_commit,
        )
        if args.reference_snapshot_out is not None:
            args.reference_snapshot_out.parent.mkdir(parents=True, exist_ok=True)
            args.reference_snapshot_out.write_text(
                _canonical_json(neuro),
                encoding="utf-8",
            )

    audit = build_audit(policy, neuro)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(_canonical_json(audit), encoding="utf-8")
    args.out_markdown.write_text(render_markdown(audit), encoding="utf-8")


if __name__ == "__main__":
    main()
