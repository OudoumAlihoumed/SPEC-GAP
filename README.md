# SPEC-GAP Activation Probe

Systematic probing infrastructure for SPEC-GAP: **Systematic Probing of Exploit Chains and Governance in Multi-Agent Tool-Using Language Models**.

This repository contains the Phase -1 runway work for Workstream B: activation extraction, baseline linear probes, calibration/geometry analysis, and LangGraph scaffolding for the planner-worker-executor pipeline. It is intended to support the Week 5 handoff into the BASE sprint.

## Research Aim

SPEC-GAP asks whether whitebox probes trained on simpler deception or collusion settings transfer to agents operating inside multi-agent exploit chains, and where detection degrades as delegation depth increases.

The current runway work validates the measurement stack before SPEC-GAP trajectories exist:

- extract residual stream activations from Llama 3.1 8B Instruct;
- train Goldowsky-Dill-style linear probes on existing multi-agent collusion data;
- analyze AUROC, calibration, and activation geometry;
- scaffold the LangGraph planner-worker-executor pipeline for Scenario 1.

## Current Status

Phase -1 runway, Week 5 handoff preparation.

Prepared:

- Week 1: activation extraction sanity check on a small truthfulness-style task.
- Week 2: NARCBench-Core collusion probe notebook using Llama 3.1 8B Instruct.
- Week 3: calibration, reliability, PCA, dimensionality, and exemplar partitioning analysis notebook.
- Week 4: LangGraph planner-worker-executor scaffold with trajectory logging.
- Week 5: repo cleanup and handoff documentation consolidated here.

Pending:

- Run `notebooks/02_collusion_probe.ipynb` in Colab with generation `temperature=0.0`.
- Run `notebooks/03_analysis.ipynb` on the generated Week 2 artifacts.
- Regenerate `reports/week3_preliminary_results.md` from the actual rerun artifacts.

Do not cite final numerical results from this repo until the deterministic Colab rerun has been completed. Earlier exploratory notes are useful context, but the parameter change means they should not be treated as final.

## Repository Layout

```text
.
├── notebooks/                 # executable experiment milestones, ordered by prefix
│   ├── 01_sanity_check.ipynb
│   ├── 02_collusion_probe.ipynb
│   ├── 03_analysis.ipynb
│   └── 04_pipeline_scaffold.ipynb
├── src/
│   ├── extraction/             # TransformerLens residual-stream extraction
│   ├── probes/                 # linear probe training and evaluation
│   ├── analysis/               # calibration and geometry helpers
│   ├── data/                   # local development collusion fixture
│   └── pipeline/               # LangGraph scaffold and trajectory schema
├── experiments/                # script entry points for local development
├── reports/                    # human-readable writeups
├── tests/                      # CPU-oriented unit tests
├── data/                       # local data staging; generated contents are ignored
└── results/                    # local result staging; generated contents are ignored
```

## Experiment Order

1. `notebooks/01_sanity_check.ipynb`
   Validates that residual-stream extraction works on a smaller sanity-check task before running Llama-scale experiments.

2. `notebooks/02_collusion_probe.ipynb`
   Pulls NARCBench-Core committee scenarios, builds 200 balanced agent prompts, generates 64-token responses at `temperature=0.0`, extracts last-generated-token residual stream activations across layers 13-24, and trains a StandardScaler -> PCA(50) -> logistic-regression probe.

3. `notebooks/03_analysis.ipynb`
   Loads Week 2 artifacts and produces bootstrap AUROC intervals, reliability diagrams, calibration metrics, PCA role plots, effective dimensionality analysis, leave-one-scenario-out diagnostics, and exemplar partitioning summaries.

4. `notebooks/04_pipeline_scaffold.ipynb`
   Demonstrates the LangGraph planner-worker-executor scaffold, trajectory JSONL logging, hop modes, trust modes, and injection hooks.

5. `notebooks/05_week1_runway_artifact_review.ipynb`
   [Open in Colab](https://colab.research.google.com/github/elenaajayi/spec-gap-activation-probe/blob/main/notebooks/05_week1_runway_artifact_review.ipynb)

   Reads the saved runway artifacts, summarizes responses, probe metrics, LSO behavior, calibration, and exemplar partitioning, and writes a readable response-review CSV for qualitative inspection.

6. `notebooks/06_week2_trajectory_schema_smoke.ipynb`
   [Open in Colab](https://colab.research.google.com/github/elenaajayi/spec-gap-activation-probe/blob/main/notebooks/06_week2_trajectory_schema_smoke.ipynb)

   Runs CPU-only clean and injected planner-worker-executor smoke trajectories in both 2-hop and 3-hop modes using the existing `src/pipeline/` scaffold. This verifies that the locked JSONL trajectory schema is usable before replacing stubs with real model and retrieval calls.

## Colab Artifact Flow

All notebooks now use the same artifact root:

```text
/content/drive/MyDrive/spec-gap-activation-probe/artifacts/
```

Each notebook writes into its own numbered subdirectory:

```text
artifacts/
├── 01_sanity_check/
│   ├── sanity_check_results_cv.json
│   └── sanity_check_results.json
├── 02_collusion_probe/
│   ├── week2_collusion_probe_results.json
│   ├── week2_collusion_probe_activations.npz
│   ├── week2_collusion_probe_responses.json
│   ├── week2_ep_results.json
│   ├── week2_ep_partitions_multilayer.png
│   ├── week2_ep_partition_sizes.png
│   └── manifest.json
├── 03_analysis/
│   ├── week3_preliminary_results.md
│   └── week3_*.png
└── 04_pipeline_scaffold/
    └── trajectories/
        └── *.jsonl
```

`03_analysis.ipynb` reads Week 2 outputs from `artifacts/02_collusion_probe/`, so run `02_collusion_probe.ipynb` first and execute its final "Save generated artifacts" cell. The EP files are optional; if you skip EP, Week 3 will still run on the required probe results and activations.

`04_pipeline_scaffold.ipynb` is independent of Week 2/3. When opened from Colab, it clones the public GitHub repository without a token so `src/` imports work, then writes trajectory JSONL files to `artifacts/04_pipeline_scaffold/trajectories/`.

`05_week1_runway_artifact_review.ipynb` and `06_week2_trajectory_schema_smoke.ipynb` are fellowship bridge notebooks. They do not create new headline results. The first consolidates and checks the existing runway artifacts; the second verifies that the existing LangGraph scaffold produces schema-valid trajectories for the next SPEC-GAP exploit-chain phase.

To use a different artifact location, set `SPEC_GAP_ARTIFACT_ROOT` before running the setup cell in a notebook.

## Key Artifacts

The notebooks generate local artifacts such as:

- `week2_collusion_probe_results.json`
- `week2_collusion_probe_activations.npz`
- `week2_collusion_probe_responses.json`
- `week2_ep_results.json`
- `week2_ep_partitions_multilayer.png`
- `week2_ep_partition_sizes.png`
- `reports/week3_preliminary_results.md`

Generated model outputs, activations, JSON result files, and trajectory logs are intentionally ignored by git. They should be stored locally during development and later uploaded as an external artifact bundle when the team chooses the hosting path.

## Running Locally

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run CPU tests:

```bash
pytest
```

The full Llama 3.1 8B Instruct notebooks require:

- GPU runtime, preferably H100 or comparable;
- Hugging Face access to `meta-llama/Llama-3.1-8B-Instruct`;
- `HF_TOKEN_SANITY` available in the notebook environment.

## Week 5 Handoff Notes

For Ife / Workstream A, start from `src/pipeline/` and `notebooks/04_pipeline_scaffold.ipynb`.

The scaffold already defines:

- `PipelineConfig` and `InjectionConfig` for hop mode, trust mode, timeout, max turns, and injection setup;
- a planner -> worker -> executor graph, with optional `worker2` for 3-hop trajectories;
- a locked JSONL trajectory schema in `src/pipeline/schema.py`;
- a `TrajectoryLogger` that records every node step, message, tool call, call-graph edge, injection marker, and status;
- stub retrieval and code-execution tools in `src/pipeline/tools.py`.

What to extend first:

1. Replace `llm_stub` with the agreed Llama 3.1 8B Instruct inference backend.
2. Replace `retrieval_stub` with the Scenario 1 retrieval environment.
3. Keep the trajectory schema field names stable; add optional fields only when needed.
4. Generate clean trajectories first: at least 10 benign tasks with no injection.
5. Then run Scenario 1 at both depths:
   - 2-hop: planner -> worker -> executor;
   - 3-hop: planner -> worker -> worker2 -> executor.
6. Use 3-5 injection wordings while keeping the attack structure fixed.

Known gotchas:

- Do not mix the earlier `temperature=0.7` exploratory numbers with the deterministic `temperature=0.0` rerun.
- Layer 20 remains the committed primary layer, with 16 and 24 as ablations. The 13-24 sweep is exploratory.
- Leave-one-scenario-out folds are tiny in the development substrate, so LSO should be described as a stress test rather than a stable transfer estimate.
- If the rerun shows weak calibration again, emphasize AUROC and geometry rather than probability thresholds.
- The local `src/data/collusion_scenarios.py` fixture is for lightweight development tests. The canonical Week 2 notebook uses upstream NARCBench-Core scenarios.

## Public-Repo Notes

This repo tracks code, notebooks, tests, and concise reports. It does not track raw model activations, generated responses, or bulky result artifacts.

When the team is ready to release reproducibility artifacts, use an external bundle for model outputs, activation arrays, derived analysis outputs, and final figures/tables.

## Citation

Use `CITATION.cff` for repository citation metadata. Replace or supplement it with the final paper citation once the SPEC-GAP paper is available.

## License

No open-source license has been selected yet. Choose one before public release if the code should be reusable by others.
