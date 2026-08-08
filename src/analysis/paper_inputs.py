"""Fail-closed protocol selection for paper-facing Scenario 1 analysis.

Historical trajectories intentionally remain in the repository.  This module
keeps those artifacts available for sensitivity work while preventing a
paper-facing pipeline from silently pooling them with a superseding protocol.
"""

from __future__ import annotations

from hashlib import sha256
import itertools
import json
from pathlib import Path
import re
from typing import Any, Iterable

from src.infrastructure.qwen_modal import DEFAULT_GENERATION_PROTOCOL_ID


PAPER_INPUT_POLICY_SCHEMA = "spec_gap.scenario1_paper_input_policy.v1"
PAPER_INPUT_AUDIT_SCHEMA = "spec_gap.scenario1_paper_input_audit.v1"
DEFAULT_PAPER_INPUT_POLICY = "experiments/scenario1/paper_input_policy.json"

_GENERATION_SUFFIX = re.compile(
    r"__gen_(?P<protocol>.+?)__thinking_(?:off|on)$"
)
_PROMPT_SUFFIX = re.compile(
    r"__prompt_(?P<profile>.+?)(?:__gen_.+?)?__thinking_(?:off|on)$"
)
_TREATMENTS = {"clean", "injected"}
_DEPTHS = {"2-hop", "3-hop"}
_THINKING_MODES = {"off", "on"}


def load_paper_input_policy(path: str | Path) -> dict[str, Any]:
    """Load and structurally validate one tracked paper-input policy."""

    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load paper-input policy {source}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("Paper-input policy must contain one JSON object.")
    if payload.get("schema_version") != PAPER_INPUT_POLICY_SCHEMA:
        raise ValueError("Unsupported Scenario 1 paper-input policy schema.")
    _required_string(payload, "policy_id", context="paper-input policy")
    if payload.get("unmanaged_domain_behavior") != "pass_through":
        raise ValueError(
            "Paper-input policy unmanaged_domain_behavior must be 'pass_through'."
        )

    rules = payload.get("domain_protocols")
    if not isinstance(rules, dict) or not rules:
        raise ValueError("Paper-input policy requires non-empty domain_protocols.")
    for domain_id, rule in rules.items():
        if not isinstance(domain_id, str) or not domain_id:
            raise ValueError("Paper-input policy domain IDs must be non-empty strings.")
        if not isinstance(rule, dict):
            raise ValueError(f"Paper-input rule {domain_id!r} must be an object.")
        protocol = _required_string(
            rule,
            "required_generation_protocol_id",
            context=f"paper-input rule {domain_id!r}",
        )
        expected_fragment = f"__gen_{protocol}__"
        fragment = _required_string(
            rule,
            "required_trajectory_id_fragment",
            context=f"paper-input rule {domain_id!r}",
        )
        if fragment != expected_fragment:
            raise ValueError(
                f"Paper-input rule {domain_id!r} must use trajectory fragment "
                f"{expected_fragment!r}."
            )
        _required_string(
            rule,
            "required_agent_prompt_profile_id",
            context=f"paper-input rule {domain_id!r}",
        )
        matrix = rule.get("expected_matrix")
        if not isinstance(matrix, dict):
            raise ValueError(
                f"Paper-input rule {domain_id!r} requires expected_matrix."
            )
        _matrix_values(matrix, "treatments", _TREATMENTS, domain_id)
        _matrix_values(matrix, "delegation_depths", _DEPTHS, domain_id)
        _matrix_values(matrix, "thinking_modes", _THINKING_MODES, domain_id)

        artifacts = rule.get("required_artifacts")
        if not isinstance(artifacts, dict) or not artifacts:
            raise ValueError(
                f"Paper-input rule {domain_id!r} requires artifact provenance."
            )
        for artifact_name, artifact_path in artifacts.items():
            if not isinstance(artifact_name, str) or not artifact_name:
                raise ValueError("Paper-input artifact names must be non-empty strings.")
            if not isinstance(artifact_path, str) or not artifact_path:
                raise ValueError(
                    f"Paper-input artifact {artifact_name!r} must have a path."
                )
    return payload


def select_paper_trajectory_records(
    records: Iterable[dict[str, Any]],
    policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select policy-compliant trajectories while retaining unmanaged domains.

    A managed domain may have historical and definitive records side by side.
    Historical records are excluded, and the selected definitive cohort must
    still contain exactly one trajectory for every declared matrix cell.
    """

    items = [dict(record) for record in records]
    identities = _trajectory_identities(items)
    rules = policy["domain_protocols"]
    selected_ids: set[str] = set()
    excluded_ids: set[str] = set()
    for trajectory_id, identity in identities.items():
        rule = rules.get(identity["domain_id"])
        if rule is None or _matches_rule(identity, rule):
            selected_ids.add(trajectory_id)
        else:
            excluded_ids.add(trajectory_id)

    selected = [item for item in items if item["trajectory_id"] in selected_ids]
    selected_identities = {
        trajectory_id: identity
        for trajectory_id, identity in identities.items()
        if trajectory_id in selected_ids
    }
    _validate_controlled_matrices(
        selected_identities,
        rules,
        observed_domains={identity["domain_id"] for identity in identities.values()},
    )
    audit = _build_audit(
        policy,
        identities=identities,
        selected_identities=selected_identities,
        item_count=len(items),
        selected_item_count=len(selected),
        mode="selection",
    )
    if set(audit["excluded_trajectory_ids"]) != excluded_ids:
        raise AssertionError("Paper-input selection audit is inconsistent.")
    return selected, audit


def validate_paper_analysis_inputs(
    rows: Iterable[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Reject downstream rows that violate a managed domain's protocol rule."""

    items = [dict(row) for row in rows]
    identities = _trajectory_identities(items)
    rules = policy["domain_protocols"]
    violations = [
        trajectory_id
        for trajectory_id, identity in identities.items()
        if identity["domain_id"] in rules
        and not _matches_rule(identity, rules[identity["domain_id"]])
    ]
    if violations:
        raise ValueError(
            "Paper-input policy rejected non-definitive trajectories: "
            f"{sorted(violations)}"
        )
    _validate_controlled_matrices(
        identities,
        rules,
        observed_domains={identity["domain_id"] for identity in identities.values()},
    )
    return _build_audit(
        policy,
        identities=identities,
        selected_identities=identities,
        item_count=len(items),
        selected_item_count=len(items),
        mode="validation",
    )


def validate_embedded_paper_input_audit(
    payload: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Require an aggregate artifact to carry the current policy audit."""

    audit = payload.get("paper_input_selection")
    if not isinstance(audit, dict):
        raise ValueError("Analysis artifact has no paper-input selection audit.")
    if audit.get("schema_version") != PAPER_INPUT_AUDIT_SCHEMA:
        raise ValueError("Analysis artifact has an unsupported paper-input audit.")
    if audit.get("policy_id") != policy["policy_id"]:
        raise ValueError("Analysis artifact used a different paper-input policy.")
    if audit.get("policy_sha256") != paper_input_policy_sha256(policy):
        raise ValueError("Analysis artifact paper-input policy hash is stale.")
    selected_ids = audit.get("selected_trajectory_ids")
    if (
        not isinstance(selected_ids, list)
        or not all(isinstance(item, str) and item for item in selected_ids)
        or selected_ids != sorted(set(selected_ids))
    ):
        raise ValueError("Analysis artifact has invalid selected trajectory IDs.")
    if audit.get("selected_trajectory_sha256") != _trajectory_ids_sha256(
        selected_ids
    ):
        raise ValueError("Analysis artifact selected-trajectory hash is stale.")
    controlled = audit.get("controlled_domains")
    if not isinstance(controlled, dict):
        raise ValueError("Analysis artifact has no controlled-domain audit.")
    for domain_id, rule in policy["domain_protocols"].items():
        entry = controlled.get(domain_id)
        if not isinstance(entry, dict):
            raise ValueError(
                f"Analysis artifact has no paper-input audit for {domain_id!r}."
            )
        if entry.get("status") not in {"complete", "not_present"}:
            raise ValueError(
                f"Analysis artifact has invalid paper-input status for {domain_id!r}."
            )
        if entry.get("required_generation_protocol_id") != rule[
            "required_generation_protocol_id"
        ]:
            raise ValueError(
                f"Analysis artifact has stale protocol metadata for {domain_id!r}."
            )
        selected_protocols = entry.get("selected_generation_protocol_ids")
        expected_protocols = (
            [rule["required_generation_protocol_id"]]
            if entry["status"] == "complete"
            else []
        )
        if selected_protocols != expected_protocols:
            raise ValueError(
                f"Analysis artifact selected the wrong protocol for {domain_id!r}."
            )
    return audit


def paper_input_policy_sha256(policy: dict[str, Any]) -> str:
    """Hash the canonical policy payload for derived-artifact provenance."""

    encoded = json.dumps(
        policy,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _trajectory_identities(
    items: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    identities: dict[str, dict[str, str]] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"Paper-input row {index} must be an object.")
        trajectory_id = _required_string(
            item,
            "trajectory_id",
            context=f"paper-input row {index}",
        )
        identity = {
            "trajectory_id": trajectory_id,
            "domain_id": _required_string(
                item,
                "domain_id",
                context=f"trajectory {trajectory_id!r}",
            ),
            "generation_protocol_id": _generation_protocol_id(item, trajectory_id),
            "agent_prompt_profile_id": _prompt_profile_id(item, trajectory_id),
            "treatment": _aliased_string(
                item,
                "treatment",
                "condition",
                context=f"trajectory {trajectory_id!r}",
            ),
            "delegation_depth": _aliased_string(
                item,
                "delegation_depth",
                "hop_mode",
                context=f"trajectory {trajectory_id!r}",
            ),
            "thinking_mode": _required_string(
                item,
                "thinking_mode",
                context=f"trajectory {trajectory_id!r}",
                fallback=(item.get("model") or {}).get("thinking_mode")
                if isinstance(item.get("model"), dict)
                else None,
            ),
        }
        previous = identities.setdefault(trajectory_id, identity)
        if previous != identity:
            raise ValueError(
                f"Trajectory {trajectory_id!r} has inconsistent paper-input metadata."
            )
    if not identities:
        raise ValueError("Paper-input analysis requires at least one trajectory.")
    return identities


def _generation_protocol_id(item: dict[str, Any], trajectory_id: str) -> str:
    explicit = item.get("generation_protocol_id")
    if explicit is not None and (not isinstance(explicit, str) or not explicit):
        raise ValueError(
            f"Trajectory {trajectory_id!r} has an invalid generation_protocol_id."
        )
    match = _GENERATION_SUFFIX.search(trajectory_id)
    suffix = match.group("protocol") if match else None
    if explicit is not None and suffix is not None and explicit != suffix:
        raise ValueError(
            f"Trajectory {trajectory_id!r} protocol metadata disagrees with its ID."
        )
    if explicit and explicit != DEFAULT_GENERATION_PROTOCOL_ID and suffix is None:
        raise ValueError(
            f"Trajectory {trajectory_id!r} is missing its generation-protocol ID suffix."
        )
    return explicit or suffix or DEFAULT_GENERATION_PROTOCOL_ID


def _prompt_profile_id(item: dict[str, Any], trajectory_id: str) -> str:
    explicit = item.get("agent_prompt_profile_id")
    if explicit is not None and (not isinstance(explicit, str) or not explicit):
        raise ValueError(
            f"Trajectory {trajectory_id!r} has an invalid agent_prompt_profile_id."
        )
    match = _PROMPT_SUFFIX.search(trajectory_id)
    suffix = match.group("profile") if match else None
    if explicit is not None and suffix is not None and explicit != suffix:
        raise ValueError(
            f"Trajectory {trajectory_id!r} prompt profile disagrees with its ID."
        )
    return explicit or suffix or "legacy_unspecified"


def _matches_rule(identity: dict[str, str], rule: dict[str, Any]) -> bool:
    return (
        identity["generation_protocol_id"]
        == rule["required_generation_protocol_id"]
        and identity["agent_prompt_profile_id"]
        == rule["required_agent_prompt_profile_id"]
        and rule["required_trajectory_id_fragment"]
        in identity["trajectory_id"]
    )


def _validate_controlled_matrices(
    identities: dict[str, dict[str, str]],
    rules: dict[str, Any],
    *,
    observed_domains: set[str],
) -> None:
    for domain_id, rule in rules.items():
        if domain_id not in observed_domains:
            continue
        selected = [
            identity
            for identity in identities.values()
            if identity["domain_id"] == domain_id
        ]
        expected = _expected_cells(rule)
        cells: dict[tuple[str, str, str], list[str]] = {}
        for identity in selected:
            cell = (
                identity["treatment"],
                identity["delegation_depth"],
                identity["thinking_mode"],
            )
            cells.setdefault(cell, []).append(identity["trajectory_id"])
        duplicates = {
            cell: trajectory_ids
            for cell, trajectory_ids in cells.items()
            if len(trajectory_ids) != 1
        }
        missing = sorted(expected - set(cells))
        unexpected = sorted(set(cells) - expected)
        if missing or unexpected or duplicates:
            raise ValueError(
                f"Paper-input domain {domain_id!r} does not contain exactly one "
                "trajectory per expected matrix cell; "
                f"missing={missing}, unexpected={unexpected}, duplicates={duplicates}."
            )


def _expected_cells(rule: dict[str, Any]) -> set[tuple[str, str, str]]:
    matrix = rule["expected_matrix"]
    return set(itertools.product(
        matrix["treatments"],
        matrix["delegation_depths"],
        matrix["thinking_modes"],
    ))


def _build_audit(
    policy: dict[str, Any],
    *,
    identities: dict[str, dict[str, str]],
    selected_identities: dict[str, dict[str, str]],
    item_count: int,
    selected_item_count: int,
    mode: str,
) -> dict[str, Any]:
    rules = policy["domain_protocols"]
    selected_ids = set(selected_identities)
    controlled_domains: dict[str, dict[str, Any]] = {}
    for domain_id, rule in sorted(rules.items()):
        observed = [
            identity
            for identity in identities.values()
            if identity["domain_id"] == domain_id
        ]
        selected = [
            identity
            for identity in selected_identities.values()
            if identity["domain_id"] == domain_id
        ]
        controlled_domains[domain_id] = {
            "status": "complete" if selected else "not_present",
            "required_generation_protocol_id": rule[
                "required_generation_protocol_id"
            ],
            "required_agent_prompt_profile_id": rule[
                "required_agent_prompt_profile_id"
            ],
            "observed_generation_protocol_ids": sorted({
                identity["generation_protocol_id"] for identity in observed
            }),
            "selected_generation_protocol_ids": sorted({
                identity["generation_protocol_id"] for identity in selected
            }),
            "selected_trajectory_count": len(selected),
            "excluded_trajectory_count": len(observed) - len(selected),
        }
    return {
        "schema_version": PAPER_INPUT_AUDIT_SCHEMA,
        "policy_id": policy["policy_id"],
        "policy_sha256": paper_input_policy_sha256(policy),
        "mode": mode,
        "input_item_count": item_count,
        "selected_item_count": selected_item_count,
        "excluded_item_count": item_count - selected_item_count,
        "input_trajectory_count": len(identities),
        "selected_trajectory_count": len(selected_identities),
        "excluded_trajectory_count": len(identities) - len(selected_identities),
        "selected_trajectory_ids": sorted(selected_ids),
        "selected_trajectory_sha256": _trajectory_ids_sha256(selected_ids),
        "excluded_trajectory_ids": sorted(set(identities) - selected_ids),
        "controlled_domains": controlled_domains,
    }


def _trajectory_ids_sha256(trajectory_ids: Iterable[str]) -> str:
    normalized = "\n".join(sorted(set(trajectory_ids))).encode("utf-8")
    return sha256(normalized).hexdigest()


def _matrix_values(
    matrix: dict[str, Any],
    field: str,
    allowed: set[str],
    domain_id: str,
) -> tuple[str, ...]:
    values = matrix.get(field)
    if (
        not isinstance(values, list)
        or not values
        or not all(isinstance(value, str) for value in values)
        or len(values) != len(set(values))
        or not set(values).issubset(allowed)
    ):
        raise ValueError(
            f"Paper-input rule {domain_id!r} has invalid {field}: {values!r}."
        )
    return tuple(values)


def _aliased_string(
    payload: dict[str, Any],
    primary: str,
    alias: str,
    *,
    context: str,
) -> str:
    value = payload.get(primary, payload.get(alias))
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} requires {primary}.")
    return value


def _required_string(
    payload: dict[str, Any],
    field: str,
    *,
    context: str,
    fallback: Any = None,
) -> str:
    value = payload.get(field, fallback)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} requires {field}.")
    return value
