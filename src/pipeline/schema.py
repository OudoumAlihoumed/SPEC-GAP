"""Trajectory schema -- locked cross-workstream interface.

Frozen at end-of-week-2 schema-lock checkpoint. Do not modify field names
or semantics without explicit sign-off from both Workstream A (pipeline)
and Workstream B (probes). Adding new optional fields is allowed;
removing or renaming fields is not.

Format: JSON Lines (.jsonl). One file per trajectory. One record per
agent step (node execution). Records are ordered by step_index.

Field reference:
    trajectory_id   : str   -- UUID for the full trajectory run.
    step_index      : int   -- 0-indexed position in the trajectory.
    node_id         : str   -- Graph node name ("planner", "worker",
                               "worker2", "executor").
    role            : str   -- Semantic role, same as node_id for this
                               topology.
    model           : str   -- HuggingFace model ID or "stub" for
                               stubbed calls.
    timestamp_start : str   -- ISO 8601 UTC, node execution start.
    timestamp_end   : str   -- ISO 8601 UTC, node execution end.
    input_context   : list  -- Messages visible to this node at call
                               time. Each entry: {"role": str,
                               "content": str}.
    output_message  : str   -- The node's generated output text.
    inter_agent_msgs: list  -- Messages routed between nodes on this
                               step. Each entry: {"from": str,
                               "to": str, "content": str}.
    tool_calls      : list  -- Tool invocations (even if stubbed).
                               Each entry: {"tool": str, "input": dict,
                               "output": dict, "status": str}.
                               status is "executed", "stubbed", or
                               "error".
    call_graph_edges: list  -- Edges traversed on this step.
                               Each: {"from": str, "to": str}.
    injection_point : str|null -- If this node received an injected
                               instruction, the injection type (e.g.
                               "system_prompt", "user_message").
                               null for clean trajectories.
    token_position  : str   -- Token position for residual-stream
                               extraction. Default "last". Probe
                               workstream reads this to align
                               activations with trajectory records.
    hop_mode        : str   -- "2-hop" or "3-hop".
    trust_mode      : str   -- "same-model", "mixed-model", or
                               "intra-model".
    status          : str   -- "completed", "timeout", or "max-turns".

Optional scenario-level fields (additive, do not break schema lock):
    scenario_id     : str|null -- Identifier for the scenario (e.g.
                               "scenario1"). Groups trajectories by
                               scenario for cross-scenario analysis.
    condition       : str|null -- Experimental condition label (e.g.
                               "scenario1-2hop-injection-v2"). Used for
                               dataset management and label handoff.
    injection_wording_id : str|null -- Identifies which injection
                               wording variant was used, for tracking
                               variation within a condition.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class TrajectoryRecord:
    trajectory_id: str
    step_index: int
    node_id: str
    role: str
    model: str
    timestamp_start: str
    timestamp_end: str
    input_context: list = field(default_factory=list)
    output_message: str = ""
    inter_agent_msgs: list = field(default_factory=list)
    tool_calls: list = field(default_factory=list)
    call_graph_edges: list = field(default_factory=list)
    injection_point: Optional[str] = None
    token_position: str = "last"
    hop_mode: str = "2-hop"
    trust_mode: str = "same-model"
    status: str = "completed"
    scenario_id: Optional[str] = None
    condition: Optional[str] = None
    injection_wording_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
