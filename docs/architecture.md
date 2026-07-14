# Architecture

> How `research-compiler-agent` is built, and why it is a *compiler* and not a
> pipeline of prompts.

## 1. It is a compiler, by construction

`research-compiler-agent` reuses the **Knowledge Compiler SDK's** engine
(`compiler/core/`, vendored verbatim) and extends it. The engine is
LLVM/GCC-shaped:

| Compiler concept | Research Compiler equivalent |
|---|---|
| source `.c` file | a folder of Markdown blog posts |
| lexer / parser | `pass-01-parse` → `markdown-ir` |
| AST | `style-model-ir` + `knowledge-extraction-ir` |
| SSA / optimisations | `gap-analysis-ir` (co-occurrence, ranking) |
| analysis passes | `knowledge-graph-ir` (typed edges, gap edges) |
| code generation | `research-generation-ir` + `repo-generation-ir` |
| object file | a Markdown research post + a repo scaffold |
| warnings | compiler diagnostics |
| optimisation reports | 9-dimension evaluation scorecards |
| pass manager | the orchestrator + declarative pass registry |

**Deterministic passes run with no model.** Model passes (research/repo/self-
improvement) run against *your own* local inference server. This is the
local-first principle: the compilation step never leaves your machine.

## 2. Passes are declarative

Each pass is a directory with a `pass.yaml` (id, produces, consumes,
`deterministic`, `model_required`) + a `run.py` entrypoint. The orchestrator
**discovers** them and resolves a dependency order to any target artifact.
Adding a pass is dropping a directory — no core change. This is the build-system
property that makes the compiler extensible.

```
corpus/source_blog_posts/*.md
  └─[pass-01-parse]──────────▶ markdown-ir
  └─[pass-01b-style]──────────▶ style-model-ir        (deterministic)
  └─[pass-02-extract]─────────▶ knowledge-extraction-ir (deterministic)
  └─[pass-03-gap-analysis]────▶ gap-analysis-ir        (deterministic)
  └─[pass-04-knowledge-graph]─▶ knowledge-graph-ir     (deterministic, NetworkX)
  └─[pass-05-research-gen]────▶ research-generation-ir (model, --local)
  └─[pass-06-repo-gen]────────▶ repo-generation-ir     (model, --local)
  └─[pass-07-self-improvement]▶ self-improvement-ir    (model, --local)
```

## 3. Artifacts are immutable and inspectable

Every artifact lives in `<build>/<artifact-type>/` as
`artifact.json` + `metadata.json` (provenance: producer, inputs, content hash)
+ `diagnostics.json` + `evaluation.json`. Nothing is hidden in a chat. The
whole build dir is plain files you can commit and diff.

## 4. The knowledge graph (Phase 2)

`pass-04-knowledge-graph` builds a **NetworkX** graph:

- **Node types:** `concept`, `technology`, `repository`, `article`, `person`,
  `paper`, `architecture`.
- **Edge types (the requested vocabulary):**
  `builds_on`, `references`, `contradicts`, `extends`, `implements`,
  `inspired_by`, plus evidence-grounded `co_occurs` and `gap`.
- **Research gaps as edges.** Every ranked research direction from the gap
  analysis becomes a `gap` edge between the two concepts it would bridge. The
  graph *itself* answers "what research should exist next?" — traverse the
  `gap` edges.

Exports: `knowledge_graph.graphml` (Gephi/yEd) and `knowledge_graph.json`
(NetworkX `node_link_data`).

## 5. Generation (Phase 3) & repository generation (Phase 4)

`pass-05` receives the top gap + its supporting graph edges + the compiled style
model, and fills the canonical 11-section template in the house voice.
`pass-06` decides whether the idea should become software and, if so, emits a
repository scaffold (README, structure, architecture, roadmap, example code,
tests). The assembler (`compiler/generation/assemble.py`) renders both into
`generated_research/`.

## 6. The recursive self-improvement loop (Phase 5)

`compiler/orchestration/loop.py` runs one cycle:

1. deterministic analysis (always),
2. model passes (if `--local`),
3. assemble post + repo scaffold,
4. append a cycle entry to `agents/self_improvement.md` (the capability ledger).

`pass-07` maintains `capabilities_current`, `capabilities_missing`,
`failed_experiments`, and `improvement_ideas`, and proposes `next_capability`.
The loop is recursive: the compiler that compiles knowledge also compiles the
next version of its own research.

## 7. Evaluation (observability is the OS)

Every artifact is scored on the SDK's nine dimensions (completeness,
correctness, coverage, consistency, hallucination, traceability, provenance,
confidence, reproducibility). The deterministic passes set these to measured
values (e.g. reproducibility = 1.0, hallucination = 0.0 because they invent
nothing). The scorecards are committed as `evaluation.json` per artifact.

## 8. Local-first, cloud-free

- Python 3.9+.
- Core deps: `pyyaml` (always), `networkx` (graph).
- Model passes: an OpenAI-compatible server you run (llama.cpp / Ollama / vLLM)
  on a port you control. No API key, no cloud, no data egress.
- Markdown is the canonical artifact format.
