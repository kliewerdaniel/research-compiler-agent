# SDK Integration Plan

> How `research-compiler-agent` extends the Knowledge Compiler SDK. This document
> is honest about what is **reused**, what is **added**, and what is **missing**.

## 1. What we reused (verbatim, from `knowledge-compiler-sdk/compiler/core/`)

The engine is the SDK's engine. We vendored these files unchanged:

| File | Role |
|---|---|
| `core/registry.py` | Declarative pass discovery (`pass-*/pass.yaml`). |
| `core/orchestrator.py` | Plans + executes a target artifact from dependency edges. |
| `core/artifacts.py` | Immutable artifact store (write once, `metadata.json` provenance). |
| `core/diagnostics.py` | LLVM-style warnings/errors (`UNREFERENCED_ENTITY`, etc.). |
| `core/evaluation.py` | The 9-dimension scorecard. |
| `core/inference.py` | OpenAI-compatible local client + Ollama embedding fallback. |
| `core/llm_pass.py` | The `run_model_pass` scaffold (retry, batching, JSON repair). |
| `reports/dashboard.py` | Self-contained evaluation dashboard. |

Rationale: the SDK's engine is exactly the "compiler for knowledge" substrate
the research compiler needs. Re-implementing it would be wasted work and would
diverge from the source of truth. We extend, not fork.

## 2. What we added (research-specific passes)

| Our pass | SDK equivalent | Difference |
|---|---|---|
| `pass-01b-style` | (none) | Compiles a **style model** from the corpus — the SDK never models *voice*. |
| `pass-02-extract` (deterministic half) | `pass-02-extract` | We added a **heuristic, reproducible** extraction (repos, code, future questions) that runs *without* a model; the SDK's is model-only. |
| `pass-03-gap-analysis` | (none) | **Research-direction mining**: co-occurrence gaps + ranked hypotheses. The SDK has `pass-08-reasoning` (observations/contradictions) but not "what to research next". |
| `pass-04-knowledge-graph` | `pass-04-graph` | We use **NetworkX** with the requested edge vocabulary (`builds_on`, `references`, `contradicts`, `extends`, `implements`, `inspired_by`) **and** encode research gaps as `gap` edges so the graph answers "what research should exist next?". |
| `pass-05-research-generation` | `pass-09-specifications` (spirit) | Generates a *research post* (11-section template), not just an app spec. |
| `pass-06-repo-generation` | `pass-10-software` (spirit) | Generates a **repo scaffold** (README, structure, code, tests), not a Next.js app. |
| `pass-07-self-improvement` | (none) | The recursive capability ledger — the SDK is not self-modifying. |

## 3. Extension points we used (the SDK's actual contract)

- **Pass registry.** Every new capability is a `pass-*/pass.yaml` + `run.py`.
  The orchestrator picks it up on discovery. No `orchestrator.py` edit needed.
- **`run_model_pass`**. The three model passes are thin `run.py` files that call
  `core.llm_pass.run_model_pass` with a `build_user_prompt(inputs)` and a
  `SYSTEM_PROMPT`. The SDK's batching/retry/local-client logic is reused wholesale.
- **Artifact contract.** We write the same `{artifact.json, metadata.json,
  diagnostics.json, evaluation.json}` shape, so the SDK's dashboard and
  evaluation work unchanged on our artifacts.
- **Local inference client.** `pass-05/06/07` run against llama.cpp / Ollama /
  vLLM with no cloud dependency, exactly as the SDK intends.

## 4. What is missing / different (gaps we should close)

1. ~~**Embeddings + thematic clusters.**~~ **DONE** — `pass-03b-embeddings`
   wires `core.inference.InferenceClient.embeddings` (Ollama `nomic-embed-text`)
   into a semantic gap ranker. It embeds the corpus vocabulary, collapses
   morphological variants, and ranks research gaps by *semantic affinity vs.
   co-occurrence* — pairs that are close in meaning but never co-developed.
   `pass-05` prefers these reranked hypotheses when `embeddings-ir` is present.
   This was the capability the self-improvement pass (`pass-07`) proposed, then
   the compiler implemented — the recursive loop closing on itself.
2. **Reasoning IR** (`pass-08`): contradictions + observations. We have gaps but
   not `contradicts` edges mined from the corpus. *Extension:* add a
   `contradicts` edge type mined from opposing claims.
3. **The SDK emits a Next.js app** (`pass-10`); we emit *repo scaffolds*.
   If we want a browsable knowledge-graph UI, we can reuse the SDK's
   `pass-10-software` against our `knowledge-graph-ir`.
4. **PyTorch/transformers reuse.** The SDK is inference-only. A future
   `pass-02b` could use a local sentence-transformer for zero-shot concept
   extraction without an LLM server.

## 5. The recursive payoff

The SDK's thesis is *compile-time AI*: move semantic work into a build step.
This project applies it **reflexively** — the compiler compiles knowledge, and
`pass-07` proposes the next capability the compiler should grow. The SDK is the
static foundation; the research compiler is the part that points it at its own
next version.

```
Knowledge Compiler SDK  ──▶ engine (reused)
        +
research-compiler-agent ──▶ research passes (added)
        =
   a compiler that compiles knowledge
   and proposes the next version of its own research
```
