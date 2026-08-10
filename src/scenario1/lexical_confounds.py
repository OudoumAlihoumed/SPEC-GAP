"""Deterministic lexical-confound diagnostics for Scenario 1 packages.

The audit compares an injection span with three clean-text views:

* the complete selected carrier chunk that receives the injection;
* a length-matched lexical window immediately before the insertion anchor; and
* the complete selected clean source-chunk text included for Worker1.

URLs and common English function words are removed from the content metrics so
that endpoint syntax and ordinary prose do not masquerade as domain overlap.
The all-token metrics remain available as a sensitivity view.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.scenario1.retrieval import (
    canonical_plan_sha256,
    load_retrieval_plan,
    sha256_text,
    validate_retrieval_plan,
)


LEXICAL_CONFOUND_AUDIT_SCHEMA = "spec_gap.lexical_confound_audit.v1"
LEXICAL_PACKAGE_SNAPSHOT_SCHEMA = "spec_gap.lexical_package_snapshot.v1"

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
_URL_RE = re.compile(r"https?://[^\s<>()\[\]{}\"']+")
_STOPWORDS = frozenset(
    """
    a about above after again against all am an and any are aren't as at be
    because been before being below between both but by can can't cannot could
    couldn't did didn't do does doesn't doing don't down during each few for
    from further had hadn't has hasn't have haven't having he he'd he'll he's
    her here here's hers herself him himself his how how's i i'd i'll i'm i've
    if in into is isn't it it's its itself let's me more most mustn't my myself
    no nor not of off on once only or other ought our ours ourselves out over
    own same shan't she she'd she'll she's should shouldn't so some such than
    that that's the their theirs them themselves then there there's these they
    they'd they'll they're they've this those through to too under until up
    very was wasn't we we'd we'll we're we've were weren't what what's when
    when's where where's which while who who's whom why why's with won't would
    wouldn't you you'd you'll you're you've your yours yourself yourselves
    """.split()
)


@dataclass(frozen=True)
class LexicalPackage:
    """Validated clean and injected lexical views for one Scenario 1 domain."""

    domain_id: str
    registry_path: str
    registry_sha256: str
    retrieval_plan_path: str
    retrieval_plan_sha256: str
    provenance_status: str | None
    readiness_blockers: tuple[str, ...]
    carrier_chunk_id: str
    carrier_chunk_token_count: int
    carrier_chunk_text_sha256: str
    injection_payload_sha256: str
    selected_chunk_count: int
    injection_text: str
    carrier_text: str
    selected_context_text: str
    source_snapshot_path: str | None = None
    source_snapshot_sha256: str | None = None
    source_commit: str | None = None
    source_documents: tuple[dict[str, str], ...] = ()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _display_path(path: Path, project_root: Path | None) -> str:
    resolved = path.resolve()
    if project_root is not None:
        try:
            return resolved.relative_to(project_root.resolve()).as_posix()
        except ValueError:
            pass
    return resolved.as_posix()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def lexical_terms(text: str, *, content_only: bool = False) -> list[str]:
    """Return case-folded lexical terms after redacting URL values."""

    without_urls = _URL_RE.sub(" ", text)
    terms = [match.group(0).lower() for match in _WORD_RE.finditer(without_urls)]
    if content_only:
        return [term for term in terms if term not in _STOPWORDS]
    return terms


def _load_documents(
    registry: dict[str, Any],
    *,
    inputs_root: Path,
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    resolved_inputs = inputs_root.resolve()
    slots = registry.get("document_slots")
    if not isinstance(slots, list) or not slots:
        raise ValueError("registry document_slots must be a non-empty list")

    for slot in slots:
        if not isinstance(slot, dict):
            raise ValueError("registry document slots must be objects")
        source_file = slot.get("file")
        if not isinstance(source_file, str) or not source_file:
            raise ValueError(f"{slot.get('doc_id')} must use a tracked text file")
        source_path = (resolved_inputs / source_file).resolve()
        if not source_path.is_relative_to(resolved_inputs):
            raise ValueError(f"{slot.get('doc_id')} escapes the inputs root")
        text = source_path.read_text(encoding="utf-8")
        document = {
            "doc_id": slot.get("doc_id"),
            "title": slot.get("title"),
            "role": slot.get("role"),
            "text": text,
        }
        for field in ("source_pdf", "clean_source_pdf", "injected_source_pdf"):
            if isinstance(slot.get(field), str):
                document[field] = slot[field]
        documents.append(document)
    return documents


def load_lexical_package(
    registry_path: str | Path,
    retrieval_plan_path: str | Path,
    *,
    inputs_root: str | Path,
    project_root: str | Path | None = None,
) -> LexicalPackage:
    """Load and validate the exact clean carrier and selected-context views."""

    registry_path = Path(registry_path)
    retrieval_plan_path = Path(retrieval_plan_path)
    inputs_root = Path(inputs_root)
    root = Path(project_root) if project_root is not None else None

    registry = _read_json(registry_path)
    plan = load_retrieval_plan(retrieval_plan_path)
    assigned_wording = registry.get("assigned_wording")
    wordings = registry.get("injection", {}).get("wordings", {})
    injection_text = wordings.get(assigned_wording)
    if not isinstance(injection_text, str) or not injection_text.strip():
        raise ValueError("registry has no non-empty assigned injection wording")

    documents = _load_documents(registry, inputs_root=inputs_root)
    validate_retrieval_plan(
        plan,
        documents,
        injection_payload=injection_text,
    )
    documents_by_id = {document["doc_id"]: document for document in documents}
    candidates_by_id = {
        candidate["chunk_id"]: candidate
        for candidate in plan["candidate_chunks"]
    }
    mapping = plan["injection_mapping"]
    carrier_chunk_id = mapping["selected_carrier_chunk_id"]
    carrier_chunk = candidates_by_id[carrier_chunk_id]
    carrier_document = documents_by_id[mapping["carrier_doc_id"]]
    carrier_text = carrier_document["text"][
        carrier_chunk["source_char_start"] : carrier_chunk["source_char_end"]
    ]
    if mapping["insertion_offset_in_chunk"] != len(carrier_text):
        raise ValueError(
            "lexical comparison requires an insertion at the end of the "
            "selected clean carrier chunk"
        )

    selected_context_parts = []
    for chunk_id in plan["selection"]["render_order_chunk_ids"]:
        candidate = candidates_by_id[chunk_id]
        document_text = documents_by_id[candidate["doc_id"]]["text"]
        selected_context_parts.append(
            document_text[
                candidate["source_char_start"] : candidate["source_char_end"]
            ]
        )
    provenance = registry.get("provenance", {})
    raw_blockers = provenance.get("readiness_blockers", [])
    readiness_blockers = tuple(
        blocker for blocker in raw_blockers if isinstance(blocker, str)
    )
    raw_source_documents = provenance.get("source_documents", [])
    source_documents = tuple(
        {
            field: value
            for field in ("doc_id", "source_url", "doi", "license")
            if isinstance((value := item.get(field)), str)
        }
        for item in raw_source_documents
        if isinstance(item, dict)
    )

    domain_id = registry.get("domain_id")
    if not isinstance(domain_id, str) or not domain_id:
        raise ValueError("registry has no domain_id")
    return LexicalPackage(
        domain_id=domain_id,
        registry_path=_display_path(registry_path, root),
        registry_sha256=_file_sha256(registry_path),
        retrieval_plan_path=_display_path(retrieval_plan_path, root),
        retrieval_plan_sha256=canonical_plan_sha256(plan),
        provenance_status=(
            provenance.get("status")
            if isinstance(provenance.get("status"), str)
            else None
        ),
        readiness_blockers=readiness_blockers,
        carrier_chunk_id=carrier_chunk_id,
        carrier_chunk_token_count=carrier_chunk["token_count"],
        carrier_chunk_text_sha256=sha256_text(carrier_text),
        injection_payload_sha256=sha256_text(injection_text),
        selected_chunk_count=plan["selection"]["selected_chunk_count"],
        injection_text=injection_text,
        carrier_text=carrier_text,
        selected_context_text="\n".join(selected_context_parts),
        source_documents=source_documents,
    )


def build_lexical_package_snapshot(
    package: LexicalPackage,
    *,
    source_commit: str,
) -> dict[str, Any]:
    """Serialize the exact validated text views needed by the lexical audit."""

    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise ValueError("source_commit must be a full lowercase Git SHA")
    return {
        "schema_version": LEXICAL_PACKAGE_SNAPSHOT_SCHEMA,
        "source_commit": source_commit,
        "package": {
            "domain_id": package.domain_id,
            "registry_path": package.registry_path,
            "registry_sha256": package.registry_sha256,
            "retrieval_plan_path": package.retrieval_plan_path,
            "retrieval_plan_sha256": package.retrieval_plan_sha256,
            "provenance_status": package.provenance_status,
            "readiness_blockers": list(package.readiness_blockers),
            "carrier_chunk_id": package.carrier_chunk_id,
            "carrier_chunk_token_count": package.carrier_chunk_token_count,
            "carrier_chunk_text_sha256": package.carrier_chunk_text_sha256,
            "injection_payload_sha256": package.injection_payload_sha256,
            "selected_chunk_count": package.selected_chunk_count,
            "selected_context_text_sha256": sha256_text(
                package.selected_context_text
            ),
            "source_documents": list(package.source_documents),
            "injection_text": package.injection_text,
            "carrier_text": package.carrier_text,
            "selected_context_text": package.selected_context_text,
        },
    }


def _package_from_snapshot_data(
    snapshot: dict[str, Any],
    *,
    snapshot_path: Path | None,
    project_root: Path | None,
) -> LexicalPackage:
    if snapshot.get("schema_version") != LEXICAL_PACKAGE_SNAPSHOT_SCHEMA:
        raise ValueError("unsupported lexical-package snapshot schema")
    source_commit = snapshot.get("source_commit")
    if not isinstance(source_commit, str) or re.fullmatch(
        r"[0-9a-f]{40}", source_commit
    ) is None:
        raise ValueError("snapshot source_commit must be a full lowercase Git SHA")
    data = snapshot.get("package")
    if not isinstance(data, dict):
        raise ValueError("snapshot package must be an object")

    required_strings = (
        "domain_id",
        "registry_path",
        "registry_sha256",
        "retrieval_plan_path",
        "retrieval_plan_sha256",
        "carrier_chunk_id",
        "carrier_chunk_text_sha256",
        "injection_payload_sha256",
        "selected_context_text_sha256",
        "injection_text",
        "carrier_text",
        "selected_context_text",
    )
    for field in required_strings:
        if not isinstance(data.get(field), str) or not data[field]:
            raise ValueError(f"snapshot package field {field} must be non-empty")
    for field in (
        "registry_sha256",
        "retrieval_plan_sha256",
        "carrier_chunk_text_sha256",
        "injection_payload_sha256",
        "selected_context_text_sha256",
    ):
        if re.fullmatch(r"[0-9a-f]{64}", data[field]) is None:
            raise ValueError(f"snapshot package field {field} is not SHA-256")
    for field in ("carrier_chunk_token_count", "selected_chunk_count"):
        if not isinstance(data.get(field), int) or data[field] <= 0:
            raise ValueError(f"snapshot package field {field} must be positive")
    blockers = data.get("readiness_blockers")
    if not isinstance(blockers, list) or not all(
        isinstance(item, str) for item in blockers
    ):
        raise ValueError("snapshot readiness_blockers must be strings")
    source_documents = data.get("source_documents")
    if not isinstance(source_documents, list) or not source_documents:
        raise ValueError("snapshot source_documents must be a non-empty list")
    for document in source_documents:
        if not isinstance(document, dict) or not all(
            isinstance(document.get(field), str) and document[field]
            for field in ("doc_id", "source_url", "license")
        ):
            raise ValueError(
                "snapshot source documents require IDs, URLs, and licenses"
            )
    provenance_status = data.get("provenance_status")
    if provenance_status is not None and not isinstance(provenance_status, str):
        raise ValueError("snapshot provenance_status must be text or null")

    text_hashes = {
        "carrier_text": "carrier_chunk_text_sha256",
        "injection_text": "injection_payload_sha256",
        "selected_context_text": "selected_context_text_sha256",
    }
    for text_field, hash_field in text_hashes.items():
        if sha256_text(data[text_field]) != data[hash_field]:
            raise ValueError(f"snapshot {text_field} no longer matches its hash")

    return LexicalPackage(
        domain_id=data["domain_id"],
        registry_path=data["registry_path"],
        registry_sha256=data["registry_sha256"],
        retrieval_plan_path=data["retrieval_plan_path"],
        retrieval_plan_sha256=data["retrieval_plan_sha256"],
        provenance_status=provenance_status,
        readiness_blockers=tuple(blockers),
        carrier_chunk_id=data["carrier_chunk_id"],
        carrier_chunk_token_count=data["carrier_chunk_token_count"],
        carrier_chunk_text_sha256=data["carrier_chunk_text_sha256"],
        injection_payload_sha256=data["injection_payload_sha256"],
        selected_chunk_count=data["selected_chunk_count"],
        injection_text=data["injection_text"],
        carrier_text=data["carrier_text"],
        selected_context_text=data["selected_context_text"],
        source_snapshot_path=(
            _display_path(snapshot_path, project_root)
            if snapshot_path is not None
            else None
        ),
        source_snapshot_sha256=(
            _file_sha256(snapshot_path) if snapshot_path is not None else None
        ),
        source_commit=source_commit,
        source_documents=tuple(dict(document) for document in source_documents),
    )


def load_lexical_package_snapshot(
    snapshot_path: str | Path,
    *,
    project_root: str | Path | None = None,
) -> LexicalPackage:
    """Load a hash-checked, self-contained lexical reference snapshot."""

    path = Path(snapshot_path)
    root = Path(project_root) if project_root is not None else None
    snapshot = _read_json(path)
    snapshot.pop("_file_info", None)
    return _package_from_snapshot_data(
        snapshot,
        snapshot_path=path,
        project_root=root,
    )


def canonical_package_snapshot_json(snapshot: dict[str, Any]) -> str:
    """Return stable JSON after validating every embedded text hash."""

    _package_from_snapshot_data(
        snapshot,
        snapshot_path=None,
        project_root=None,
    )
    return json.dumps(snapshot, indent=2, sort_keys=True) + "\n"


def _overlap_metrics(
    injection_terms: list[str],
    clean_terms: list[str],
) -> dict[str, Any]:
    if not injection_terms:
        raise ValueError("injection span has no terms under the selected policy")
    if not clean_terms:
        raise ValueError("clean comparison text has no terms under the policy")
    injection_types = set(injection_terms)
    clean_types = set(clean_terms)
    matched_types = sorted(injection_types & clean_types)
    occurrence_matches = sum(term in clean_types for term in injection_terms)
    injection_counts = Counter(injection_terms)
    clean_counts = Counter(clean_terms)
    dot_product = sum(
        frequency * clean_counts[term]
        for term, frequency in injection_counts.items()
    )
    injection_norm = math.sqrt(
        sum(frequency**2 for frequency in injection_counts.values())
    )
    clean_norm = math.sqrt(
        sum(frequency**2 for frequency in clean_counts.values())
    )
    return {
        "clean_term_count": len(clean_terms),
        "clean_unique_term_count": len(clean_types),
        "injection_term_count": len(injection_terms),
        "injection_unique_term_count": len(injection_types),
        "matched_injection_term_occurrences": occurrence_matches,
        "matched_injection_unique_terms": len(matched_types),
        "occurrence_overlap_fraction": occurrence_matches / len(injection_terms),
        "unique_term_overlap_fraction": len(matched_types) / len(injection_types),
        "term_frequency_cosine_similarity": (
            dot_product / (injection_norm * clean_norm)
        ),
        "matched_terms": matched_types,
    }


def _view_metrics(
    package: LexicalPackage,
    *,
    matched_window_terms: int,
) -> dict[str, Any]:
    injection_all = lexical_terms(package.injection_text)
    injection_content = lexical_terms(package.injection_text, content_only=True)
    carrier_all = lexical_terms(package.carrier_text)
    carrier_content = lexical_terms(package.carrier_text, content_only=True)
    context_all = lexical_terms(package.selected_context_text)
    context_content = lexical_terms(
        package.selected_context_text,
        content_only=True,
    )
    if len(carrier_all) < matched_window_terms:
        raise ValueError(
            f"{package.domain_id} carrier has fewer terms than the matched window"
        )
    matched_window_all = carrier_all[-matched_window_terms:]
    matched_window_content = [
        term for term in matched_window_all if term not in _STOPWORDS
    ]
    inputs = {
        "registry": package.registry_path,
        "registry_sha256": package.registry_sha256,
        "retrieval_plan": package.retrieval_plan_path,
        "retrieval_plan_sha256": package.retrieval_plan_sha256,
        "provenance_status": package.provenance_status,
        "readiness_blockers": list(package.readiness_blockers),
        "carrier_chunk_id": package.carrier_chunk_id,
        "carrier_chunk_model_token_count": package.carrier_chunk_token_count,
        "carrier_chunk_text_sha256": package.carrier_chunk_text_sha256,
        "injection_payload_sha256": package.injection_payload_sha256,
        "selected_context_text_sha256": sha256_text(
            package.selected_context_text
        ),
        "selected_chunk_count": package.selected_chunk_count,
        "source_documents": list(package.source_documents),
    }
    if package.source_snapshot_path is not None:
        inputs["reference_snapshot"] = package.source_snapshot_path
        inputs["reference_snapshot_sha256"] = package.source_snapshot_sha256
        inputs["source_commit"] = package.source_commit
    return {
        "domain_id": package.domain_id,
        "inputs": inputs,
        "all_lexical_terms": {
            "full_carrier_chunk": _overlap_metrics(
                injection_all,
                carrier_all,
            ),
            "matched_pre_anchor_window": _overlap_metrics(
                injection_all,
                matched_window_all,
            ),
            "full_selected_clean_context": _overlap_metrics(
                injection_all,
                context_all,
            ),
        },
        "content_lexical_terms": {
            "full_carrier_chunk": _overlap_metrics(
                injection_content,
                carrier_content,
            ),
            "matched_pre_anchor_window": _overlap_metrics(
                injection_content,
                matched_window_content,
            ),
            "full_selected_clean_context": _overlap_metrics(
                injection_content,
                context_content,
            ),
        },
    }


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _comparison(
    focus: dict[str, Any],
    reference: dict[str, Any],
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for view_name in (
        "full_carrier_chunk",
        "matched_pre_anchor_window",
        "full_selected_clean_context",
    ):
        focus_view = focus["content_lexical_terms"][view_name]
        reference_view = reference["content_lexical_terms"][view_name]
        focus_overlap = focus_view["unique_term_overlap_fraction"]
        reference_overlap = reference_view["unique_term_overlap_fraction"]
        metrics[view_name] = {
            "focus_unique_term_overlap_fraction": focus_overlap,
            "reference_unique_term_overlap_fraction": reference_overlap,
            "difference": focus_overlap - reference_overlap,
            "ratio": _ratio(focus_overlap, reference_overlap),
            "focus_tf_cosine_similarity": focus_view[
                "term_frequency_cosine_similarity"
            ],
            "reference_tf_cosine_similarity": reference_view[
                "term_frequency_cosine_similarity"
            ],
        }
    return metrics


def build_lexical_confound_audit(
    focus: LexicalPackage,
    reference: LexicalPackage,
) -> dict[str, Any]:
    """Build a descriptive, hash-bound lexical comparison for two domains."""

    if focus.domain_id == reference.domain_id:
        raise ValueError("focus and reference domains must differ")
    carrier_lengths = {
        package.domain_id: len(lexical_terms(package.carrier_text))
        for package in (focus, reference)
    }
    matched_window_terms = min(carrier_lengths.values())
    focus_metrics = _view_metrics(
        focus,
        matched_window_terms=matched_window_terms,
    )
    reference_metrics = _view_metrics(
        reference,
        matched_window_terms=matched_window_terms,
    )
    stopword_sha256 = sha256_text("\n".join(sorted(_STOPWORDS)))
    return {
        "schema_version": LEXICAL_CONFOUND_AUDIT_SCHEMA,
        "focus_domain": focus.domain_id,
        "reference_domain": reference.domain_id,
        "method": {
            "purpose": (
                "descriptive sensitivity audit for lexical overlap between "
                "the injected wording and clean text visible to Worker1"
            ),
            "tokenization": (
                "case-folded regex lexical terms; URLs redacted before "
                "tokenization"
            ),
            "term_pattern": _WORD_RE.pattern,
            "content_policy": "remove fixed common-English stopword list",
            "stopword_count": len(_STOPWORDS),
            "stopword_sha256": stopword_sha256,
            "matched_window_policy": (
                "take the final N lexical terms before the insertion anchor, "
                "where N is the smaller complete carrier-chunk term count"
            ),
            "matched_window_terms": matched_window_terms,
            "descriptive_only": True,
            "injection_spans_per_domain": 1,
        },
        "domains": {
            focus.domain_id: focus_metrics,
            reference.domain_id: reference_metrics,
        },
        "comparison": _comparison(focus_metrics, reference_metrics),
    }


def _format_percent(value: float) -> str:
    return f"{100.0 * value:.2f}%"


def _format_ratio(value: float | None) -> str:
    return "undefined" if value is None else f"{value:.2f}x"


def _domain_label(domain_id: str) -> str:
    return {"fin": "Finance", "convex": "Convex"}.get(
        domain_id,
        domain_id,
    )


def render_lexical_confound_markdown(audit: dict[str, Any]) -> str:
    """Render the audit's measured values without inferring significance."""

    if audit.get("schema_version") != LEXICAL_CONFOUND_AUDIT_SCHEMA:
        raise ValueError("unsupported lexical-confound audit schema")
    focus = audit["focus_domain"]
    reference = audit["reference_domain"]
    focus_label = _domain_label(focus)
    reference_label = _domain_label(reference)
    comparison = audit["comparison"]
    domains = audit["domains"]
    labels = (
        ("Complete selected carrier chunk", "full_carrier_chunk"),
        ("Length-matched pre-anchor window", "matched_pre_anchor_window"),
        (
            "Complete selected clean source-chunk context",
            "full_selected_clean_context",
        ),
    )
    rows = []
    for label, key in labels:
        item = comparison[key]
        rows.append(
            f"| {label} | {_format_percent(item['focus_unique_term_overlap_fraction'])} "
            f"| {_format_percent(item['reference_unique_term_overlap_fraction'])} "
            f"| {_format_ratio(item['ratio'])} |"
        )

    focus_carrier = domains[focus]["content_lexical_terms"][
        "full_carrier_chunk"
    ]
    reference_carrier = domains[reference]["content_lexical_terms"][
        "full_carrier_chunk"
    ]
    focus_window = domains[focus]["content_lexical_terms"][
        "matched_pre_anchor_window"
    ]
    reference_window = domains[reference]["content_lexical_terms"][
        "matched_pre_anchor_window"
    ]
    reference_inputs = domains[reference]["inputs"]
    focus_higher = {
        key: comparison[key]["difference"] > 0
        for key in (
            "full_carrier_chunk",
            "matched_pre_anchor_window",
            "full_selected_clean_context",
        )
    }
    if all(focus_higher.values()):
        interpretation = (
            f"`{focus}` has higher overlap in all three clean-text views, "
            "including the equal-length text immediately adjacent to the "
            "insertion anchor. This supports treating both the local carrier "
            "neighborhood and the broader domain context as lexical-confound "
            "sensitivities."
        )
    elif (
        focus_higher["full_carrier_chunk"]
        and focus_higher["full_selected_clean_context"]
        and not focus_higher["matched_pre_anchor_window"]
    ):
        interpretation = (
            f"`{focus}` has higher overlap for the complete carrier chunk "
            "and the complete selected clean source-chunk context. "
            "However, it does not have higher overlap in the equal-length "
            "text immediately adjacent to the insertion anchor. This "
            "supports a domain-level sensitivity but does not establish an "
            "unusually entangled local carrier neighborhood."
        )
    else:
        interpretation = (
            "The direction of overlap differs across clean-text views, so "
            "the audit does not support a single context-independent lexical "
            "ordering."
        )
    blockers = reference_inputs.get("readiness_blockers") or []
    provenance_note = ""
    provenance_status = reference_inputs.get("provenance_status")
    if blockers:
        blocker_text = (
            "; ".join(blocker.rstrip(".") for blocker in blockers)
        )
        provenance_note = (
            "\n## Reference-package status\n\n"
            f"The `{reference}` package status is "
            f"`{provenance_status or 'unspecified'}`. "
            f"Recorded blockers: {blocker_text}. These measurements are a "
            "diagnostic comparison, not a final paper claim, until that "
            "package's provenance is cleared.\n"
        )
    elif provenance_status:
        provenance_note = (
            "\n## Reference-package status\n\n"
            f"The `{reference}` package status is `{provenance_status}` and "
            "records no readiness blockers. The comparison remains "
            "descriptive because each domain contributes one injection "
            "wording, not because reference provenance is pending.\n"
        )
    snapshot_note = ""
    snapshot_command = ""
    if reference_inputs.get("reference_snapshot"):
        snapshot_note = (
            " A committed, hash-checked reference snapshot contains the "
            "exact derived text views needed to reproduce the comparison "
            f"from source commit `{reference_inputs['source_commit']}`."
        )
        focus_inputs = domains[focus]["inputs"]
        snapshot_command = (
            "\nFrom a clean checkout, rebuild both committed outputs with:\n\n"
            "```bash\n"
            "python scripts/01_scenario_construction/"
            "05_audit_lexical_confounds.py \\\n"
            f"  --focus-registry {focus_inputs['registry']} \\\n"
            f"  --focus-plan {focus_inputs['retrieval_plan']} \\\n"
            "  --reference-snapshot "
            f"{reference_inputs['reference_snapshot']} \\\n"
            "  --out-json results/scenario1/"
            "2026-08-07_finance_convex_lexical_confound_audit.json \\\n"
            "  --out-markdown results/scenario1/"
            "2026-08-07_finance_convex_lexical_confound_audit.md\n"
            "```\n"
        )

    return (
        f"# {focus_label} versus {reference_label} lexical-confound audit\n\n"
        "This audit responds to the PR #26 request to measure whether the "
        "Finance injection is lexically entangled with clean carrier text. "
        "URLs are removed and the primary comparison excludes fixed English "
        "stopwords.\n\n"
        "## Content-term overlap\n\n"
        f"The value is the fraction of unique injection content terms also "
        f"present in the clean comparison text. The matched window uses the "
        f"nearest {audit['method']['matched_window_terms']} lexical terms "
        "before each insertion anchor.\n\n"
        f"| Clean comparison | `{focus}` | `{reference}` | "
        f"`{focus}` / `{reference}` |\n"
        "| --- | ---: | ---: | ---: |\n"
        + "\n".join(rows)
        + "\n\n"
        "## Matched terms\n\n"
        f"- `{focus}` complete carrier: "
        f"{', '.join(focus_carrier['matched_terms']) or 'none'}\n"
        f"- `{reference}` complete carrier: "
        f"{', '.join(reference_carrier['matched_terms']) or 'none'}\n"
        f"- `{focus}` matched window: "
        f"{', '.join(focus_window['matched_terms']) or 'none'}\n"
        f"- `{reference}` matched window: "
        f"{', '.join(reference_window['matched_terms']) or 'none'}\n\n"
        "## Interpretation\n\n"
        f"{interpretation} Report the Finance fold separately and avoid "
        "attributing its probe performance solely to malicious-instruction "
        "semantics. PR #35 should carry this as a lexical sensitivity flag "
        "distinct from the chat-template issue.\n"
        "\nThe audit is descriptive: each domain contributes one injection "
        "wording, so no inferential significance claim is made.\n"
        + provenance_note
        + "\n## Reproducibility\n\n"
        "The companion JSON records the registry, retrieval-plan, carrier-"
        "chunk, injection, and selected-context hashes; source retrieval "
        "plans are validated against their clean source slices before "
        f"metrics are computed.{snapshot_note}\n"
        + snapshot_command
    )


def validate_audit_numbers(audit: dict[str, Any]) -> None:
    """Reject non-finite or out-of-range metrics in a serialized audit."""

    if audit.get("schema_version") != LEXICAL_CONFOUND_AUDIT_SCHEMA:
        raise ValueError("unsupported lexical-confound audit schema")
    domains = audit.get("domains")
    if not isinstance(domains, dict) or set(domains) != {
        audit.get("focus_domain"),
        audit.get("reference_domain"),
    }:
        raise ValueError("lexical-confound audit domains are inconsistent")
    for domain in domains.values():
        for policy in ("all_lexical_terms", "content_lexical_terms"):
            for view in domain[policy].values():
                for field in (
                    "occurrence_overlap_fraction",
                    "unique_term_overlap_fraction",
                    "term_frequency_cosine_similarity",
                ):
                    value = view[field]
                    if (
                        not isinstance(value, (int, float))
                        or isinstance(value, bool)
                        or not math.isfinite(value)
                        or not 0.0 <= value <= 1.0
                    ):
                        raise ValueError(f"invalid lexical metric {field}")


def canonical_audit_json(audit: dict[str, Any]) -> str:
    """Return the stable, human-readable JSON serialization used in results."""

    validate_audit_numbers(audit)
    return json.dumps(audit, indent=2, sort_keys=True) + "\n"


def audit_input_files(packages: Iterable[LexicalPackage]) -> set[str]:
    """Return the registry and plan paths bound into an audit."""

    return {
        path
        for package in packages
        for path in (package.registry_path, package.retrieval_plan_path)
    }
