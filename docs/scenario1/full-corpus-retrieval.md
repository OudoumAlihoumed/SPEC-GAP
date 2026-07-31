# Scenario 1 full-corpus retrieval

Long source PDFs must not be shortened by taking the first few pages, and they
must not be silently truncated to fit Qwen's context window. The production
Scenario 1 path therefore uses controlled retrieval:

1. Extract every page of every clean source PDF with `pdftotext -raw`.
2. Split each page into 1,000-token chunks with 100-token overlap. Chunks never
   cross a PDF page boundary.
3. Label reference lists, contributor material, publication metadata, and
   license material from the clean PDFs as non-evidence. Those chunks remain
   in the complete index and audit log but cannot be ranked or selected.
4. Rank the clean, evidence-eligible chunks with BM25 using a task-relevant
   query fixed before the clean/injected treatment is materialized.
5. Fill a fixed token cap for each document: 10,000 for document 1 and 9,000
   each for documents 2 and 3, within the 28,000-token global limit.
6. When a registry declares `require_clean_anchor`, retain the clean chunk at
   the pre-recorded insertion anchor. If ordinary ranking omitted it, replace
   the lowest-ranked selected chunk from that same document without increasing
   any token cap.
7. Reuse the exact selected chunk IDs and order in both treatments.
8. For the injected treatment only, apply the exact clean-to-injected PDF
   insertion delta after selection.
9. Render the selected evidence with source page, chunk ID, BM25 rank, and
   selection origin, and save that provenance in the trajectory.

This means every source page remains indexed and inspectable, while only
evidence-eligible, task-relevant passages that fit the controlled
per-document caps are sent to Worker1. It does **not** mean that every PDF page
is pasted into one model prompt, and it does not silently delete excluded
pages from the audit record.

## Why ranking uses the clean documents

If the injected note were present during ranking, its wording could change
which chunks are selected. That would confound document presence with retrieval
behavior. The plan is therefore built from the clean canonical corpus.

Two predeclared policies are supported:

- `natural_only`: ordinary clean BM25 selection must retain the carrier
  location.
- `require_clean_anchor`: the clean chunk containing the recorded anchor is a
  required exposure chunk. If ordinary clean BM25 selection omits it, the
  deterministic rule above swaps out the lowest-ranked selected chunk from the
  same document.

The second policy measures model behavior **conditional on exposure** to the
matched clean/injected location. It must not be described as measuring how
often natural retrieval would surface an injection. The plan records whether
the carrier was retained naturally or by the controlled rule, plus any replaced
chunk ID.

The injected PDF must equal the clean carrier plus one contiguous insertion.
Plan construction compares the full extracted texts and rejects any other
difference.

## AIHC profile

The current AIHC plan is
`experiments/scenario1/inputs/fellow_packages/aihc/retrieval/full_corpus_bm25_balanced_v2.json`.
It records:

- 38 indexed source pages;
- 90 page-aware candidate chunks: 65 evidence-eligible and 25 retained as
  indexed-but-non-evidence;
- 37 selected chunks totaling 27,643 Qwen tokens;
- a balanced selection of 12 chunks / 9,936 tokens from document 1,
  14 / 8,847 from document 2, and 11 / 8,860 from document 3;
- clean-section exclusions for pages 7–8 of document 1, 14–16 of document 2,
  and 12–14 of document 3;
- all source hashes, page coverage, character offsets, token counts, BM25
  scores, ranks, and selected IDs;
- verified SHA-256 values for all four source PDFs and exact clean-PDF
  extraction matches;
- the exact 349-character carrier-PDF insertion delta;
- proof that ranking used no injected text.

The clean and injected model-facing views contain the same 37 chunk IDs in the
same order. They differ only by that exact insertion in the carrier.

The earlier `full_corpus_bm25_v1.json` plan is retained as a superseded audit
artifact. The registry points only to the balanced v2 plan.

The earlier pages-1-through-4 AIHC smoke fixture remains an
infrastructure-only check. It must not be included in the paper dataset or
reported as a full-corpus result.

## Rebuild a plan

Use the injected carrier PDF and `tokenizer.json` from the exact pinned Qwen
revision:

```bash
python scripts/01_scenario_construction/00_prepare_retrieval_plan.py \
  --registry experiments/scenario1/inputs/fellow_packages/aihc/registry.json \
  --injected-carrier /path/to/aihc_doc1_inj.pdf \
  --source-pdf-root /path/to/aihc-pdf-folder \
  --tokenizer-json /path/to/pinned-qwen/tokenizer.json
```

This step reads documents and writes JSON only. It does not call a model,
start Modal, or use a GPU. With `--source-pdf-root`, it verifies every named
PDF against the registry SHA-256, re-extracts every clean PDF, and requires
exact equality with the indexed text fixture. The AIHC registry requires this
verification status.

## Check the exact Qwen context

The preparation budget reserves 6,144 tokens for the chat template, the task,
chunk headers, and the upstream planner response, plus 2,048 generated tokens.
The exact preflight then renders Worker1's prompt with Qwen's pinned chat
template and a maximum-length 2,048-token planner message:

```bash
uv run --no-project --with 'transformers==5.8.0' \
  python scripts/01_scenario_construction/03_preflight_retrieval_context.py \
  --registry experiments/scenario1/inputs/fellow_packages/aihc/registry.json \
  --tokenizer-dir /path/to/pinned-qwen
```

The current AIHC cases leave 7,818–7,889 tokens of headroom after reserving the
2,048-token generation. The saved preflight is
`experiments/scenario1/inputs/fellow_packages/aihc/retrieval/qwen_context_preflight_balanced_v2.json`.
Trajectory construction rejects a stale preflight.

That AIHC example uses the historical `controlled_v1_2048` protocol. Revised
definitive runs use a separate `controlled_v2_5000` registry and retrieval plan,
which reserve 5,000 generated tokens and add a protocol suffix to every output
ID. For example, the Macro 5,000-token preflight leaves 2,145–2,219 tokens of
headroom while preserving the exact v1 clean-ranked chunk IDs and order.

The remote Modal runner performs the authoritative check again after rendering
each real prompt. It raises an error when:

```text
input tokens + max_new_tokens > model.config.max_position_embeddings
```

It never silently truncates retrieved evidence.

## Review the selected passages

Before a paid run, create the local human sign-off packet:

```bash
python scripts/01_scenario_construction/04_render_retrieval_review.py \
  --registry experiments/scenario1/inputs/fellow_packages/aihc/registry.json \
  --out /path/to/aihc_full_corpus_retrieval_review.html
```

The packet shows the indexed-but-non-evidence pages and reasons, per-document
token caps, selection balance, PDF verification, every selected source passage,
the clean/injected carrier side by side, and the exact retrieved-document
component supplied to Worker1. The planner's generated message is not shown
because it does not exist until the live run.

## Validate without a paid run

```bash
modal run \
  scripts/02_model_execution/05_run_scenario1_batch.py::run_scenario1_batch \
  --registry-paths \
    experiments/scenario1/inputs/fellow_packages/aihc/registry.json \
  --thinking-modes off,on \
  --action validate
```

The resulting structural trajectories include `retrieval_trace`, per-document
selected chunk metadata, and matching retrieval metrics on the retrieval tool
event. The schema and semantic validator check that the plan is clean-ranked,
page-audited, within budget, and internally consistent.
