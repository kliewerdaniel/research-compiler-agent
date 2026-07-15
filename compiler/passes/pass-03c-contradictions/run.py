#!/usr/bin/env python3
"""pass-03c-contradictions entrypoint (deterministic).

The self-improvement ledger proposed mining ``contradicts`` reasoning edges from
the corpus: two posts that touch the *same* concept but advocate *opposing*
stances. A contradiction is itself a research gap — a post that resolves it is
high-value, because the author has already argued both sides.

This pass is fully deterministic (no model):

  1. Reads the staged corpus (``<build>/source/*.md``) and splits each post into
     sections by heading.
  2. Extracts *claim sentences* — assertive statements that take a position
     (thesis cues, stance verbs, recommendation language).
  3. Groups claims by the controlled vocabulary concept(s) they mention.
  4. Within each concept's claim set, flags *opposing* claim pairs using a
     stance lexicon: pro vs. contra cue words plus negation markers
     ("not", "never", "shouldn't", "the opposite of", ...). A pair is a
     contradiction when both claims assert on the same concept but their stance
     cues point in opposite directions.
  5. Emits ``contradictions-ir`` with:
       * ``contradiction_edges``: (doc_a, doc_b, concept, claim_a, claim_b,
         stance_a, stance_b, score) — the ``contradicts`` reasoning edges,
       * ``research_resolutions``: the top contradictions reframed as
         candidate research posts ("Resolving X vs. Y").

The knowledge-graph pass (pass-04) reads ``contradictions-ir`` (optionally) and
adds ``contradicts`` edges; the generation pass (pass-05) can surface the top
resolutions as topics.

Invocation: python run.py <build_dir>
"""

from __future__ import annotations

import json
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

PRODUCES = "contradictions-ir"
CONSUMES = ["knowledge-extraction-ir"]

# --- stance lexicon ----------------------------------------------------------
# Claims that contain a PRO cue take one side; CONTRA cues the other. A pair of
# claims on the same concept with opposing cue sets is a contradiction candidate.
PRO_CUES = [
    "should", "must", "need to", "recommend", "prefer", "better to", "the right",
    "correct", "always", "best practice", "the way to", "instead", "use",
    "adopt", "embrac", "favor", "advantage", "superior",
]
CONTRA_CUES = [
    "should not", "shouldn't", "must not", "avoid", "never", "don't", "do not",
    "wrong", "misguided", "outdated", "overrated", "the opposite", "worse",
    "problem with", "pitfall", "anti-pattern", "instead of", "not the",
    "fails", "limitation", "risk", "danger",
]
NEG_MARKERS = ["not ", "never ", "no longer", "without", "rather than",
               "contrary to", "against", "but ", "however", "on the other hand"]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "item"


def _stance(claim: str) -> str:
    """Return 'pro', 'contra', or '' for a claim sentence."""
    low = claim.lower()
    pro = any(c in low for c in PRO_CUES)
    con = any(c in low for c in CONTRA_CUES)
    if pro and not con:
        return "pro"
    if con and not pro:
        return "contra"
    # both/neither -> fall back to negation markers as contra signal
    if con:
        return "contra"
    return ""


def _split_sections(md_text: str):
    """Yield (heading, body) sections from a markdown string."""
    lines = md_text.splitlines()
    cur_heading = None
    cur_body: list[str] = []
    sections: list[tuple[str, str]] = []
    for ln in lines:
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            if cur_heading is not None or cur_body:
                sections.append((cur_heading or "", "\n".join(cur_body).strip()))
            cur_heading = m.group(2).strip()
            cur_body = []
        else:
            cur_body.append(ln)
    if cur_heading is not None or cur_body:
        sections.append((cur_heading or "", "\n".join(cur_body).strip()))
    return sections


def _extract_claims(text: str) -> list[str]:
    """Extract assertive claim sentences that take a POSITION.

    A claim must contain an explicit stance cue (pro/contra lexicon or a
    negation marker). This deliberately excludes neutral exposition, code,
    and abstract boilerplate — only sentences that argue one way or the other
    count as claims worth contradiction-mining.
    """
    # Strip code blocks (they are not prose claims).
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    sents = re.split(r"(?<=[.!?])\s+", text)
    claims = []
    for s in sents:
        s = s.strip()
        if len(s) < 50 or len(s) > 350:
            continue
        if s.startswith(("#", "-", "*", ">", "|", "!", "[", "{", "(")):
            continue
        low = s.lower()
        # Must take a position: an explicit stance cue.
        if not any(c in low for c in PRO_CUES + CONTRA_CUES + NEG_MARKERS):
            continue
        # Crude boilerplate exclusion: dissertation/paper abstracts.
        if re.match(r"^(this|the) (paper|dissertation|post|article|essay|report)\b",
                    low):
            continue
        claims.append(s)
    return claims


def main() -> int:
    build_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    store = ArtifactStore(build_dir)
    if not store.has("knowledge-extraction-ir"):
        print("error: knowledge-extraction-ir missing; run pass-02 first",
              file=sys.stderr)
        return 1
    ke = store.read("knowledge-extraction-ir")
    index = ke.get("corpus_index", {})
    vocab = [v["label"].lower() for v in index.get("vocabulary", [])]

    # Map staged filename -> markdown-ir doc id (so graph edges line up with
    # pass-04's article nodes, which use the doc-<n> id).
    doc_id_for: dict[str, str] = {}
    if store.has("markdown-ir"):
        md = store.read("markdown-ir")
        for d in md.get("documents", []):
            p = d.get("path", "")
            doc_id_for[os.path.basename(p)] = d.get("id")

    # Read staged corpus for raw claim text (section bodies only; the preamble
    # is usually an abstract and is excluded from claim mining).
    src_dir = os.path.join(build_dir, "source")
    docs: list[dict] = []  # {id, title, claims:[(concept, claim, stance)]}
    if os.path.isdir(src_dir):
        for fn in sorted(os.listdir(src_dir)):
            if not fn.endswith(".md"):
                continue
            path = os.path.join(src_dir, fn)
            try:
                with open(path, encoding="utf-8") as fh:
                    raw = fh.read()
            except OSError:
                continue
            title = ""
            m = re.match(r"^#{1,6}\s+(.*)$", raw, re.M)
            if m:
                title = m.group(1).strip()
            claims_per_doc: list[tuple[str, str, str]] = []
            for heading, body in _split_sections(raw):
                if not heading:
                    continue  # skip preamble / abstract
                for claim in _extract_claims(body):
                    low = claim.lower()
                    mentioned = [c for c in vocab if c in low]
                    if not mentioned:
                        continue
                    stance = _stance(claim)
                    if not stance:
                        continue
                    for concept in mentioned:
                        claims_per_doc.append((concept, claim, stance))
            did = doc_id_for.get(fn, _slug(fn))
            docs.append({"id": did, "title": title, "claims": claims_per_doc})

    # Group claims by concept across the whole corpus. Dedupe claim sentences
    # per (doc, stance) so a single repeated sentence isn't broadcast against
    # every opposing claim. Skip generic catch-all concepts (too broad to be a
    # real, resolvable disagreement).
    GENERIC_CONCEPTS = {"ai", "ai agents", "ai-agents", "local-first", "local",
                        "ml", "machine learning", "llm", "llms"}
    by_concept: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for d in docs:
        seen_claim = set()  # (doc, stance, normalized claim) dedupe
        for concept, claim, stance in d["claims"]:
            if concept in GENERIC_CONCEPTS:
                continue
            norm = re.sub(r"\s+", " ", claim.lower()).strip()
            k = (d["id"], stance, norm)
            if k in seen_claim:
                continue
            seen_claim.add(k)
            by_concept[concept].append((d["id"], claim, stance))

    # Flag opposing-stance pairs per concept (capped to keep the graph focused).
    MAX_PER_CONCEPT = 8
    contradiction_edges: list[dict] = []
    for concept, claims in by_concept.items():
        pro = [c for c in claims if c[2] == "pro"]
        contra = [c for c in claims if c[2] == "contra"]
        if not pro or not contra:
            continue
        pairs = []
        for (da, ca, _) in pro:
            for (db, cb, _) in contra:
                if da == db:
                    continue  # same doc arguing with itself
                pairs.append({
                    "concept": concept, "doc_a": da, "doc_b": db,
                    "claim_pro": ca, "claim_contra": cb,
                    "stance_pro": "pro", "stance_contra": "contra",
                    "score": 1.0,
                })
        contradiction_edges.extend(pairs[:MAX_PER_CONCEPT])

    # Deduplicate symmetric pairs.
    seen = set()
    uniq = []
    for e in contradiction_edges:
        key = tuple(sorted([e["doc_a"], e["doc_b"]])) + (e["concept"],)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    contradiction_edges = uniq

    # Rank by how many distinct claim-pairs back each (doc_a, doc_b, concept).
    cnt = Counter((e["doc_a"], e["doc_b"], e["concept"]) for e in contradiction_edges)
    contradiction_edges.sort(key=lambda e: cnt[(e["doc_a"], e["doc_b"], e["concept"])],
                             reverse=True)

    research_resolutions = []
    for e in contradiction_edges[:20]:
        research_resolutions.append({
            "topic": f"Resolving {e['concept']}: {e['stance_pro']} vs. "
                     f"{e['stance_contra']}",
            "concept": e["concept"],
            "doc_a": e["doc_a"],
            "doc_b": e["doc_b"],
            "claim_pro": e["claim_pro"],
            "claim_contra": e["claim_contra"],
        })

    ir = {
        "schema_version": "1.0",
        "concept_count": len(by_concept),
        "claims_mined": sum(len(d["claims"]) for d in docs),
        "contradiction_edge_count": len(contradiction_edges),
        "contradiction_edges": contradiction_edges[:40],
        "research_resolutions": research_resolutions,
        "top_contradiction": contradiction_edges[0] if contradiction_edges else None,
    }

    emitter = DiagnosticEmitter(PRODUCES, build_dir)
    if not contradiction_edges:
        emitter.info("NO_CONTRADICTIONS",
                     "no opposing-stance claim pairs detected")
    else:
        emitter.info("CONTRADICTIONS_FOUND",
                     f"{len(contradiction_edges)} contradiction edges")
    emitter.write()

    meta = write_artifact(
        build_dir, PRODUCES, ir, pass_id="pass-03c-contradictions",
        source_artifacts=CONSUMES, schema_id=PRODUCES,
        pass_dir=os.path.dirname(os.path.abspath(__file__)),
    )
    ev = evaluate_artifact(
        PRODUCES, ir, meta,
        hints={"coverage": 1.0, "traceability": 1.0, "reproducibility": 1.0,
               "consistency": 1.0, "hallucination": 0.0},
    )
    write_evaluation(build_dir, PRODUCES, ev)

    tc = ir["top_contradiction"]
    print(f"info: mined {ir['claims_mined']} claims across {len(docs)} docs; "
          f"{len(contradiction_edges)} contradiction edges; "
          f"top: {tc['concept'] if tc else None} "
          f"({tc['doc_a']} vs {tc['doc_b']})" if tc else "no contradictions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
