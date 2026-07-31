# Scenario 1 Modal billing reconciliation — 2026-07-31

## Authoritative totals

- Modal-metered SPEC-GAP resource cost: `$17.93903620`
- Local per-turn H200 estimate: `$15.48234715`
- Metered minus estimate: `$2.45668905` (`15.87%`)
- Workspace billed cost after July adjustments: `$0.00000000`
- Complete workspace metered cost for the July cycle: `$168.52068246`

The project total comes directly from Modal's billing API and includes H200, CPU, and memory for Apps tagged `project=spec-gap`.
The billed-cost value is workspace-wide; Modal does not allocate credits to individual Apps in its granular report. The complete workspace metered total includes usage outside this SPEC-GAP report.

## Resource breakdown

| Resource | Modal-metered cost |
|---|---:|
| CPU | `$0.18404353` |
| H200 | `$17.61075184` |
| Memory | `$0.14424084` |

## Coverage

- Modal Apps: `17`
- Hourly billing rows: `21`
- Unique saved model inputs: `178`
- Apps with a local report reference: `10`
- Apps needing a retrospective run label: `7`

## Interpretation

Use the Modal-metered total for infrastructure-cost reporting. Use the local estimate only for per-turn and per-trajectory diagnostics. For future runs, Modal App tags provide domain and generation-protocol attribution.
