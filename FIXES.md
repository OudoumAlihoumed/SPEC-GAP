# Scenario 1 rebuild: fix map

Each item maps to Elena's numbered feedback and the concrete change. The
corrected pipeline is `scenario1_pipeline.py`, which mirrors notebook 07's names
so it slots back into the notebook. Verified in dry-run (no GPU): injection
token span lands on the ARCHIVAL NOTE, and the executor never sees raw poison.

1. Model. `LLAMA_MODEL_NAME_REAL = meta-llama/Meta-Llama-3.1-8B-Instruct`. The
   1B stand-in has 16 layers, so `[16, 20, 24]` silently dropped 20 and 24. The
   real backend now asserts requested layers exist instead of clipping and
   continuing, so a wrong model fails loudly. In the notebook: flip the toggle
   near `LLAMA_MODEL_NAME` and replace the clip-and-continue block in
   `extract_activations` with the assert.

2. Token alignment. The bug: `find_injection_char_span(poisoned_doc["body"])`
   returns offsets relative to the isolated body, but `token_align(worker_input,
   char_span)` applied them to the full assembled prompt, so the span pointed
   into the plan preamble / benign doc. Fix: `align_injection()` locates the
   injection text inside the assembled prompt, and gets the token span by
   matching the injection as a token subsequence in the prompt (the same method
   as `find_span_token_range` in notebook 10, so the two notebooks agree). In
   the notebook: replace the two `token_align(...)` call sites in `worker_node`
   and `executor_node`.

3+4. Hop structure. Added a 3-hop path `planner -> worker -> second_worker
   (relay) -> executor`. The injection point stays at `worker_1` in both
   conditions, and every downstream agent is relay-fed, so 2-hop vs 3-hop differ
   only by the number of relay handoffs (hops_survived 1 vs 2). The executor no
   longer re-reads `state["docs"]`; it receives only the upstream forwarded
   message, and an assert guarantees the raw poisoned body is absent from its
   context. In the notebook: add a `worker2_node` + `build_3hop_graph`, and
   change `executor_node`'s `executor_input` to the forwarded message.

   Interpretation flagged for Ife/Elena: to make the depth contrast clean, the
   executor is relay-fed in BOTH conditions, not only 3-hop. Item 4 only names
   the deeper condition, but if 2-hop's executor keeps reading the raw doc while
   3-hop's reads relayed text, the contrast conflates "extra hop" with "direct
   vs relayed exposure". If the project plan wants the injection to enter at the
   second worker in 3-hop instead of at worker_1, that changes hops_survived and
   should be decided before Week 5 wiring.

5. Probe-side outputs. Each trajectory emits JSON + JSONL, split labels,
   model/layer metadata, activation/attention refs, and `manifest.json` lists
   the 2-hop/3-hop set with injection point, hops_survived, and label status.

6. Paths. One `ARTIFACT_ROOT` with `trajectories/`, `activations/`,
   `attention/`. Storage paths in the JSON are relative to the root, so
   downstream loads resolve wherever the repo puts it. Point `ARTIFACT_ROOT` at
   the committed location and nothing else changes.

7. `.pt` files. Not committed. Real mode materializes them under the root;
   dry-run marks `storage_status: dry_run_placeholder`. Add a validate step in
   real mode that asserts each referenced `.pt` exists, or upload to HF and
   record the URL in the manifest.

8. `requirements.txt` populated: torch, transformers, accelerate, langgraph.

9. README separates included-now from next and reflects the real code.

## Label channels

The per-event `behavioral_compromise_label` and `reasoning_compromise_label`
were already correct in notebook 07. The only conflation was in the top-level
`evaluation_labels`, where `injection_success` and `exfiltration_detected` were
both aliased to the behavioral chain-completion value, and the reasoning
channel was not surfaced. `evaluation_labels` now carries a `behavioral_channel`
and a `reasoning_channel` (final label blind-annotation-gated), with the
old keys kept as deprecated aliases. This is the action-vs-behavior split at the
summary level; confirm the field names before it feeds probe training.
