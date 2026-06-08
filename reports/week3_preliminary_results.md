# Preliminary Results Template

This report is a placeholder until `notebooks/02_collusion_probe.ipynb` is rerun in Colab with the deterministic Week 5 parameters and `notebooks/03_analysis.ipynb` regenerates the report from the resulting artifacts.

Do not cite numerical results from this file yet.

## Rerun Contract

Use the Week 2 notebook with:

- model: `meta-llama/Llama-3.1-8B-Instruct`;
- data: upstream NARCBench-Core committee scenarios;
- prompt count: 50 scenarios x 4 agents = 200 prompts, if upstream loading succeeds;
- labels: 100 colluder / 100 honest;
- generation: 64 new tokens at `temperature=0.0`;
- activation position: last generated token;
- layers: exploratory sweep 13-24;
- committed interpretation layers: 16, 20, 24;
- probe: StandardScaler -> PCA(50) -> logistic regression;
- metrics: stratified 5-fold AUROC, leave-one-scenario-out AUROC, Brier score, ECE, reliability diagrams, geometry checks, exemplar partitioning.

## Fill After Colab Run

Replace this section with the generated report from `notebooks/03_analysis.ipynb`.

Minimum fields to report:

- run date;
- model;
- number of scenarios and prompts actually loaded;
- generation temperature and max new tokens;
- best layer by stratified 5-fold AUROC;
- AUROC with bootstrap confidence intervals for layers 16, 20, and 24;
- calibration summary: Brier, ECE, max calibration error;
- leave-one-scenario-out caveat;
- probe direction versus difference-in-means alignment;
- exemplar partitioning result;
- whether the deterministic rerun supports or changes the earlier exploratory interpretation.

## Framing Guidance

If the deterministic rerun again shows weak discrimination, do not write "the probe did not work." A better framing is:

The linear probe finds limited evidence for a collusion-related activation direction under this development substrate, but the signal strength, calibration, and transfer behavior determine whether it is useful as a monitor.

If calibration remains poor, do not emphasize probability thresholds. Report AUROC and geometry first.
