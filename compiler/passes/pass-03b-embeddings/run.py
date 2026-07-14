#!/usr/bin/env python3
"""pass-03b-embeddings entrypoint (model-required: embeddings only).

The compiler's own self-improvement pass proposed this capability: move gap
ranking from lexical co-occurrence to *semantic* distance. This pass embeds the
corpus's controlled vocabulary (concepts) with a local embedding model
(Ollama ``nomic-embed-text`` by default, since the Orinth chat server exposes no
embeddings endpoint), then finds the strongest research gaps:

    high semantic affinity  +  low/zero co-occurrence
    = two ideas that *belong* together but were never co-developed.

This is a more faithful "what research should exist next?" signal than raw
co-occurrence, because it captures latent conceptual closeness the author's tag
graph never made explicit.

Writes ``embeddings-ir`` with:
  * per-concept embedding metadata (model, dim, count),
  * the top semantic neighbours per concept,
  * ``semantic_gaps``: pairs ranked by affinity*(1-co_occurrence_norm),
  * ``reranked_hypotheses``: the gap-analysis hypotheses, re-scored.

Invocation (the orchestrator supplies these for a model_required pass):
    python run.py <build_dir> --port 8080 [--model NAME]
        [--embed-model nomic-embed-text:latest] [--timeout N] [--max-tokens N]
"""

from __future__ import annotations

import math
import os
import sys
from itertools import combinations

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
for _p in (_REPO, os.path.join(_REPO, "compiler")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import (  # noqa: E402
    DiagnosticEmitter,
    write_artifact,
    write_evaluation,
    evaluate_artifact,
)
from core.artifacts import ArtifactStore  # noqa: E402
from core.inference import InferenceClient  # noqa: E402
from core.llm_pass import parse_port_model  # noqa: E402

PRODUCES = "embeddings-ir"
CONSUMES = ["knowledge-extraction-ir", "gap-analysis-ir"]

# How many top vocabulary concepts to embed. Embeddings are cheap but we keep
# this bounded so the pass stays fast on CPU-bound Ollama.
MAX_CONCEPTS = 60
TOP_NEIGHBOURS = 6
TOP_GAPS = 40


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _norm_concept(s: str) -> str:
    """Normalise a concept label so morphological variants collapse.

    'knowledge-graphs', 'knowledge graph', 'Knowledge Graphs' -> 'knowledge graph'.
    Used to drop near-duplicate pairs that are the *same* idea, not a gap.
    """
    s = s.lower().strip()
    s = s.replace("-", " ").replace("_", " ")
    s = " ".join(s.split())
    # crude singularisation of the last token
    words = s.split()
    if words and words[-1].endswith("s") and len(words[-1]) > 3:
        words[-1] = words[-1][:-1]
    return " ".join(words)


# Above this cosine, two labels are effectively the same term (variant/synonym),
# not a research gap worth generating a post about. Tuned for nomic-embed-text,
# where morphological variants sit ~0.90-0.99 and genuinely distinct-but-related
# ideas (e.g. "reinforcement-learning" x "ai-agents") sit ~0.75-0.85.
SYNONYM_CEILING = 0.88


def main() -> int:
    ns = parse_port_model(sys.argv[1:])
    build_dir = ns.build_dir
    store = ArtifactStore(build_dir)

    if not store.has("knowledge-extraction-ir"):
        print("error: knowledge-extraction-ir missing; run pass-02 first",
              file=sys.stderr)
        return 1
    ke = store.read("knowledge-extraction-ir")
    ga = store.read("gap-analysis-ir") if store.has("gap-analysis-ir") else {}

    index = ke.get("corpus_index", {})
    raw_vocab = [v["label"] for v in index.get("vocabulary", [])]
    if len(raw_vocab) < 3:
        raw_vocab = [c["label"] for c in index.get("top_concepts", [])]
    # Collapse morphological variants (knowledge-graphs / knowledge graph) so the
    # gap ranker compares *distinct ideas*, not spelling variants.
    vocab = []
    seen_norm = set()
    for label in raw_vocab:
        n = _norm_concept(label)
        if n in seen_norm:
            continue
        seen_norm.add(n)
        vocab.append(label)
        if len(vocab) >= MAX_CONCEPTS:
            break
    if len(vocab) < 3:
        print("error: not enough concepts to embed", file=sys.stderr)
        return 1

    # --- embed the concepts (Ollama; Orinth has no embeddings endpoint) -------
    client = InferenceClient(
        port=ns.port,
        model=ns.model,
        timeout=ns.timeout,
        embedding_model=ns.embed_model or "nomic-embed-text:latest",
    )
    # Give each concept a tiny bit of context so the embedding is about the
    # *topic*, not the bare token.
    texts = [f"{c} — a concept in AI systems research" for c in vocab]
    try:
        # prefer_primary=False: the chat server (Orinth) has no /embeddings,
        # and the user requires embeddings via Ollama.
        vectors = client.embeddings(texts, prefer_primary=False)
    except Exception as e:  # noqa: BLE001
        print(f"error: embedding failed: {e}", file=sys.stderr)
        return 1

    if len(vectors) != len(vocab) or not vectors or not vectors[0]:
        print("error: embedding server returned no vectors", file=sys.stderr)
        return 1
    dim = len(vectors[0])
    vec_by_concept = dict(zip(vocab, vectors))

    # --- co-occurrence lookup (normalised) ------------------------------------
    pair_co = {}
    max_co = 1
    for row in ga.get("pair_co_occurrence_top", []):
        pair = row.get("pair", [])
        if len(pair) == 2:
            c = int(row.get("count", 0))
            pair_co[frozenset((pair[0].lower(), pair[1].lower()))] = c
            max_co = max(max_co, c)

    def co_norm(a, b):
        return pair_co.get(frozenset((a.lower(), b.lower())), 0) / max_co

    # --- top semantic neighbours per concept ----------------------------------
    neighbours = {}
    for c in vocab:
        sims = []
        for other in vocab:
            if other == c:
                continue
            sims.append((other, round(_cosine(vec_by_concept[c],
                                               vec_by_concept[other]), 4)))
        sims.sort(key=lambda x: x[1], reverse=True)
        neighbours[c] = [{"concept": o, "similarity": s}
                         for o, s in sims[:TOP_NEIGHBOURS]]

    # --- semantic gaps: close in meaning, far in co-occurrence ----------------
    semantic_gaps = []
    for a, b in combinations(vocab, 2):
        if _norm_concept(a) == _norm_concept(b):
            continue  # same idea, different spelling
        sim = _cosine(vec_by_concept[a], vec_by_concept[b])
        if sim <= 0 or sim >= SYNONYM_CEILING:
            continue  # unrelated, or effectively synonyms
        cn = co_norm(a, b)
        # gap score: high similarity, low co-occurrence.
        gap_score = sim * (1.0 - cn)
        semantic_gaps.append({
            "connects": [a, b],
            "similarity": round(sim, 4),
            "co_occurrence_norm": round(cn, 4),
            "gap_score": round(gap_score, 4),
        })
    semantic_gaps.sort(key=lambda g: g["gap_score"], reverse=True)
    # The most interesting gaps are semantically close (sim high) yet unlinked.
    top_semantic_gaps = [g for g in semantic_gaps
                         if g["similarity"] >= 0.5][:TOP_GAPS]
    if not top_semantic_gaps:  # relax if the embedding space is flat
        top_semantic_gaps = semantic_gaps[:TOP_GAPS]

    # --- re-rank the gap-analysis hypotheses with the semantic signal ---------
    reranked = []
    for h in ga.get("candidate_hypotheses", []):
        connects = [c.lower() for c in h.get("connects", [])]
        if len(connects) == 2 and _norm_concept(connects[0]) == _norm_concept(connects[1]):
            continue  # skip morphological-variant "gaps"
        sim = 0.0
        if len(connects) == 2 and connects[0] in vec_by_concept and \
                connects[1] in vec_by_concept:
            sim = _cosine(vec_by_concept[connects[0]],
                          vec_by_concept[connects[1]])
        if sim >= SYNONYM_CEILING:
            continue
        base = float(h.get("priority", 0.5))
        # blend the lexical priority with semantic affinity
        new_priority = round(0.5 * base + 0.5 * sim, 4)
        item = dict(h)
        item["semantic_similarity"] = round(sim, 4)
        item["priority"] = new_priority
        reranked.append(item)
    reranked.sort(key=lambda h: h["priority"], reverse=True)

    ir = {
        "schema_version": "1.0",
        "embedding_model": client.embedding_model,
        "embedding_dim": dim,
        "concept_count": len(vocab),
        "concepts": vocab,
        "neighbours": neighbours,
        "semantic_gaps": top_semantic_gaps,
        "reranked_hypotheses": reranked[:TOP_GAPS],
        "top_semantic_gap": top_semantic_gaps[0] if top_semantic_gaps else None,
    }

    emitter = DiagnosticEmitter(PRODUCES, build_dir)
    if dim < 128:
        emitter.warning("LOW_DIM_EMBEDDING",
                        f"embedding dim {dim} is unusually small")
    if not top_semantic_gaps:
        emitter.info("NO_SEMANTIC_GAPS", "no semantic gaps above threshold")
    emitter.write()

    meta = write_artifact(
        build_dir, PRODUCES, ir, pass_id="pass-03b-embeddings",
        source_artifacts=CONSUMES, schema_id=PRODUCES,
    )
    ev = evaluate_artifact(
        PRODUCES, ir, meta,
        hints={"coverage": 1.0, "traceability": 1.0, "reproducibility": 0.9,
               "consistency": 1.0, "hallucination": 0.0},
    )
    write_evaluation(build_dir, PRODUCES, ev)
    print(f"info: embedded {len(vocab)} concepts (dim={dim}); "
          f"{len(top_semantic_gaps)} semantic gaps; "
          f"top gap: {ir['top_semantic_gap']['connects'] if ir['top_semantic_gap'] else None}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
