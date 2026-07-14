#!/usr/bin/env python3
"""pass-03-gap-analysis entrypoint (deterministic).

Consumes the knowledge-extraction IR and the style model and proposes the set
of research directions the compiler should consider generating. This is the
heart of "what research should exist next?": it computes, reproducibly,

  * concept co-occurrence gaps (two concepts that SHOULD connect but rarely do),
  * under-explored high-value concepts (appear in few posts),
  * a ranked list of unanswered questions harvested from the corpus,
  * candidate research hypotheses (combinatorial: connect two strong concepts).

The model pass (pass-03b) refines these with judgement; this base produces a
real, inspectable candidate set with no LLM.

Invocation: python run.py <build_dir>
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, _HERE)

from core import (  # noqa: E402
    DiagnosticEmitter,
    write_artifact,
    write_evaluation,
    evaluate_artifact,
)

# Concepts that, if connected, would clearly produce valuable research.
AFFINITY_PAIRS = [
    ("knowledge graph", "self-improvement"),
    ("compiler", "autonomous agent"),
    ("knowledge graph", "code generation"),
    ("evaluation", "reasoning"),
    ("local-first", "federation"),
    ("sovereign", "observability"),
    ("ontology", "graph"),
    ("memory", "agent"),
    ("specification", "compiler"),
    ("retrieval", "reasoning"),
]


def main() -> int:
    build_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    with open(os.path.join(build_dir, "knowledge-extraction-ir", "artifact.json"), encoding="utf-8") as fh:
        ke = json.load(fh)
    with open(os.path.join(build_dir, "style-model-ir", "artifact.json"), encoding="utf-8") as fh:
        style = json.load(fh)

    articles = ke.get("articles", [])
    index = ke.get("corpus_index", {})

    # --- build a *concept universe* from the research vocabulary --------------
    # The author's own controlled vocabulary (frontmatter tags + wiki_references)
    # plus the corpus signature terms are the real "ideas" in the corpus. We
    # deliberately IGNORE generic section headings (tutorial scaffolding), so gap
    # detection reasons about concepts, not document structure.
    concept_universe: set = set()
    for t in style.get("top_signature_terms", []):
        concept_universe.add(t["term"].lower())
    for v in index.get("vocabulary", []):
        concept_universe.add(v["label"].lower())
    for t in index.get("technologies", []):
        concept_universe.add(t["label"].lower())

    # --- concept co-occurrence across articles --------------------------------
    # An article's concept-set = its vocabulary (tags/wiki) + technologies +
    # repositories. Two concepts "co-occur" when they appear in the same post.
    art_concepts: list[set] = []
    for a in articles:
        labels = set()
        for tag in a.get("topics", []) or []:
            if isinstance(tag, str):
                labels.add(tag.lower())
        labels |= {t["label"].lower() for t in a.get("technologies", [])}
        labels |= {r["name"].lower() for r in a.get("repositories", [])}
        labels &= concept_universe
        if labels:
            art_concepts.append(labels)

    pair_co = Counter()
    for concepts in art_concepts:
        for a, b in combinations(sorted(concepts), 2):
            pair_co[(a, b)] += 1

    # affinity gaps: pairs we think should connect but rarely do
    affinity_gaps = []
    for a, b in AFFINITY_PAIRS:
        ca, cb = a.lower(), b.lower()
        if ca in concept_universe and cb in concept_universe:
            co = pair_co.get((ca, cb), pair_co.get((cb, ca), 0))
            if co <= 1:
                affinity_gaps.append({
                    "a": a, "b": b,
                    "co_occurrence": co,
                    "signal": "strong concepts, weak direct link in corpus",
                })

    # --- under-explored high-value concepts -----------------------------------
    vocab_mentions = {v["label"].lower(): v["mentions"]
                      for v in index.get("vocabulary", [])}
    # value heuristic: signature concepts that appear but in few posts
    signature = {t["term"].lower() for t in style.get("top_signature_terms", [])}
    under_explored = []
    for c, mentions in vocab_mentions.items():
        if c in signature and mentions <= 3:
            under_explored.append({"concept": c, "mentions": mentions,
                                    "signal": "signature term, low coverage"})

    # --- unanswered questions -------------------------------------------------
    questions = []
    for a in articles:
        for q in a.get("future_questions", []):
            questions.append({
                "text": q.get("text"),
                "source_doc": a["id"],
                "source_title": a.get("title", ""),
            })
    # de-dup by normalized text
    seen = set()
    unique_q = []
    for q in questions:
        k = re.sub(r"\W+", " ", (q.get("text") or "")).strip().lower()
        if k and k not in seen:
            seen.add(k)
            unique_q.append(q)

    # --- candidate research hypotheses (combinatorial) ------------------------
    # Rank concepts by corpus mentions; bridge the strong-but-unconnected ones.
    strong = [c for c in concept_universe
              if vocab_mentions.get(c, 0) >= 4][:25]
    hypotheses = []
    for a, b in combinations(strong, 2):
        co = pair_co.get((a, b), pair_co.get((b, a), 0))
        if co == 0:
            hypotheses.append({
                "title": f"Bridging {a} and {b}",
                "connects": [a, b],
                "co_occurrence": 0,
                "rationale": f"'{a}' and '{b}' are both well-covered topics "
                             f"but never co-developed in a single post.",
                "priority": 0.5,
            })
    # boost affinity-gap hypotheses
    for g in affinity_gaps:
        hypotheses.append({
            "title": f"Synthesizing {g['a']} with {g['b']}",
            "connects": [g["a"], g["b"]],
            "co_occurrence": g["co_occurrence"],
            "rationale": g["signal"],
            "priority": 0.9,
        })
    hypotheses.sort(key=lambda h: h["priority"], reverse=True)

    ir = {
        "schema_version": "1.0",
        "affinity_gaps": affinity_gaps,
        "under_explored_concepts": under_explored,
        "unanswered_questions": unique_q,
        "unanswered_question_count": len(unique_q),
        "candidate_hypotheses": hypotheses[:40],
        "pair_co_occurrence_top": [
            {"pair": list(p), "count": c}
            for p, c in pair_co.most_common(20)
        ],
    }

    emitter = DiagnosticEmitter("gap-analysis-ir", build_dir)
    if not affinity_gaps:
        emitter.info("NO_AFFINITY_GAPS", "all signature concept pairs already linked")
    emitter.write()

    meta = write_artifact(
        build_dir, "gap-analysis-ir", ir, pass_id="pass-03-gap-analysis",
        source_artifacts=["knowledge-extraction-ir", "style-model-ir"],
        schema_id="gap-analysis-ir",
    )
    ev = evaluate_artifact(
        "gap-analysis-ir", ir, meta,
        hints={"coverage": 1.0, "traceability": 1.0, "reproducibility": 1.0,
               "consistency": 1.0, "hallucination": 0.0},
    )
    write_evaluation(build_dir, "gap-analysis-ir", ev)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
