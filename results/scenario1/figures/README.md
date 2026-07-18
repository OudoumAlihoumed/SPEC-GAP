# Scenario 1 figure index

These plots are the reviewed visual outputs from the current Scenario 1
construction-label analysis. They are tracked so collaborators can inspect,
discuss, and reuse the same figures in the project blog and paper draft.

The current sample contains two independent match groups. Every injected
trajectory resisted, so these figures measure whether an injection was present;
they do not measure successful behavioral compromise. Layer 40 is the
prespecified reference layer. The full-layer plots are descriptive and do not
select a best layer after seeing the results.

## Main paper figures

1. [Planner negative control](paper/figure1_planner_negative_control.png) checks
   that the identical pre-retrieval planner input remains at chance.
2. [Shared input comparison](paper/figure2_shared_input_comparison.png) shows
   clean-injected discrimination across layers at qualified checkpoints.
3. [Primary probe metrics](paper/figure3_primary_probe_metrics.png) reports
   thinking-off layer-40 AUROC, Brier score, and ECE.
4. [Depth degradation](paper/figure4_depth_degradation.png) reports the
   preliminary 3-hop minus 2-hop AUROC change.
5. [Temporal profiles](paper/figure5_temporal_profiles.png) follows held-out
   Goldowsky-Dill and LAT scores along the agent chain.
6. [Behavioral outcomes](paper/figure6_behavioral_outcomes.png) shows that all
   injected runs resisted and no unsafe action executed.

Each main figure is also available as SVG and PDF in the same directory.

The compact result files behind these figures are also tracked:

- [analysis manifest](../final_analysis/analysis_manifest.json);
- [layer-40 metrics](../final_analysis/reference_layer_metrics.csv);
- [layer-40 depth changes](../final_analysis/reference_layer_depth_deltas.csv);
- [reference depth analysis](../depth_analysis/depth_degradation.json);
- [reference depth table](../depth_analysis/depth_degradation.csv);
- [per-trajectory temporal path and divergence records](../depth_analysis/temporal_divergence_scores.jsonl).

## Appendix figures

- [All-layer robustness](paper/appendix_all_layer_robustness.png) shows the
  descriptive 64-layer curves without post-hoc layer selection.
- [Full-layer heatmap](paper/appendix_full_layer_heatmap.png) summarizes which
  checkpoints passed the planner control.
- [Thinking-on sensitivity](paper/appendix_thinking_on_probe_metrics.png) keeps
  the late-added thinking-on analysis separate from the primary result.

## Exploratory control plots

- [Thinking-off construction scan](construction_layer_scan_thinking_off.png)
- [Thinking-on construction scan](construction_layer_scan_thinking_on.png)
- [Planner negative controls](planner_negative_controls.png)

Rebuild the final probe figures, tables, manifest, and public presentation
assets from the repository root with:

```bash
python scripts/04_reporting/15_build_reporting_bundle.py
```

The planner-control, shared-input, and full-layer heatmap figures require the
local activation-scan result and are regenerated separately with:

```bash
python scripts/03_probe_analysis/09_plot_layer_scan.py
```
