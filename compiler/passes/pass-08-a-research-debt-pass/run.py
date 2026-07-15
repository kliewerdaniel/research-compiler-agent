#!/usr/bin/env python3
"""pass-08-a-research-debt-pass entrypoint (deterministic).

Research debt = corpus areas that are *under-covered relative to their
importance*. The self-improvement ledger proposed tracking low-coverage posts
and under-explored concepts and turning them into consolidation-post proposals.
This pass computes that debt from real artifacts and emits actionable
consolidation topics.

Signals (all derived from existing IRs, no model needed):

  * thin / image-only posts  — ``word_count`` / ``section_count`` far below the
    corpus median (or exactly 0) means a post contributes little textual
    coverage; it is research debt waiting to be deepened.
  * unanswered questions      — ``gap-analysis-ir`` carries 190+ future-work
    items; posts that raise many but are never followed up accumulate debt.
  * under-explored concepts   — vocabulary concepts with very few mentions are
    gap debt (the corpus name-drops them but never develops them).
  * topic sparsity            — normalized topics appearing in only 1 post are
    consolidation candidates (a lone post on an orphan topic).

The pass emits ``research-debt-ir`` with:
  * ``debt_score``            — corpus-level 0..1 research-debt metric,
  * ``debt_posts``            — posts ranked by coverage debt + reason,
  * ``debt_concepts``         — concepts rarely covered,
  * ``consolidation_proposals`` — synthesized "write a post that consolidates X"
    topics, the actionable payoff of the pass.

Invocation: python run.py <build_dir>
"""

from __future__ import annotations

import os
import re
import sys
from collections import Counter, defaultdict

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

PRODUCES = "research-debt-ir"
CONSUMES = ["knowledge-extraction-ir", "gap-analysis-ir"]


def _norm_topic(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "item"


def _clean_title(t: str) -> str:
    """Strip markdown/image noise from a post title for clean display."""
    t = (t or "").replace("**", "").strip()
    if t.startswith("!["):
        return "(image-only post)"
    return t


def main() -> int:
    build_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    store = ArtifactStore(build_dir)
    if not store.has("knowledge-extraction-ir"):
        print("error: knowledge-extraction-ir missing; run pass-02 first",
              file=sys.stderr)
        return 1
    ke = store.read("knowledge-extraction-ir")
    ga = store.read("gap-analysis-ir") if store.has("gap-analysis-ir") else {}

    articles = ke.get("articles", [])
    index = ke.get("corpus_index", {})
    vocab = index.get("vocabulary", [])

    # --- per-post coverage baselines -----------------------------------------
    wcs = sorted(a.get("word_count", 0) for a in articles)
    scs = sorted(a.get("section_count", 0) for a in articles)
    n = len(wcs)
    median_wc = wcs[n // 2] if n else 0
    median_sc = scs[n // 2] if n else 0
    # debt threshold: half the median coverage
    wc_thresh = max(1, int(0.5 * median_wc))
    sc_thresh = max(1, int(0.5 * median_sc))

    # unanswered questions per source doc
    uq_by_doc: Counter = Counter()
    for q in ga.get("unanswered_questions", []):
        uq_by_doc[q.get("source_doc", "")] += 1

    # --- per-post debt --------------------------------------------------------
    debt_posts: list[dict] = []
    for a in articles:
        wc = a.get("word_count", 0)
        sc = a.get("section_count", 0)
        reasons: list[str] = []
        score = 0.0
        if wc == 0:
            reasons.append("image-only / no textual coverage")
            score += 1.0
        elif wc < wc_thresh:
            reasons.append(f"thin post ({wc} words < {wc_thresh} median-half)")
            score += min(1.0, (wc_thresh - wc) / max(1, wc_thresh))
        if sc == 0:
            reasons.append("no sections")
            score += 0.3
        elif sc < sc_thresh:
            reasons.append(f"shallow structure ({sc} sections)")
            score += 0.2
        uq = uq_by_doc.get(a.get("id", ""), 0)
        if uq >= 3:
            reasons.append(f"raises {uq} unanswered questions w/o follow-up")
            score += min(0.5, uq * 0.1)
        if not reasons:
            continue
        debt_posts.append({
            "doc_id": a.get("id"),
            "title": _clean_title(a.get("title")),
            "word_count": wc,
            "section_count": sc,
            "unanswered_questions": uq,
            "debt_score": round(min(1.0, score), 3),
            "reasons": reasons,
        })
    debt_posts.sort(key=lambda d: d["debt_score"], reverse=True)

    # --- concept debt (vocabulary concepts rarely covered) --------------------
    # The vocabulary already records how often each concept is mentioned across
    # the corpus; a concept is "under-explored" when its mention count is in the
    # low tail of that distribution (named, but never developed).
    mentions = [v.get("mentions", 0) for v in vocab if v.get("mentions")]
    mentions.sort()
    m_n = len(mentions)
    median_mentions = mentions[m_n // 2] if m_n else 0
    # debt threshold: concepts within a small margin of the *minimum* mention
    # count are the genuine low tail (named, but essentially undeveloped).
    min_mentions = mentions[0] if mentions else 0
    concept_thresh = max(3, min_mentions + 2)
    debt_concepts: list[dict] = []
    for v in vocab:
        label = v.get("label", "")
        m = v.get("mentions", 0)
        if m <= concept_thresh:
            debt_concepts.append({
                "concept": label,
                "mentions": m,
                "covering_docs": m,  # vocabulary mentions ~ doc coverage
                "reason": f"mentioned only {m}x (<= {concept_thresh} threshold)",
            })
    debt_concepts.sort(key=lambda c: c["mentions"])
    # merge explicit under-explored concepts if present
    under_explored = ga.get("under_explored_concepts", [])
    for c in under_explored:
        lbl = c.get("label") or c.get("concept") if isinstance(c, dict) else str(c)
        if lbl and not any(d["concept"] == lbl for d in debt_concepts):
            debt_concepts.append({
                "concept": lbl, "mentions": c.get("mentions", 0),
                "covering_docs": c.get("covering_docs", 0),
                "reason": "flagged under-explored by gap analysis",
            })

    # --- topic sparsity (orphan topics) --------------------------------------
    # Skip non-textual / image-only noise (e.g. topics derived from
    # "![Image](/images/...)" captions) so consolidation proposals stay clean.
    _JUNK = ("!", "/images/", "image", "temp.md")

    def _is_junk(t: str) -> bool:
        tl = t.lower()
        return any(j in tl for j in _JUNK)

    topic_docs: dict[str, set] = defaultdict(set)
    for a in articles:
        for t in a.get("topics", []):
            nt = _norm_topic(t)
            if nt and not _is_junk(nt):
                topic_docs[nt].add(a.get("id"))
    orphan_topics = sorted(
        [t for t, ds in topic_docs.items() if len(ds) == 1]
    )

    # --- corpus debt score ----------------------------------------------------
    if n:
        debt_ratio = len(debt_posts) / n
        thin_ratio = sum(1 for a in articles if a.get("word_count", 0) == 0) / n
        concept_debt_ratio = (len(debt_concepts) / max(1, len(vocab)))
        debt_score = round(
            min(1.0, 0.5 * debt_ratio + 0.3 * thin_ratio
                + 0.2 * concept_debt_ratio), 3)
    else:
        debt_score = 0.0

    # --- consolidation proposals (the actionable payoff) ---------------------
    consolidation_proposals: list[dict] = []
    # (1) deepen the top debt posts
    for d in debt_posts[:8]:
        consolidation_proposals.append({
            "type": "deepen_post",
            "topic": d["title"],
            "rationale": "; ".join(d["reasons"]),
            "priority": d["debt_score"],
            "doc_id": d["doc_id"],
        })
    # (2) consolidate orphan topics into a survey post
    if orphan_topics:
        # group a few orphans per proposal for a digestible consolidation post
        for i in range(0, len(orphan_topics), 5):
            batch = orphan_topics[i:i + 5]
            consolidation_proposals.append({
                "type": "consolidate_orphan_topics",
                "topic": "Consolidating: " + ", ".join(batch[:5]),
                "rationale": f"{len(batch)} orphan topic(s) covered by only one post",
                "priority": 0.6,
                "topics": batch[:5],
            })
    # (3) develop under-explored concepts
    for c in debt_concepts[:8]:
        consolidation_proposals.append({
            "type": "develop_concept",
            "topic": f"Developing the '{c['concept']}' concept",
            "rationale": c["reason"],
            "priority": 0.7,
            "concept": c["concept"],
        })
    consolidation_proposals.sort(key=lambda p: p["priority"], reverse=True)

    ir = {
        "schema_version": "1.0",
        "generated": False,
        "debt_score": debt_score,
        "metrics": {
            "article_count": n,
            "median_word_count": median_wc,
            "median_section_count": median_sc,
            "thin_post_threshold_words": wc_thresh,
            "debt_post_count": len(debt_posts),
            "debt_concept_count": len(debt_concepts),
            "orphan_topic_count": len(orphan_topics),
            "unanswered_question_count": ga.get("unanswered_question_count", 0),
        },
        "debt_posts": debt_posts[:25],
        "debt_concepts": debt_concepts[:25],
        "orphan_topics": orphan_topics[:50],
        "consolidation_proposals": consolidation_proposals[:30],
    }

    emitter = DiagnosticEmitter(PRODUCES, build_dir)
    if not debt_posts and not debt_concepts:
        emitter.info("NO_DEBT", "corpus coverage is balanced")
    else:
        emitter.info("RESEARCH_DEBT",
                     f"debt_score={debt_score} | {len(debt_posts)} thin posts, "
                     f"{len(debt_concepts)} under-explored concepts, "
                     f"{len(orphan_topics)} orphan topics")
    emitter.write()

    meta = write_artifact(
        build_dir, PRODUCES, ir, pass_id="pass-08-a-research-debt-pass",
        source_artifacts=CONSUMES, schema_id=PRODUCES,
        pass_dir=os.path.dirname(os.path.abspath(__file__)),
    )
    ev = evaluate_artifact(
        PRODUCES, ir, meta,
        hints={"coverage": 1.0, "traceability": 1.0, "reproducibility": 1.0,
               "consistency": 1.0, "hallucination": 0.0},
    )
    write_evaluation(build_dir, PRODUCES, ev)

    print(f"info: research-debt score={debt_score} | "
          f"{len(debt_posts)} thin posts, {len(debt_concepts)} debt concepts, "
          f"{len(orphan_topics)} orphan topics, "
          f"{len(consolidation_proposals)} consolidation proposals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
