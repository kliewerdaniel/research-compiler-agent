# Self-Improvement Ledger

> Maintained by `pass-07-self-improvement` and `compiler/orchestration/loop.py`.
> The compiler records what it can/cannot do, proposes the next capability, then
> implements it. The cycles below show that loop closing on itself.

## Capability status

- [x] deterministic analysis: parse, style, extract, gap, knowledge graph
- [x] research post generation (`pass-05`, house voice, 11-section template)
- [x] repository scaffold generation (`pass-06`)
- [x] self-improvement ledger (`pass-07`)
- [x] **semantic gap ranking via Ollama embeddings (`pass-03b-embeddings`)** —
  proposed by this ledger on 2026-07-14 14:31 as `semantic-gap-ranker`, then
  implemented. The compiler grew the capability it asked for.
- [x] **incremental re-compilation** — dependency-aware caching is now the
  default. Editing a blog post re-runs only `pass-01-parse` (and downstream if
  its output changed); editing a pass's code re-runs that pass + dependents but
  leaves siblings cached. A hash of each pass's code is recorded with its
  artifact. Force full rebuild with `--no-cache`.
- [x] **contradiction mining (`pass-03c-contradictions`)** — mines opposing
  claims from the corpus, emits `contradicts` reasoning edges into the
  knowledge graph, and surfaces resolution topics to the generation pass.
- [x] **self-writing pass generator (`pass-03d-pass-generator`)** — the compiler
  reads this backlog, picks the top unresolved item, and scaffolds a runnable
  pass directory (`pass-NN-<slug>/` with `pass.yaml`, `run.py`, `prompt.md`) into
  `compiler/passes/`. The next build discovers and runs it. The ledger is now a
  living work queue the compiler resolves itself.

## Backlog (next proposals)

- [x] an entity-resolution pass that merges duplicate person/repo nodes in the graph (e.g. "Orinth" vs "Ornith") — implemented as `pass-12-an-entity-resolution`

---

## Cycle log

## Cycle 2026-07-15

- wired `pass-05-research-generation` to consume `research-debt-ir` (declared in
  `CONSUMES` so the orchestrator orders pass-08 before pass-05). The model prompt
  now embeds the `research_debt` block: `debt_score`, top 8 ranked
  `consolidation_proposals` (deepen_post / develop_concept / consolidate_orphan),
  and top 8 `under_explored_concepts`. Added a pivot instruction: when a proposal
  is well-grounded in the provided graph edges, the model MAY address that debt.
  Follows the established opportunistic-read pattern (also reads embeddings-ir /
  contradictions-ir) so deterministic-only runs still work. Verified prompt
  assembly against real artifacts (no model server needed); live model test
  confirmed Orinth (:8080) consumed the `research_debt` block and pivoted to
  repay debt — generated "Sovereign Memory Bank: Autonomous Cognitive Memory for
  Agent Systems" by deepening thin post doc-135, quoting its consolidation
  proposal rationale verbatim.
- implemented `pass-12-an-entity-resolution`: reads the real `knowledge-graph-ir`,
  finds same-kind label variants (versioned/owner-variant repos, spacing variants)
  via a two-layer matcher (repos by project-name + edit-distance ≤2; concepts/
  tech/persons only when identical after stripping digit-runs + plural suffix,
  len≥6), emits `entity-resolution-ir` merge plan that `pass-04` applies.
- convergence: 2 runs on a fresh `--no-cache` build (pass-04 builds graph →
  pass-12 plans → next run applies), 1 run incrementally; idempotent (0 groups
  on a clean graph). Avoided circular dependency by keeping pass-04's read
  optional (not a hard `consumes`).
- merged 5 real duplicates: `knowledge graph`≡`knowledge-graphs`,
  `ggml-org/llama.cpp`≡`ggerganov/llama.cpp`, `PersonaGen`/`mindmap`/`objective`
  versioned repos. No false merges (`ai`/`rag`/`nlp` stay distinct; concept vs
  technology nodes of the same label are correctly kept separate).

## Cycle 2026-07-14 14:24

- graph nodes/edges: 326/1269
- research gaps detected: 40
- generated post: None
- generated repo: None
- proposed next capability: None

## Cycle 2026-07-14 14:31

- graph nodes/edges: 326/1276
- research gaps detected: 40
- generated post: Bridging Memory and Agency in Sovereign AI Systems
- generated repo: memory-agent-runtime
- proposed next capability: semantic-gap-ranker

## Cycle 2026-07-14 14:32

- graph nodes/edges: 326/1278
- research gaps detected: 40
- generated post: Bridging Memory and Agency in Sovereign AI Systems
- generated repo: memory-agent-runtime
- proposed next capability: semantic-gap-ranker

## Cycle 2026-07-14 15:12 — Orinth (real 35B)

- model: deepreinforce-ai_Ornith-1.0-35B-Q4_K_M.gguf on :8080
- generated post: Synthesizing Memory with Agent: The Substrate Is the Product (2027 words, 14 sections)
- generated repo: memory-agent-synthesis (README + example + tests)
- proposed next capability: incremental re-compilation

## Cycle 2026-07-14 — embeddings capability shipped

- implemented `pass-03b-embeddings` (Ollama nomic-embed-text, 768-dim, 53 concepts)
- semantic gaps now rank by affinity vs. co-occurrence
- `pass-05` consumes the embedding-reranked hypotheses

## Cycle 2026-07-14 — self-writing pass generator shipped

- implemented `pass-03d-pass-generator`: reads `## Backlog` from this ledger
  (a `ledger` special dependency, hashed like `source`), scaffolds a runnable
  pass dir (`pass-NN-<slug>/` with `pass.yaml`, `run.py`, `prompt.md`) into
  `compiler/passes/`.
- First real generation: `pass-08-a-research-debt-pass` (from the "research
  debt" backlog item), discovered + executed on the very next build.
- The compiler now extends itself: backlog proposal -> generated pass -> run.
- The ledger (this file) is a living work queue the compiler resolves itself.
- closes the loop: the capability proposed at 14:31 is now live
