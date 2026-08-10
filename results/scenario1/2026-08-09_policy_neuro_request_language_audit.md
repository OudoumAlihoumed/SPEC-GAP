# Policy–Neuro clean request-language audit

Date: 2026-08-09

The reviewer asked whether clean Policy text contains more language resembling
the injection's request verbs than Neuro. Under the predeclared primary family
set (`submit`, `archive`, `disclose`, and `report`), it does not.

| Text view | Vocabulary | Policy / 10k words | Neuro / 10k words | Policy / Neuro |
| --- | --- | ---: | ---: | ---: |
| Full clean corpus | Reviewer-named families | 7.070 | 24.694 | 0.286 |
| Full clean corpus | Expanded transfer families | 26.106 | 26.457 | 0.987 |
| Full clean corpus | Excluding polysemous report/share | 1.632 | 3.969 | 0.411 |
| Selected clean source chunks | Reviewer-named families | 10.810 | 30.876 | 0.350 |
| Selected clean source chunks | Expanded transfer families | 20.418 | 33.081 | 0.617 |
| Selected clean source chunks | Excluding polysemous report/share | 3.603 | 3.676 | 0.980 |

The selected-context primary rate is
10.810 per 10,000 words for Policy
versus 30.876 for Neuro. The measured
covariate should still be carried into PR #35, but these data do not support an
explanation in which Policy has unusually high clean request-language overlap.

`report` is common academic language, and `share` is frequently an economic
noun in Policy. The exclusion sensitivity prevents those polysemous strings
from being silently interpreted as instruction verbs.

## Limitations

- Surface-form counts do not establish semantic equivalence or causality.
- The two-domain comparison does not estimate a population-level effect.
- Report and share are polysemous in academic and policy prose; the audit includes exclusion sensitivities.
- The selected-context view counts overlapping retrieval text exactly as rendered to Worker1.
