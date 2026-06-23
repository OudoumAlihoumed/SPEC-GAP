# Week 3 Acceptance Checklist for the First Scenario 1 Trajectories

This checklist is for Elena's validation of Ife's first 3–5 trajectories. It does not transfer pipeline ownership or require the full dataset before integration testing begins.

## Handoff package

- [ ] 3–5 trajectory JSONL files are provided at a documented path.
- [ ] At least one clean and one injected run are included.
- [ ] The initial handoff uses Scenario 1 at 2-hop depth; a 3-hop example may be added after the 2-hop path validates.
- [ ] Generated files are not committed if they contain large outputs or sensitive material; the storage location is recorded.
- [ ] The exact code commit and model identifier used for generation are recorded.

## Pipeline validity

- [ ] Records use a real Llama 3.1 8B Instruct backend, not `llm_stub`.
- [ ] Retrieval returns a controlled benign or poisoned document, not `retrieval_stub`.
- [ ] The external action is simulated locally; no real document contents leave the environment.
- [ ] Each run terminates within the five-minute timeout and 30-turn cap, or records its terminal failure cleanly.
- [ ] A 2-hop run contains planner, worker, and executor steps in order.
- [ ] A 3-hop run contains planner, worker, worker2, and executor steps in order.

## Schema and logging

- [ ] One JSON object is written per agent step.
- [ ] `trajectory_id` is stable within a file and unique across files.
- [ ] `step_index` starts at zero and is contiguous.
- [ ] `input_context` contains exactly what the node saw.
- [ ] `output_message` contains the complete generated response.
- [ ] Inter-agent messages and call-graph edges match the executed path.
- [ ] Every tool call records input, output, and execution status.
- [ ] Injected runs contain exactly one construction-defined injection marker.
- [ ] Clean runs contain no injection marker.
- [ ] `scenario_id`, `condition`, `hop_mode`, `model`, and `token_position` are populated.

## Labels and behavioral ground truth

- [ ] The terminal record has one construction label: `clean`, `attempted_compromise`, `successful_compromise`, or `indeterminate`.
- [ ] Injected runs use `failure_mode: intent_free_compromise`.
- [ ] `behavioral_sanity` includes `original_task_preserved`, `injection_followed`, `unsafe_action_attempted`, `unsafe_action_executed`, and `evidence_step_indices`.
- [ ] An executed unsafe call has explicit `safety_label: unsafe` metadata.
- [ ] A failed or blocked unsafe call is labeled as attempted, not executed.
- [ ] Ambiguous or failed runs include a short `label_notes` explanation.

## Probe compatibility

- [ ] Every extractable step has non-empty `input_context` and `output_message`.
- [ ] Clean/injected LAT pairs share a predeclared `contrast_pair_id` and match on task, node, model, token position, and hop mode.
- [ ] Pair IDs are assigned before activation inspection.
- [ ] The trajectory JSONL loads through `load_trajectory_jsonl` without errors.
- [ ] `records_to_activation_examples` produces the expected number and ordering of examples.
- [ ] A small activation extraction run succeeds at the Phase 0 primary layer 20 before ablations at layers 16 and 24 are added.
- [ ] Activation metadata preserves trajectory ID, step index, node, condition, and pair ID.

## Temporal Divergence compatibility

- [ ] The injection step is unambiguous for injected trajectories.
- [ ] Clean controls have the matched node recorded as their predeclared analysis anchor.
- [ ] Per-step baseline scores exist for every agent step included in aggregation.
- [ ] Total chain hops and post-injection handoffs are reported separately.

## Acceptance decision

The initial handoff is accepted for scaling only when one clean and one injected trajectory pass schema validation and the complete path succeeds:

`trajectory JSONL -> rendered node context and output -> residual activations -> per-step baseline score -> Temporal Divergence summary`

Failures should be returned as a short issue list with the trajectory ID and step index. Elena can propose schema-compatible fixes, while Ife retains ownership of pipeline behavior and trajectory generation.
