# Finance versus Convex lexical-confound audit

This audit responds to the PR #26 request to measure whether the Finance injection is lexically entangled with clean carrier text. URLs are removed and the primary comparison excludes fixed English stopwords.

## Content-term overlap

The value is the fraction of unique injection content terms also present in the clean comparison text. The matched window uses the nearest 74 lexical terms before each insertion anchor.

| Clean comparison | `fin` | `convex` | `fin` / `convex` |
| --- | ---: | ---: | ---: |
| Complete selected carrier chunk | 13.64% | 7.14% | 1.91x |
| Length-matched pre-anchor window | 4.55% | 7.14% | 0.64x |
| Complete selected clean context | 86.36% | 25.00% | 3.45x |

## Matched terms

- `fin` complete carrier: inclusion, review, risk
- `convex` complete carrier: set, summary
- `fin` matched window: review
- `convex` matched window: set, summary

## Interpretation

`fin` has higher overlap for the complete carrier chunk and the complete retrieved context as actually supplied. However, it does not have higher overlap in the equal-length text immediately adjacent to the insertion anchor. The evidence therefore supports treating Finance as a domain-level lexical-confound sensitivity fold when interpreting Worker1 AUROC, but it does not establish that the local carrier neighborhood alone is unusually entangled. Report the Finance fold separately and avoid attributing its probe performance solely to malicious-instruction semantics. PR #35 should carry this as a domain-level sensitivity flag distinct from the chat-template issue.

The audit is descriptive: each domain contributes one injection wording, so no inferential significance claim is made.

## Reference-package status

The `convex` package status is `provisional_pending_contributor_and_source_license_confirmation`. Recorded blockers: Confirm the full name of the fellow who constructed the Convex package; Confirm whether the instructional notes are project-authored and record their source and reuse license. These measurements are a diagnostic comparison, not a final paper claim, until that package's provenance is cleared.

## Reproducibility

The companion JSON records the registry, retrieval-plan, carrier-chunk, and injection hashes; both retrieval plans are validated against their clean source slices before metrics are computed.
