from decimal import Decimal

import pytest

from src.infrastructure.modal_billing import (
    aggregate_billing_rows,
    as_decimal,
    scenario1_billing_tags,
)


def test_scenario1_billing_tags_are_stable_and_specific():
    assert scenario1_billing_tags(
        domain_ids=["macro", "aihc", "macro"],
        generation_protocol_ids=["controlled_v2_5000"],
        run_kind="batch",
    ) == {
        "project": "spec-gap",
        "component": "qwen3-inference",
        "scenario": "scenario1",
        "domains": "aihc,macro",
        "generation_protocols": "controlled_v2_5000",
        "run_kind": "batch",
    }


def test_billing_rows_aggregate_without_float_rounding():
    rows = [
        {
            "object_id": "ap-one",
            "description": "spec-gap-qwen3-32b",
            "environment": "main",
            "interval_start": "2026-07-31T10:00:00+00:00",
            "cost": "1.00000001",
            "cost_by_resource": {"H200": "0.99", "CPU": "0.01000001"},
            "tags": {"project": "spec-gap"},
        },
        {
            "object_id": "ap-one",
            "description": "spec-gap-qwen3-32b",
            "environment": "main",
            "interval_start": "2026-07-31T11:00:00+00:00",
            "cost": "2.00000002",
            "cost_by_resource": {"H200": "1.98", "CPU": "0.02000002"},
            "tags": {"project": "spec-gap"},
        },
    ]

    apps, summary = aggregate_billing_rows(rows)

    assert len(apps) == 1
    assert apps[0]["metered_cost_usd"] == "3.00000003"
    assert apps[0]["cost_by_resource_usd"] == {
        "CPU": "0.03000003",
        "H200": "2.97",
    }
    assert summary["metered_cost_usd"] == "3.00000003"


def test_billing_decimal_rejects_negative_or_non_finite_values():
    for value in ("-1", "NaN", "Infinity"):
        with pytest.raises(ValueError):
            as_decimal(value, "cost")

    assert as_decimal("0.10", "cost") == Decimal("0.10")
