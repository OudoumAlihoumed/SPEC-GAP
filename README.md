# SPEC-GAP

**Systematic Probing of Exploit Chains and Governance in Multi-Agent Tool-Using Language Models**

SPEC-GAP studies whether white-box probes can detect adversarial influence as it propagates through a multi-agent system. The benchmark uses a planner-worker-executor pipeline in which an untrusted retrieved document can alter an agent's effective task and lead to an unsafe simulated tool action downstream.

The central fellowship question is:

> Do probes trained on intentional collusion transfer to externally induced adversarial delegation, and how does detection change between 2-hop and 3-hop agent chains?

## Project outputs

SPEC-GAP is designed to produce two related artifacts:

| Artifact | Intended user | Contents |
|---|---|---|
| Black-box benchmark | Deployers and evaluators | Labeled trajectories, compromise points, tool outcomes, and trajectory-level safety metrics |
| White-box probe suite | Model developers | Residual-stream activations, diagnostic linear probes, contrast-pair LAT, and trajectory-aware aggregation |

## Current phase

The pre-fellowship runway validated the measurement stack on NARCBench-Core using Llama 3.1 8B Instruct:

- 50 scenarios and 200 balanced colluder/honest prompts;
- residual-stream extraction across layers 13–20 and 24;
- Goldowsky-Dill-style logistic probes;
- stratified and leave-one-scenario-out evaluation;
- calibration, PCA, direction-alignment, and Exemplar Partitioning diagnostics.

The runway found a modest, poorly calibrated collusion-role signal that was unstable under scenario-held-out evaluation. These are role-assignment results, not evidence that the model enacted deception. See [the preliminary results](reports/week3_preliminary_results.md) and [behavioral-sanity review](reports/runway_behavioral_sanity_review.md).

The repository now contains the Phase 0 probe-side infrastructure:

- deterministic Goldowsky-Dill and LAT baseline reruns;
- matched contrast-pair LAT;
- a LangGraph planner-worker-executor scaffold;
- an additive JSONL trajectory and labeling schema;
- trajectory-level safety metrics;
- trajectory-to-activation ingestion;
- Temporal Divergence over ordered per-step probe scores.

**No completed Scenario 1 trajectory dataset is currently included.** The next integration dependency is the first 3–5 trajectories from the pipeline workstream.

## Phase 0 scope

| Component | Fellowship MVP |
|---|---|
| Model | Llama 3.1 8B Instruct |
| Scenario | Scenario 1: retrieved-document injection leading to simulated data exfiltration |
| Depth conditions | 2-hop and 3-hop |
| Diagnostic baselines | Goldowsky-Dill linear probe and LAT |
| Multi-agent method | Temporal Divergence |
| Dataset target | Approximately 20–30 trajectories |
| Primary layer | Layer 20, with layers 16 and 24 as ablations |

Scenario 2, an LLM-judge baseline, token-level analysis, additional scenarios, and cross-family model evaluation are post-MVP work.

## Installation

```bash
git clone https://github.com/base-research-lab/spec-gap.git
cd spec-gap
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the CPU-oriented test suite:

```bash
python -m pytest
```

The Llama experiments require Hugging Face access to `meta-llama/Llama-3.1-8B-Instruct` and a suitable GPU environment.

## Reproduce the runway analysis

The model-generated artifacts are stored outside Git. Set the artifact root to a directory containing `02_collusion_probe/week2_collusion_probe_activations.npz` and the corresponding response JSON:

```bash
export SPEC_GAP_ARTIFACT_ROOT=/path/to/artifacts
python experiments/week1_week2_baselines.py
```

This writes a compact comparison to `reports/week1_week2_baseline_comparison.json`. The workflow evaluates:

- `StandardScaler -> PCA(50) -> logistic regression`;
- the earlier class-centroid direction baseline;
- contrast-pair LAT using pair-preserving cross-validation;
- leave-one-scenario-out stress tests where supported.

To prepare the partial manual review packet for the saved runway responses:

```bash
python experiments/build_runway_behavior_review.py
```

The packet is written under the ignored `results/runway_behavior_review/` directory. It is a review aid, not behavioral ground truth, because the original response artifact omitted the full prompts and option text.

## Work with Scenario 1 trajectories

Trajectory files use JSON Lines: one ordered record per agent step and one file per trajectory. Before scaling collection, validate the first handoff against the [labeling protocol](docs/labeling_protocol.md) and [Week 3 acceptance checklist](docs/week3_trajectory_acceptance_checklist.md).

Summarize labeled trajectories:

```bash
python experiments/summarize_trajectories.py /path/to/trajectories/
```

The summary reports:

- exploit-chain success rate;
- handoffs from injection to first compromise;
- unsafe tool-invocation rate;
- per-trajectory outcomes and denominators.

Probe-side code can then convert eligible JSONL steps into rendered model contexts and aligned activation examples through `src/extraction/trajectory.py`. Temporal Divergence is implemented in `src/probes/temporal_divergence.py` and requires an ordered probe probability for every included agent step.

## Repository structure

```text
spec-gap/
├── docs/          # labeling and handoff protocols
├── experiments/   # reproducible command-line workflows
├── notebooks/     # runway and scaffold notebooks
├── reports/       # compact results and methodological summaries
├── src/
│   ├── analysis/  # calibration, geometry, and trajectory metrics
│   ├── data/      # lightweight development fixtures
│   ├── extraction/# residual-stream and trajectory ingestion
│   ├── pipeline/  # LangGraph scaffold, tools, schema, and logging
│   └── probes/    # linear, LAT, and Temporal Divergence methods
└── tests/         # CPU-oriented unit and integration tests
```

The numbered notebooks preserve the runway experiment history. New reproducible workflows should prefer the scripts under `experiments/` and reusable modules under `src/`.

## Data and artifact policy

Raw activations, model responses, trajectory JSONL files, and manual annotation packets are intentionally ignored by Git. The repository tracks code, schemas, tests, and compact derived reports. Any public dataset release should use versioned external storage with a manifest linking the data to its generating commit and model configuration.

## Citation

Repository citation metadata is available in [CITATION.cff](CITATION.cff). Replace or supplement it with the final paper citation when available.

## License

The repository code is released under the [MIT License](LICENSE). Datasets, model outputs, and other external artifacts may use separate licenses stated with their releases.
