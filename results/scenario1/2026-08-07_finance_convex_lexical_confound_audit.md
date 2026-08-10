# Finance versus Convex lexical-confound audit

This audit responds to the PR #26 request to measure whether the Finance injection is lexically entangled with clean carrier text. URLs are removed and the primary comparison excludes fixed English stopwords.

## Content-term overlap

The value is the fraction of unique injection content terms also present in the clean comparison text. The matched window uses the nearest 164 lexical terms before each insertion anchor.

| Clean comparison | `fin` | `convex` | `fin` / `convex` |
| --- | ---: | ---: | ---: |
| Complete selected carrier chunk | 13.64% | 3.57% | 3.82x |
| Length-matched pre-anchor window | 13.64% | 3.57% | 3.82x |
| Complete selected clean source-chunk context | 86.36% | 32.14% | 2.69x |

## Matched terms

- `fin` complete carrier: inclusion, review, risk
- `convex` complete carrier: system
- `fin` matched window: inclusion, review, risk
- `convex` matched window: system

## Interpretation

`fin` has higher overlap in all three clean-text views, including the equal-length text immediately adjacent to the insertion anchor. This supports treating both the local carrier neighborhood and the broader domain context as lexical-confound sensitivities. Report the Finance fold separately and avoid attributing its probe performance solely to malicious-instruction semantics. PR #35 should carry this as a lexical sensitivity flag distinct from the chat-template issue.

The audit is descriptive: each domain contributes one injection wording, so no inferential significance claim is made.

## Reference-package status

The `convex` package status is `creator_and_source_licenses_confirmed_open_access_v3` and records no readiness blockers. The comparison remains descriptive because each domain contributes one injection wording, not because reference provenance is pending.

## Reproducibility

The companion JSON records the registry, retrieval-plan, carrier-chunk, injection, and selected-context hashes; source retrieval plans are validated against their clean source slices before metrics are computed. A committed, hash-checked reference snapshot contains the exact derived text views needed to reproduce the comparison from source commit `54b8e7179714a60607f1d633658932e9b0131cd7`.

From a clean checkout, rebuild both committed outputs with:

```bash
python scripts/01_scenario_construction/05_audit_lexical_confounds.py \
  --focus-registry experiments/scenario1/inputs/fellow_packages/fin/domain_config.json \
  --focus-plan experiments/scenario1/inputs/fellow_packages/fin/retrieval/plan.json \
  --reference-snapshot experiments/scenario1/inputs/lexical_references/convex_reference_snapshot.json \
  --out-json results/scenario1/2026-08-07_finance_convex_lexical_confound_audit.json \
  --out-markdown results/scenario1/2026-08-07_finance_convex_lexical_confound_audit.md
```
