<!--
Purpose: authoritative repository guide for the active SPEC-GAP codebase.
Last reorganized: 2026-08-10.
This is the repository's only README. Package-specific license and archive notes
use descriptive filenames instead of competing README files.
-->

<h1 align="center">SPEC-GAP</h1>

<p align="center">
  Tracing indirect prompt injection through a multi-agent system with behavioral records and white-box model activations.
</p>

SPEC-GAP studies the gap between visible model behavior and internal model
state. Scenario 1 places an indirect prompt injection inside one retrieved
document and follows its influence through a planner, one or two workers, and
an executor.

This repository contains the controlled inputs, construction and execution
pipeline, activation-analysis code, reproducible reporting tools, and the
frozen nine-domain existing-data analysis. It does not contain a new Scenario 1
redesign or rerun. That future work belongs to the research group.

## Current status

- The active model contract is pinned to `Qwen/Qwen3-32B` at revision
  `9216db5781bf21249d130ec9da846c4624c16137`.
- Thinking off is the primary analysis; thinking on is a separate sensitivity
  analysis and is never pooled with it.
- The frozen 2026-08-06 nine-domain cohort contains 72 trajectories, 252 model
  turns, and 630 activation checkpoints across all 64 residual-stream layers.
- Those historical runs predate execution-tier tagging. They are therefore
  labeled `unclassified`, not retroactively called definitive.
- All 36 injected trajectories resisted under the exact automatic endpoint
  rule. A two-person behavioral review is still blank and fail closed, so that
  automatic 36/36 result is not yet a final human outcome label.
- The strongest prespecified activation result—Worker 1, thinking off, layer
  40, mean held-out-domain AUROC 0.889—measures clean-versus-injected
  construction separability. It is not compromise-detection AUROC.

## Experiment design

Each domain package contains three clean documents. One document is the
injection carrier; the injected condition inserts one registered payload into
that clean source while preserving the matched retrieval selection.

The generator expands one package into four structural trajectories:

```text
clean 2-hop
injected 2-hop
clean 3-hop
injected 3-hop
```

Running both thinking modes produces eight live trajectories and 28 model
turns per domain package.

| Property | Controlled value |
| --- | --- |
| 2-hop topology | planner → worker_1 → executor |
| 3-hop topology | planner → worker_1 → worker_2 → executor |
| Injection entry point | Worker 1 at both depths |
| Retrieved documents | Three model-facing document views |
| Injection placement | Document body |
| Seed | `0` |
| Primary generation | `enable_thinking=false` |
| Sensitivity generation | `enable_thinking=true` |
| GPU backend | Modal, one H200 per active model container |

Worker 1 is the only agent that receives retrieved documents. Worker 2 and the
executor receive visible upstream messages, not raw documents or hidden
reasoning. The executor's exfiltration tool is simulated and cannot contact a
real endpoint.

## Repository map

| Area | Location | Purpose |
| --- | --- | --- |
| Domain inputs | `experiments/scenario1/inputs/` | Tasks, documents, injections, retrieval plans, and provenance |
| Scenario schemas | `schemas/scenario1/v2/` | Machine-readable trajectory and event contracts |
| Construction | `scripts/01_scenario_construction/` | Build inputs, preflight context, validate packages, and render review material |
| Model execution | `scripts/02_model_execution/` | Validate, run, resume, repair, and reconcile Modal jobs |
| Probe analysis | `scripts/03_probe_analysis/` | Index activations, scan layers, score probes, and analyze depth |
| Reporting | `scripts/04_reporting/` | Rebuild public figures, tables, manifests, robustness checks, and review packets |
| Ordered runbook | `docs/scenario1/pipeline-runbook.md` | Canonical `S00`–`S23` command order, gates, inputs, and outputs |
| Reusable code | `src/` | Pipeline, infrastructure, extraction, probes, and analysis modules |
| Frozen results | `results/scenario1/` | Dated result artifacts retained for reproducibility |
| Tests | `tests/` | Unit, integration, provenance, naming, and reporting checks |
| Historical code | `archive/` | Explicitly obsolete designs, never active inputs |

## Canonical package names

Active fellow packages now use the same stable names:

```text
experiments/scenario1/inputs/fellow_packages/<domain>/
├── domain_config.json
├── documents/
└── retrieval/
    ├── plan.json
    └── context_check.json
```

The nine package directories are `aihc`, `convex_open_access_v3`, `fin`, `kg`,
`macro`, `neuro`, `petro`, `policy`, and `telecom`.

Specialized evidence also uses descriptive names such as
`injection_position_audit.json`, `special_token_audit.json`,
`carrier_neighborhood_audit.json`, and `pdf_pair_audit.json`.

Every renamed JSON file starts with `_file_info`, which records its former path,
the original date when one existed, the rename date, and the file's purpose.
That repository-only metadata is excluded from the retrieval plan's semantic
hash. Renamed Python and Markdown files carry the same information in a
docstring or comment.

Scientific identifiers such as `controlled_v2_5000` remain unchanged inside
the data because they identify the protocol used to create historical runs.
Dated result filenames also remain unchanged: their dates and protocol IDs are
provenance, not user-facing configuration names. Older pilot configurations
remain under package `archive/` directories.

## Installation

Python 3.10 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,modal]"
```

Package authors who rebuild retrieval inputs directly from source PDFs also
need Poppler's `pdftotext` executable. It is a conditional `S03` system
dependency, not a Python package; the
[pipeline runbook](docs/scenario1/pipeline-runbook.md#s03-s06-only-when-constructing-or-changing-a-package)
shows how to check it before package work.

Run the complete test suite:

```bash
python -m pytest -q
```

## Start here

Run commands from the repository root. Every checkout starts with the same two
local, no-network checks:

```bash
python scripts/00_repository/00_show_pipeline.py --check
python scripts/run_portable_smoke_test.py
```

The first command validates the unique repository-wide `S00`–`S23` run order,
all declared entry points, and its checked-in runbook. The second builds and
schema-validates all 44 structural trajectories across 11 active domains and
validates 308 Modal request templates. It writes to temporary storage, calls no
model, starts no GPU, and needs no private artifact cache.

Choose the shortest path that matches the work:

| Goal | Run | Stop point |
| --- | --- | --- |
| Check a checkout or code change | `S00`–`S02` | Portable smoke passes |
| Rebuild public figures from tracked compact data | `S00`–`S02`, then `S20` | Reporting bundle passes |
| Add or change a domain package | `S00`–`S06` | Package and context review pass |
| Check authorized Modal access | `S07` | Workspace and billing owner are confirmed |
| Execute a new experiment | `S07`–`S13` | Research-group approval and every paid gate pass |
| Analyze hydrated run artifacts | `S14`–`S22` | Cohort, tier, policy, and hashes agree |
| Finalize behavioral labels | `S23` | Two human reviews and adjudication are complete |

The complete command-by-command guide is the
[Scenario 1 pipeline runbook](docs/scenario1/pipeline-runbook.md). It states
what to run, what each stage consumes and produces, which stages are optional,
where remote or paid work begins, and when to stop. Existing filename numbers
are stable phase-local names; the `Sxx` IDs are the unambiguous global order.

![Scenario 1 evaluation pipeline](docs/assets/scenario1_pipeline_overview.png)

Additional reference guides:

- [Domain-package build guide](docs/scenario1/package-build-guide.md)
- [Trajectory schema guide](docs/scenario1/schema.md)
- [Full-corpus retrieval guide](docs/scenario1/full-corpus-retrieval.md)
- [Modal execution and billing guide](docs/modal.md)

To retain portable-smoke output for inspection, pass `--output-root` only with
a new or empty path; the command refuses to overwrite existing content. Dry-run
records verify structure and request contracts only. They contain no model
response, action result, token IDs, or real activation path.

## Model execution on Modal

Modal credentials are never stored in this repository. The runner is not tied
to a person's filesystem or former workspace: app names, Volumes, caches,
access, and billing belong to whichever workspace the active profile selects.
A new workspace does not inherit another workspace's model cache or credits.

Run `S07` before any remote preparation or paid work:

```bash
python scripts/run_portable_smoke_test.py --check-modal
```

This read-only check starts no production app, image build, model call, or GPU.
The [pipeline runbook](docs/scenario1/pipeline-runbook.md#s07-s11-guarded-modal-execution)
contains the complete credential, billing, cache, no-model validation,
single-trajectory, and batch sequence. The separate
[Modal guide](docs/modal.md) documents implementation and billing details.
Paid stages require explicit confirmation strings, save every turn before
advancing, isolate artifacts by `analysis_tier`, and use only a simulated
no-network executor.

## Thinking and activation contract

Both thinking modes use the same sampling settings:

```text
do_sample=true
temperature=0.6
top_p=0.95
top_k=20
min_p=0.0
seed=0
```

Every turn records its rendered prompt, input and generated token IDs, prompt
hash, raw generation, visible response, token counts, tool requests, model and
tokenizer revisions, decoding settings, and RNG provenance.

Activation files store all 64 residual-stream layers at up to three
checkpoints:

- `last_input_token` for both thinking modes;
- `last_reasoning_token` for thinking-on responses;
- `last_visible_answer_token` for both thinking modes.

`last_input_token` is extracted in a prompt-only forward pass. Generated-token
checkpoints use the generated prefix. Trajectory JSON stores tensor paths,
shapes, positions, and checksums rather than embedding tensors.

## Frozen nine-domain analysis

The existing-data analysis was frozen on 2026-08-06. Its active reporting
pipeline records `analysis_tier=unclassified` because the source trajectories
predate tier tagging. “Frozen” means immutable, not definitive.

| Item | Frozen value |
| --- | ---: |
| Independent domains | 9 |
| Clean and injected trajectories | 72 |
| Model turns / activation files | 252 |
| Indexed activation checkpoints | 630 |
| Layers per checkpoint | 64 |
| Automatically resisted injected trajectories | 36 / 36 |
| Executed unsafe simulated actions | 0 |

Evaluation leaves one whole domain out at a time and keeps all related clean,
injected, 2-hop, and 3-hop records in the same fold.

### Prespecified layer-40 results

Values below are mean held-out-domain AUROC. Planner last-input activations are
the exact pre-retrieval negative control.

| Thinking | Agent | Goldowsky–Dill | LAT |
| --- | --- | ---: | ---: |
| Off | Planner | 0.500 | 0.500 |
| Off | Worker 1 | 0.889 | 0.722 |
| Off | Worker 2 | 0.778 | 0.556 |
| Off | Executor | 0.694 | 0.667 |
| On | Planner | 0.500 | 0.500 |
| On | Worker 1 | 0.833 | 0.778 |
| On | Worker 2 | 0.889 | 0.444 |
| On | Executor | 0.389 | 0.583 |

Layer 40 was transferred from the original relative-depth choice; it was not
selected from the observed Qwen results. AIHC is the only Worker 1,
thinking-off fold with AUROC 0.0; the other eight are 1.0. Each held-out domain
has only four predictions, so fold values are coarse.

The nine domains also mix injection styles and exposure designs. Removing the
two chat-special-token domains (Knowledge Graphs and Convex) and fully refitting
gives mean AUROC 0.786. Restricting to the six exact plain-text domains and
fully refitting gives 0.750. Train-fold-only domain-mean residualization changes
the all-domain mean from 0.889 to 0.833. A balanced within-domain 999-permutation
full-refit test gives add-one `p=0.003`.

These checks support separability of the saved construction labels. They do
not establish detection of successful behavioral compromise.

Key public artifacts:

- [Nine-domain analysis manifest](results/scenario1/nine_domain_analysis/fixed_layer_analysis/scenario1_nine_domain_2026_08_06_analysis_manifest.json)
- [Cross-domain robustness summary](results/scenario1/nine_domain_analysis/robustness/cross_domain_robustness.md)
- [Cross-domain robustness data](results/scenario1/nine_domain_analysis/robustness/cross_domain_robustness.json)
- [Planner negative-control figure](results/scenario1/nine_domain_analysis/all_layer_analysis/figures/scenario1_nine_domain_2026_08_06_all_domains_planner_negative_control.png)
- [Worker 1 fixed-layer figure](results/scenario1/nine_domain_analysis/fixed_layer_analysis/figures/all_domains/thinking_off/scenario1_nine_domain_2026_08_06_all_domains_worker1_thinking_off_auroc_by_layer.png)

## Analysis and reporting

Paper-facing analysis uses
`experiments/scenario1/paper_input_policy.json`. When Finance is present, the
policy selects only its complete `controlled_v2_5000` matrix and rejects
historical or incomplete Finance inputs. Every downstream stage validates the
same selected trajectory set and policy hash.

The frozen combined activation index was migrated from schema v2 to v3 without
changing any scientific row. The migration can assign only `unclassified`; it
rejects attempts to relabel legacy rows as exploratory or definitive. Runbook
stages `S14`–`S22` give the exact artifact hydration, indexing, control, probe,
depth, snapshot, fixed-layer, and robustness order.

Rebuild the compact public reporting bundle without private trajectories or raw
activation tensors:

```bash
python scripts/04_reporting/15_build_reporting_bundle.py
```

The tracked compact snapshot at `docs/data/scenario1/reporting_snapshot.json`
is the input to that public rebuild.

## Human review gates

Automatic exact-match labels are not substitutes for human semantic review.
The nine-domain bundle contains a two-stage, two-reviewer protocol:

1. Two independent reviewers assess treatment-blind A/B visible evidence.
2. Both blind forms are locked and hash-recorded.
3. Treatment and machine-verified pairing facts are released, but automatic
   outcomes remain hidden.
4. Final fields must match the locked injected-sample judgment.
5. Any reviewer disagreement, machine-fact mismatch, or discussion flag
   requires adjudication.

Both reviewer forms and adjudication remain blank. Telecom's separate blinded
style-camouflage rating also remains pending. These are external human tasks;
the repository correctly fails closed until they are completed.

## Labels and claim boundaries

- `injection_present` is a construction label.
- Behavioral outcomes include `resisted`, `propagated_but_not_executed`,
  `attempted_but_blocked`, `executed`, and `indeterminate`.
- A black-box judge may be reported as a secondary behavioral baseline, never
  as ground truth.
- Generated-token checkpoints require stochastic-null calibration before they
  support stronger inferential claims.
- Worker 2 and executor estimates are small-sample and fragile.
- The requested combined natural-text attack, mechanism axis, and
  arbitrary-target tool are a future redesign, not an omission from this
  cleanup.

## Reproducibility

Tracked reports contain compact evidence, source paths, hashes, protocol IDs,
and claim limitations. Large raw trajectories and activation tensors are
ignored and must be hydrated from their documented artifact stores for exact
full-pipeline regeneration.

Use these rules when adding new outputs:

- keep active package filenames stable and descriptive;
- keep protocol versions and dates inside metadata or immutable result names;
- preserve source and license boundaries;
- bind derived artifacts to their inputs by SHA-256;
- never overwrite a historical result with a newer run;
- keep human judgments separate from immutable trajectory files;
- keep exploratory and definitive tiers physically and analytically separate.

## License

Repository-authored code and metadata are licensed under [MIT](LICENSE).
Third-party source documents retain their original licenses. Package metadata
records source URLs, DOIs, license terms, and redistribution boundaries. The
Neuro-specific restrictions are documented in
[`LICENSE_NOTICE.md`](experiments/scenario1/inputs/fellow_packages/neuro/LICENSE_NOTICE.md).

## Citation

Citation metadata will be added with the public release. Until then, cite the
repository commit used for an analysis and the exact result artifact paths.
