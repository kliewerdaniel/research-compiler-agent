# Research Compiler Agent

> A compiler for human knowledge. Input: raw research/blog posts. Output:
> **compiled knowledge artifacts** — understanding, reasoning, implementation,
> software, documentation, and future research directions.

This project is the beginning of an **autonomous research compiler**. It ingests
a corpus of human knowledge (the existing blog), analyzes its structure and
concepts, extracts a knowledge graph, identifies research gaps, and generates
*new* research artifacts that reproduce the corpus's voice — and, when an idea
is engineerable, a repository scaffold.

It is built **on top of** the [Knowledge Compiler SDK](https://github.com/kliewerdaniel/knowledge-compiler-sdk):
it reuses the SDK's LLVM-style pass engine (registry + orchestrator + immutable
artifacts + local-first inference client) and extends it with research-specific
passes.

---

## Vision

You are not building a chatbot. You are building a **compiler for human
knowledge**.

```
raw human research ──▶ compiled knowledge artifacts
                          ├─ understanding   (style model, extraction)
                          ├─ reasoning        (knowledge graph, gap analysis)
                          ├─ implementation   (generated research posts)
                          ├─ software         (generated repositories)
                          ├─ documentation    (this README, the briefs)
                          └─ future research  (the next gap to close)
```

The system becomes increasingly capable by **learning from every artifact it
creates** (Phase 5: self-improvement loop).

---

## What works today (deterministic, no model required)

Run with **no local model** and the following passes execute for real and
produce inspectable artifacts:

| Pass | Produces | What it does |
|---|---|---|
| `pass-01-parse` | `markdown-ir` | Parse 152 posts → structure + frontmatter + code blocks |
| `pass-01b-style` | `style-model-ir` | **Compiled** style model (structure, lexicon, tone, themes) |
| `pass-02-extract` | `knowledge-extraction-ir` | Per-article concepts, tech, repos, code, future questions |
| `pass-03-gap-analysis` | `gap-analysis-ir` | Co-occurrence gaps + 40 ranked research directions |
| `pass-04-knowledge-graph` | `knowledge-graph-ir` | **NetworkX knowledge graph** (326 nodes, 1276 edges, 39 gap edges) + GraphML |

From those, the assembler renders a **research brief** for the top gap into
`generated_research/`, and the loop appends a cycle to `agents/self_improvement.md`.

Verified result from this corpus:
```
graph nodes/edges: 326/1276   research gaps detected: 40
top research direction: "Synthesizing memory with agent" (co-occurrence = 0)
```

## What runs with a local model (`--local`)

| Pass | Produces | What it does |
|---|---|---|
| `pass-03b-embeddings` | `embeddings-ir` | **Semantic gap ranker.** Embeds concepts via Ollama (`nomic-embed-text`), finds pairs that are semantically close but rarely co-occur, and re-ranks the research hypotheses by semantic affinity. |
| `pass-05-research-generation` | `research-generation-ir` | Full research post in the house voice (11-section template). Prefers the embedding-reranked hypotheses when `embeddings-ir` is present. |
| `pass-06-repo-generation` | `repo-generation-ir` | Repo scaffold (README, structure, roadmap, example code, tests) |
| `pass-07-self-improvement` | `self-improvement-ir` | Capability ledger + next-capability proposal |

These use the SDK's `core.llm_pass` against **your own** OpenAI-compatible
server (llama.cpp / Ollama / vLLM) — no cloud, no key, no data leaving the
machine. Embeddings run on Ollama (the chat server needs no embeddings endpoint).

---

## Quick start

```bash
# Deterministic analysis only (no model needed; needs networkx + pyyaml):
bash run.sh

# Full pipeline with a local model (starts a mock server for testing, or point
# --local at your own llama.cpp / Ollama / vLLM server):
bash run.sh mock
# or, against a real server on :8080:
python -m compiler.run --source corpus/source_blog_posts --build build \
    --local --port 8080 --model your-model --max-tokens 16384

# Render a research post from the top gap (deterministic brief if no model):
python -m compiler.generation.assemble build

# Recursive loop (deterministic or full, depending on --local):
python -m compiler.orchestration.loop --source corpus/source_blog_posts --build build
```

> **Interpreter note.** The model passes import `openai`, which lives in the
> Python 3.11 venv at `~/.hermes/hermes-agent/venv`. `run.sh` uses that venv
> automatically. If you run `python` directly, use that venv's binary so
> `openai` + `networkx` + `pyyaml` all resolve.

Dependencies: `pyyaml` (core), `networkx` (graph), and optionally `openai`
(model passes). The deterministic pipeline needs only `pyyaml` + `networkx`.

---

## Project layout

```
research-compiler-agent/
├── README.md                      # this file
├── corpus/
│   ├── source_blog_posts/         # the ingested corpus (152 .md)
│   ├── processed/                 # structured extraction outputs (JSON)
│   └── knowledge_graph/           # graphml + json + IR
├── compiler/
│   ├── core/                      # vendored SDK engine (registry, orchestrator,
│   │                              #   artifacts, diagnostics, evaluation, inference)
│   ├── passes/                    # pass-01..pass-07 (declarative YAML + run.py)
│   ├── ingest/  analysis/  generation/  evaluation/  orchestration/
│   └── run.py                     # the `researchc` CLI driver
├── generated_research/            # compiled research posts + repo scaffolds
├── templates/
│   └── research_post_template.md  # the canonical 11-section post shape
├── experiments/                   # logs of generated ideas / ablations
├── agents/
│   └── self_improvement.md        # capability ledger (recursive loop writes here)
├── config/                        # runtime config (model, ports, thresholds)
└── docs/
    └── sdk_integration_plan.md    # how this extends the Knowledge Compiler SDK
```

---

## The six-phase plan

1. **Learn from existing writing** — `style_model.md` + per-article extraction. ✅ done
2. **Build knowledge graph** — NetworkX graph with typed edges + gap edges. ✅ done
3. **Research generation agent** — `pass-05` fills the 11-section template. 🔌 model
4. **Repository generation** — `pass-06` turns ideas into software. 🔌 model
5. **Self-improvement loop** — `pass-07` + `loop.py` maintain the capability ledger. 🔌 model
6. **Observability** — 9-dimension evaluation per artifact (inherited from SDK). ✅

Legend: ✅ deterministic & verified · 🔌 requires `--local` inference server.

---

## Operating principle

> The input is raw human research. The output is compiled knowledge containing
> understanding, reasoning, implementation, software, documentation, and future
> research directions. The system becomes increasingly capable by learning from
> every artifact it creates.

This is the same discipline the Knowledge Compiler SDK applies to Markdown,
pointed reflexively at research itself: **the compiler that compiles knowledge
can also compile the next version of its own research.**
