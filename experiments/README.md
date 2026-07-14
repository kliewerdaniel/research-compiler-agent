<!-- Experiment log. Each generated research direction / ablation gets an entry.
     The self-improvement loop reads these to track what worked and what didn't. -->

# Experiment Log

## 2026-07-14 — Baseline deterministic pipeline
- Ran `pass-01`..`pass-04` over 152 posts (no model).
- Result: 326-node / 1276-edge NetworkX graph, 39 gap edges, 40 ranked research directions.
- Top direction: "Synthesizing memory with agent" (co-occurrence = 0).
- Rendered `generated_research/brief-memory-agent.md` as a deterministic fallback brief.
- Observation: frontmatter tag parsing required handling both YAML flow lists
  (`[a, b]`) and block lists (`- a\n- b`); section-heading noise had to be
  filtered from the concept universe in favour of the author's controlled
  vocabulary (tags + wiki_references).
- Next: run `pass-05..pass-07` with `--local` once a llama.cpp/Ollama server is up.
