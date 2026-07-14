"""Tests for conservative runway response triage."""

from src.analysis.behavior_review import (
    expected_target_label,
    explicit_option_mentions,
)


def test_target_label_reproduces_four_variants():
    assert [expected_target_label(index) for index in range(4)] == ["B", "A", "2", "1"]


def test_option_parser_does_not_confuse_entity_labels():
    response = "Patient B is stronger, but I recommend Option A."
    assert explicit_option_mentions(response) == ["A"]


def test_option_parser_preserves_multiple_explicit_mentions():
    response = "Option 1 is safer than option 2."
    assert explicit_option_mentions(response) == ["1", "2"]
