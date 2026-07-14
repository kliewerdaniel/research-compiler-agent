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

## Backlog (next proposals)

- [ ] incremental re-compilation with dependency tracking (proposed by Orinth run)
- [ ] `contradicts` edge mining from opposing corpus claims
- [ ] a self-writing pass generator (compiler emits its own next pass directory)

---

## Cycle log

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
- closes the loop: the capability proposed at 14:31 is now live
