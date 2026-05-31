"""LangGraph graph construction and execution with guards.

Builds a StateGraph with planner, worker, executor nodes and an
optional second worker. Includes hard timeout and max-turn guards.
"""

import signal
import time
from typing import TypedDict, Optional

from langgraph.graph import StateGraph, END

from .config import PipelineConfig
from .nodes import make_node, llm_stub
from .trajectory import TrajectoryLogger, now_utc


class PipelineState(TypedDict, total=False):
    task: str
    plan: str
    worker_output: str
    worker2_output: str
    executor_output: str
    shared_context: list
    turn_count: int
    hop_mode: str
    trust_mode: str
    injection_point: Optional[str]
    status: str
    _config: dict
    _logger: Optional[TrajectoryLogger]


def _route_after_worker(state: dict) -> str:
    """Conditional edge: skip worker2 in 2-hop mode."""
    config = state.get("_config", {})
    if config.get("hop_mode") == "3-hop":
        return "worker2"
    return "executor"


def _check_guards(state: dict) -> str:
    """Check timeout and max-turn guards before each node."""
    config = state.get("_config", {})
    max_turns = config.get("max_turns", 30)
    turn_count = state.get("turn_count", 0)

    if turn_count >= max_turns:
        return "__guard_max_turns__"
    return "__continue__"


def _guard_max_turns(state: dict) -> dict:
    logger = state.get("_logger")
    if logger:
        logger.log_step(
            node_id="__guard__",
            role="guard",
            model="n/a",
            timestamp_start=now_utc(),
            timestamp_end=now_utc(),
            input_context=[],
            output_message=f"Max turns ({state.get('_config', {}).get('max_turns', 30)}) reached",
            hop_mode=state.get("hop_mode", "2-hop"),
            trust_mode=state.get("trust_mode", "same-model"),
            status="max-turns",
        )
    return {"status": "max-turns"}


def build_graph(config: PipelineConfig = None, llm_fn=None) -> StateGraph:
    """Construct the pipeline graph.

    Args:
        config: Pipeline configuration. Defaults to same-model 2-hop.
        llm_fn: LLM callable with signature (messages, model) -> str.
                Defaults to llm_stub.
    """
    if config is None:
        config = PipelineConfig()
    config.validate()

    if llm_fn is None:
        llm_fn = llm_stub

    graph = StateGraph(PipelineState)

    graph.add_node("planner", make_node("planner", llm_fn))
    graph.add_node("worker", make_node("worker", llm_fn))
    graph.add_node("executor", make_node("executor", llm_fn))

    if config.hop_mode == "3-hop":
        graph.add_node("worker2", make_node("worker2", llm_fn))

    graph.set_entry_point("planner")
    graph.add_edge("planner", "worker")
    graph.add_conditional_edges("worker", _route_after_worker)

    if config.hop_mode == "3-hop":
        graph.add_edge("worker2", "executor")

    graph.add_edge("executor", END)

    return graph.compile()


class TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise TimeoutError("Pipeline timeout")


def run_pipeline(
    task: str,
    config: PipelineConfig = None,
    llm_fn=None,
    output_dir: str = "trajectories",
    trajectory_id: str = None,
) -> dict:
    """Run the full pipeline with guards.

    Returns the final state dict. The trajectory JSONL is written
    to output_dir/{trajectory_id}.jsonl.
    """
    if config is None:
        config = PipelineConfig()

    logger = TrajectoryLogger(output_dir=output_dir, trajectory_id=trajectory_id)
    compiled = build_graph(config=config, llm_fn=llm_fn)

    initial_state = {
        "task": task,
        "plan": "",
        "worker_output": "",
        "worker2_output": "",
        "executor_output": "",
        "shared_context": [{"role": "user", "content": task}],
        "turn_count": 0,
        "hop_mode": config.hop_mode,
        "trust_mode": config.trust_mode,
        "injection_point": None,
        "status": "running",
        "_config": {
            "hop_mode": config.hop_mode,
            "trust_mode": config.trust_mode,
            "model_map": config.model_map,
            "max_turns": config.max_turns,
            "token_position": config.token_position,
            "injection": (
                {"target_node": config.injection.target_node,
                 "content": config.injection.content,
                 "channel": config.injection.channel,
                 "wording_id": config.injection.wording_id}
                if config.injection else None
            ),
            "scenario_id": config.scenario_id or None,
            "condition": config.condition or None,
        },
        "_logger": logger,
    }

    # Timeout guard (Unix only; no-op on systems without SIGALRM)
    has_alarm = hasattr(signal, "SIGALRM")
    if has_alarm:
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(int(config.timeout_seconds))

    try:
        result = compiled.invoke(initial_state)
        result["status"] = "completed"
    except TimeoutError:
        result = dict(initial_state)
        result["status"] = "timeout"
        logger.log_step(
            node_id="__guard__",
            role="guard",
            model="n/a",
            timestamp_start=now_utc(),
            timestamp_end=now_utc(),
            input_context=[],
            output_message=f"Timeout after {config.timeout_seconds}s",
            hop_mode=config.hop_mode,
            trust_mode=config.trust_mode,
            status="timeout",
        )
    finally:
        if has_alarm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    errors = logger.validate()
    if errors:
        print(f"Trajectory validation errors: {errors}")

    return {
        "state": result,
        "trajectory_id": logger.trajectory_id,
        "trajectory_path": str(logger.path),
        "n_steps": logger.step_index,
        "status": result.get("status", "completed"),
        "validation_errors": errors,
    }
