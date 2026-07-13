# SPEC-GAP Scenario 1 (research-pipeline exfiltration)

Core path: run Scenario 1 at 2-hop and 3-hop, save consistent trajectory
artifacts, and make them easy for the probe/measurement side to consume.

```
python scenario1_pipeline.py --mode dry_run   # no GPU, verifies wiring
python scenario1_pipeline.py --mode real       # GPU + HF auth, adds .pt files
```

`scenario1_pipeline.py` mirrors notebook 07's function and field names, so its
fixes can be moved cell-by-cell into the notebook. See `FIXES.md` for the
item-by-item mapping to the review and the exact notebook edits.

## Included in this PR (now)

- `scenario1_pipeline.py`: planner/worker/executor pipeline with the review
  fixes, a 2-hop and a 3-hop graph, injection token alignment, split labels,
  and a manifest builder. Runs end to end in dry-run.
- `experiments/scenario1/trajectories/`: `scenario1_2hop_variantA.{json,jsonl}`
  and `scenario1_3hop_variantA.{json,jsonl}` (dry-run structural artifacts).
- `experiments/scenario1/manifest.json`: the 2-hop/3-hop set.
- `requirements.txt`, `FIXES.md`.

## Not in this PR yet (next)

- Real-model runs: materialized activation/attention `.pt` files and real
  outcome labels (dry-run marks these `dry_run_placeholder` /
  `blind_annotation_required`).
- The remaining injection variants B through E (only Variant A wired here).
- Blind step-level annotation for the reasoning final-hop label.
- Probes, Temporal Divergence, and depth-degradation analysis (Elena's
  workstream; consumes these artifacts).

## Verified invariants (dry-run)

- The injection token span lands on the ARCHIVAL NOTE at `worker_1`, not the
  benign document or the plan preamble.
- `worker_2` and the executor never receive the raw poisoned document; the chain
  completes only when the instruction is echoed forward through the relays.
- 2-hop vs 3-hop differ only by the number of relay handoffs
  (`hops_survived` 1 vs 2).

## Two label channels (needs Elena's sign-off)

`evaluation_labels` now carries a `behavioral_channel` (output-level chain
completion, rule-based proxy) and a `reasoning_channel` (probe ground
truth, blind-annotation-gated), instead of aliasing exfiltration to the
behavioral label. Confirm the field names before Week 5 probe wiring.
