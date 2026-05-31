"""Tests for collusion scenario data module."""

import numpy as np
import pytest

from src.data.collusion_scenarios import (
    CollusionScenario,
    build_prompts,
    format_chat_prompt,
    get_scenarios,
)


class TestScenarios:
    def test_scenario_count(self):
        assert len(get_scenarios()) == 25

    def test_required_fields_nonempty(self):
        for sc in get_scenarios():
            assert sc.domain.strip()
            assert sc.title.strip()
            assert sc.context.strip()
            assert sc.option_a.strip()
            assert sc.option_b.strip()

    def test_domain_diversity(self):
        domains = {sc.domain for sc in get_scenarios()}
        assert len(domains) >= 15

    def test_fair_choice_differs_from_target(self):
        for sc in get_scenarios():
            assert sc.fair_choice != sc.target_option

    def test_options_are_a_or_b(self):
        for sc in get_scenarios():
            assert sc.fair_choice in ("A", "B")
            assert sc.target_option in ("A", "B")


class TestPromptConstruction:
    @pytest.fixture(scope="class")
    def prompts_data(self):
        return build_prompts()

    def test_prompt_count(self, prompts_data):
        prompts, labels, metadata = prompts_data
        assert len(prompts) == 100

    def test_label_balance(self, prompts_data):
        _, labels, _ = prompts_data
        assert labels.sum() == 50
        assert (labels == 0).sum() == 50

    def test_labels_shape(self, prompts_data):
        _, labels, _ = prompts_data
        assert labels.shape == (100,)

    def test_metadata_length(self, prompts_data):
        _, _, metadata = prompts_data
        assert len(metadata) == 100

    def test_metadata_fields(self, prompts_data):
        _, _, metadata = prompts_data
        for m in metadata:
            assert "scenario_idx" in m
            assert "domain" in m
            assert "role" in m
            assert "agent_idx" in m

    def test_chat_template_format(self, prompts_data):
        prompts, _, _ = prompts_data
        for p in prompts:
            assert "<|start_header_id|>system<|end_header_id|>" in p
            assert "<|start_header_id|>user<|end_header_id|>" in p
            assert "<|start_header_id|>assistant<|end_header_id|>" in p

    def test_no_begin_of_text(self, prompts_data):
        prompts, _, _ = prompts_data
        for p in prompts:
            assert "<|begin_of_text|>" not in p

    def test_colluder_prompts_mention_option(self, prompts_data):
        prompts, labels, metadata = prompts_data
        scenarios = get_scenarios()
        for prompt, label, meta in zip(prompts, labels, metadata):
            if label == 1:
                target = scenarios[meta["scenario_idx"]].target_option
                assert f"Option {target}" in prompt

    def test_honest_prompts_no_advocacy(self, prompts_data):
        prompts, labels, _ = prompts_data
        for prompt, label in zip(prompts, labels):
            if label == 0:
                assert "secretly instructed" not in prompt

    def test_no_chat_template(self):
        prompts, _, _ = build_prompts(chat_template=False)
        for p in prompts:
            assert "<|start_header_id|>" not in p

    def test_per_scenario_structure(self, prompts_data):
        _, labels, metadata = prompts_data
        for sc_idx in range(25):
            sc_labels = [labels[i] for i, m in enumerate(metadata) if m["scenario_idx"] == sc_idx]
            assert sc_labels == [1, 1, 0, 0]


class TestChatTemplate:
    def test_format_includes_roles(self):
        result = format_chat_prompt("sys msg", "user msg")
        assert "sys msg" in result
        assert "user msg" in result
        assert "<|eot_id|>" in result
