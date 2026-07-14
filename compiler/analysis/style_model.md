# Style Model — `compiler/analysis/style_model.md`

> This model was **compiled**, not guessed. It is derived from the deterministic
> `pass-01b-style` pass over the 152-post corpus in `corpus/source_blog_posts/`.
> Re-run `python -m compiler.run --source corpus/source_blog_posts --build build`
> to regenerate `build/style-model-ir/artifact.json` and this document.

## 1. Corpus at a glance (measured)

| Metric | Value |
|---|---|
| Documents | 152 |
| Mean words / post | ~3,899 |
| Mean sections / post | ~33 |
| % with code blocks | 79.6% |
| % long-form (≥1500w) | 65.8% |
| % multi-section (≥5) | 92.1% |
| % with frontmatter | 100% |

This is a **long-form, code-heavy, structured** corpus. The author writes
essays and engineering deep-dives, not micro-posts.

## 2. Article structure (recurring pattern)

Posts open with **YAML frontmatter** (title, slug, date, tags, wiki_references,
canonical URL) and a level-1 `# Title` that is a *thesis statement*, not a
headline. The dominant recurring section headings (by frequency across the
corpus) are:

```
conclusion, prerequisites, introduction, table of contents, explanation,
troubleshooting, references, related posts, related repositories,
install dependencies
```

The signature research-post shape (used by the generation pass) is:

```
# Title
## Abstract
## The Problem
## Existing Approaches
## New Concept
## Architecture
## Implementation
## Code Repository
## Experiments
## Applications
## Future Work
## Conclusion
```

## 3. Tone

- **Thesis-first.** Opens by naming a failure in the status quo (RAG, cloud,
  chat, telemetry-as-governance) and resolves it structurally.
- **Systems register.** Comparison tables are the default rhetorical device
  ("Software Compiler | Knowledge Compiler").
- **First person, peer-to-peer.** The reader is addressed as a fellow engineer,
  not a layperson. "I wrote…", "here's the loop…".
- **Declarative about architecture**, narrative about motivation.
- **Forward-pointing.** Every post ends with Next Steps / Future Work /
  Unanswered Questions.

## 4. Terminology (top signature terms, measured)

```
ir, agent, model, local, graph, knowledge, sovereign, rag, spec,
intelligence, memory, loop, compiler, observability, provenance, reasoning,
embedding, retrieval, ontology, evaluation
```

Recurring phrases worth reproducing:
- *"intelligence is not the model; intelligence is the accumulated, inspectable
  decisions that shape what the model produces"*
- *"observability is the OS"*
- *"the model is a subroutine; the knowledge graph is the product"*
- *"local-first by construction"*
- *"a build that fails honestly is more useful than one that succeeds by accident"*

## 5. Technical depth

79.6% of posts contain code. Dominant languages/stacks (measured from fenced
blocks + text): `python`, `bash`, `next.js`, `docker`, `fastapi`, `json`,
`chromadb`, `mcp`, `networkx`, `pydantic`, `sqlite`, `ollama`, `llama.cpp`,
`vllm`, `typescript`, `rust`.

## 6. Themes (from frontmatter tags / wiki_references)

```
ollama, python, ai-agents, rag, local-inference, knowledge-graphs, ai,
embeddings, llama3, sentence-transformers, rlhf, docker, typescript,
local-first-ai, mcp, transformers, sovereign-ai, quantization,
ai-sovereignty, data-sovereignty, llm, tutorial
```

## 7. Argument style

1. State the complaint (a systems-design failure).
2. Borrow an analogy from compilers / OS / sovereignty.
3. Show the inspectable artifact (graph, IR, app, repo).
4. Compare against the status quo in a table.
5. End with the recursive payoff: the artifact enables the *next* iteration.

## 8. Derived rules for generation (enforced by `pass-05` prompt)

1. Open by naming a failure in the status quo.
2. Resolve with an inspectable artifact or a build step.
3. Use comparison tables to make abstract claims concrete.
4. Prefer "intelligence is not the model" framing: the substrate is the product.
5. End with forward pointers (next steps, unanswered questions, future work).
6. Keep every claim traceable to a graph edge or mark it as a hypothesis.
