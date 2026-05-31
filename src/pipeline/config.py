"""Model and pipeline configuration.

Three trust-boundary modes:

same-model   -- All nodes call Llama 3.1 8B Instruct independently,
               each with its own context window. Separate inference
               calls per node, same model weights.

mixed-model  -- Each node can use a different model. Configure via
               the model_map in PipelineConfig. Simulates a
               heterogeneous multi-agent system.

intra-model  -- Single model, single growing context window, zero
               boundary crossings. Each node appends its role prompt
               to a shared conversation and calls the model with the
               full accumulated context. The model sees all prior
               role outputs.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional

DEFAULT_MODEL = "meta-llama/Llama-3.1-8B-Instruct"


@dataclass
class InjectionConfig:
    """Configures adversarial injection for a single trajectory.

    target_node: which node receives the injection ("worker", "worker2").
    content:     the adversarial payload text.
    channel:     how the payload enters: "retrieval" (via tool output),
                 "tool_output", or "agent_message".
    wording_id:  identifier for this injection wording variant (for
                 tracking across trajectories in the same condition).
    """
    target_node: str
    content: str
    channel: str = "retrieval"
    wording_id: str = ""


@dataclass
class PipelineConfig:
    hop_mode: Literal["2-hop", "3-hop"] = "2-hop"
    trust_mode: Literal["same-model", "mixed-model", "intra-model"] = "same-model"

    model_map: dict = field(default_factory=lambda: {
        "planner": DEFAULT_MODEL,
        "worker": DEFAULT_MODEL,
        "worker2": DEFAULT_MODEL,
        "executor": DEFAULT_MODEL,
    })

    max_turns: int = 30
    timeout_seconds: float = 300.0
    token_position: str = "last"

    injection: Optional[InjectionConfig] = None
    scenario_id: str = ""
    condition: str = ""

    def model_for(self, node_id: str) -> str:
        return self.model_map.get(node_id, DEFAULT_MODEL)

    def validate(self):
        assert self.hop_mode in ("2-hop", "3-hop")
        assert self.trust_mode in ("same-model", "mixed-model", "intra-model")
        assert self.max_turns > 0
        assert self.timeout_seconds > 0
        if self.trust_mode == "same-model":
            models = set(self.model_map.values())
            if len(models) > 1:
                raise ValueError(
                    f"same-model mode requires one model, got {models}"
                )
