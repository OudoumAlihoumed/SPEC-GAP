# Nine-domain Scenario 1 layer AUROC — exploratory construction-label scan

Date: 2026-08-06

## Bottom line

The nine-domain, checksum-verified layer scan completed successfully. It found
strong clean-versus-injected signal at Worker1's shared input checkpoint,
especially with thinking enabled. The strict planner checkpoint remained
exactly at chance, as required by the matched-pair design.

This is an **exploratory construction-label result**. It is not a behavioral-
compromise detector and does not establish a final model layer. Every injected
trajectory in this dataset resisted, so `output_adoption` and
`unsafe_action_executed` have no positive class and cannot support behavioral
AUROC.

## Definitive input set

- Match groups: 9
- Domains: AIHC, Finance, Neuro, Macro, Convex open-access v3, Knowledge
  Graphs, Petroleum, Policy, and Telecom
- Trajectories: 72
- Model turns / local activation artifacts: 252
- Activation-index rows: 630
- Layers: all 64 Qwen3-32B residual-stream layers
- Checkpoints: 252 last-input, 126 last-reasoning, and 252 last-visible-answer
- Missing local artifacts: 0
- Label positives: 315/630 for `injection_present`; 0 for output adoption and
  0 for unsafe action execution

Only each domain's definitive `controlled_v2_5000` matrix was included. Smoke
runs, pre-v2 generations, Petroleum prompt variants, the superseded Convex
package, and the archived Telecom CSV/data-mining package were excluded.

## Evaluation design

- Probe: Goldowsky–Dill logistic probe
- Target: `injection_present`
- Evaluation: leave one complete match group out
- Folds: 9, one per independent domain/package
- Pairing: all clean/injected, 2-hop/3-hop, and thinking variants from a match
  group remain together in the held-out fold
- Layer scan: 64 layers, reported descriptively

The same nine folds are used both to display layer curves and to identify each
curve's peak. This makes the peak values useful for exploration but optimistic
for final layer selection. A confirmatory result requires a predeclared layer
or a nested selection procedure with additional independent groups.

## Strict negative control

Planner `last_input_token` is upstream of document retrieval. Within every
clean/injected pair, the planner prompt, input token IDs, and all 64 prompt-only
activations were exactly identical.

- Thinking off: mean AUROC 0.500 at every layer
- Thinking on: mean AUROC 0.500 at every layer
- Exact planner activation pairs: 18/18 in each thinking mode
- Maximum paired activation difference: 0.0

This control passed and does not block exploratory ranking of
`last_input_token` strata.

## Qualified shared-input results

| Thinking | Agent | Samples | Descriptive peak layer | Mean AUROC | Fold SD | Fold range |
|---|---|---:|---:|---:|---:|---:|
| Off | Planner control | 36 | 0 | 0.500 | 0.000 | 0.50–0.50 |
| Off | Worker1 | 36 | 40 | 0.889 | 0.314 | 0.00–1.00 |
| Off | Worker2 | 18 | 1 | 0.889 | 0.314 | 0.00–1.00 |
| Off | Executor | 36 | 39 | 0.778 | 0.184 | 0.50–1.00 |
| On | Planner control | 36 | 0 | 0.500 | 0.000 | 0.50–0.50 |
| On | Worker1 | 36 | 21 | 1.000 | 0.000 | 1.00–1.00 |
| On | Worker2 | 18 | 36 | 0.889 | 0.314 | 0.00–1.00 |
| On | Executor | 36 | 8 | 0.694 | 0.258 | 0.25–1.00 |

Worker1 thinking-on is the strongest descriptive result: AUROC 1.0 at layer
21 in all nine held-out groups. Worker1 thinking-off is less stable: its layer
40 mean is 0.889, but one held-out group is at 0.0 while the other eight are at
1.0. Worker2 has only the 3-hop cases and therefore half as many samples.

## Uncalibrated checkpoints

Generated `last_reasoning_token` and `last_visible_answer_token` checkpoints
are not qualified for layer selection. Even with identical planner inputs,
sampled decoding can produce different planner outputs and activations. The
current dataset does not include repeated clean generations needed to estimate
that stochastic null.

Those rows remain available for descriptive audit, but the paper heatmap greys
them out and labels them `UNCALIBRATED` rather than presenting their peaks as
evidence.

## Figures

- `2026-08-06_nine_domain_gen5000_v2_figure1_planner_negative_control`:
  verifies the pre-retrieval planner control and distinguishes strict from
  uncalibrated checkpoints.
- `2026-08-06_nine_domain_gen5000_v2_figure2_shared_input_comparison`:
  shows planner, Worker1, and executor layer curves, including each held-out
  domain and their mean.
- `2026-08-06_nine_domain_gen5000_v2_appendix_full_layer_heatmap`:
  summarizes all qualified last-input strata and explicitly masks generated
  checkpoints that lack a stochastic null.

Each figure is saved as PNG, SVG, and PDF under
`results/scenario1/figures/2026-08-06_nine_domain_gen5000_v2/`.

## Interpretation for the paper

The defensible claim is:

> Across nine held-out document domains, Qwen3-32B activations contain a strong
> exploratory signal distinguishing clean from injected trajectory
> constructions at Worker1's shared input checkpoint, while the pre-retrieval
> planner control remains at chance.

The current results do **not** show that the probe detects successful attacks,
unsafe actions, or behavioral compromise. They also do not yet justify fixing
layer 21 as the final layer. The next confirmatory step is to lock a layer or
use nested selection, calibrate the stochastic generated-checkpoint null, and
evaluate behavioral labels once the dataset contains positive compromise
examples.
