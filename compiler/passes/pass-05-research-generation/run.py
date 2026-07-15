#!/usr/bin/env python3
"""pass-05-research-generation entrypoint (model-required).

Selects the highest-priority research gap, gathers supporting context from the
knowledge graph + style model, and asks the local model to produce a complete
research artifact that reproduces the corpus's house voice. Writes
research-generation-ir (a structured artifact: the markdown + metadata).

Runs against the user's local inference server via --local.

Invocation: python run.py <build_dir> [--port 8080] [--model NAME]
"""

from __future__ import annotations

import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from core.llm_pass import parse_port_model, run_model_pass

PRODUCES = "research-generation-ir"
CONSUMES = ["gap-analysis-ir", "knowledge-graph-ir", "style-model-ir",
            "research-debt-ir"]


def build_user_prompt(inputs: dict) -> str:
    ga = inputs.get("gap-analysis-ir", {})
    kg = inputs.get("knowledge-graph-ir", {})
    style = inputs.get("style-model-ir", {})

    # Prefer the semantically re-ranked hypotheses from pass-03b-embeddings when
    # that artifact is present (it is produced only on --local runs). This is the
    # embedding path: gaps ranked by semantic affinity vs. co-occurrence, not
    # lexical co-occurrence alone. Fall back to the deterministic gap analysis.
    hypotheses = []
    gap_source = "gap-analysis (lexical)"
    emb = inputs.get("embeddings-ir")
    if emb is None:
        # opportunistically read it from the build store if the orchestrator
        # did not pass it as a hard input.
        try:
            import os as _os
            from core.artifacts import ArtifactStore as _AS
            _bd = inputs.get("__build_dir__")
            if _bd and _os.path.isdir(_bd):
                _store = _AS(_bd)
                if _store.has("embeddings-ir"):
                    emb = _store.read("embeddings-ir")
        except Exception:
            emb = None
    if isinstance(emb, dict) and emb.get("reranked_hypotheses"):
        hypotheses = emb["reranked_hypotheses"]
        gap_source = f"embeddings-reranked ({emb.get('embedding_model')})"
    if not hypotheses:
        hypotheses = ga.get("candidate_hypotheses", [])
    top = hypotheses[0] if hypotheses else None
    if not top:
        return "No research gaps available. Return {\"skip\": true}."

    # Gather graph context around the connected concepts.
    connects = [c.lower() for c in top.get("connects", [])]
    related = []
    for e in kg.get("edges", []):
        s = e.get("source", "").split(":", 1)[-1]
        t = e.get("target", "").split(":", 1)[-1]
        if any(c in s or c in t for c in connects):
            related.append({"source": s, "target": t, "type": e.get("type")})
    related = related[:25]

    style_rules = style.get("derived_rules", [])
    tone = style.get("tone_profile", {}).get("documentation_observations", [])

    # Opportunistically surface top contradictions as resolution topics. A
    # contradiction is a high-value research direction: the corpus already
    # argues both sides, so a post that resolves it is well-grounded.
    resolutions = []
    ctr = inputs.get("contradictions-ir")
    if not isinstance(ctr, dict):
        try:
            from core.artifacts import ArtifactStore as _AS
            _bd = inputs.get("__build_dir__")
            if _bd:
                _store = _AS(_bd)
                if _store.has("contradictions-ir"):
                    ctr = _store.read("contradictions-ir")
        except Exception:
            ctr = None
    if isinstance(ctr, dict):
        for r in ctr.get("research_resolutions", [])[:5]:
            resolutions.append({
                "topic": r.get("topic"),
                "concept": r.get("concept"),
                "claim_pro": r.get("claim_pro"),
                "claim_contra": r.get("claim_contra"),
            })

    # Opportunistically surface the top research-debt consolidation proposals.
    # A consolidation proposal is a well-grounded "write this post" topic
    # (deepen a thin post, develop an under-explored concept, consolidate an
    # orphan topic) — ideal research directions because the corpus already
    # signals the gap. Surfaced so the model can prefer them when grounded.
    debt_proposals = []
    debt_concepts = []
    debt_score = None
    rd = inputs.get("research-debt-ir")
    if not isinstance(rd, dict):
        try:
            from core.artifacts import ArtifactStore as _AS
            _bd = inputs.get("__build_dir__")
            if _bd:
                _store = _AS(_bd)
                if _store.has("research-debt-ir"):
                    rd = _store.read("research-debt-ir")
        except Exception:
            rd = None
    if isinstance(rd, dict):
        debt_score = rd.get("debt_score")
        for p in sorted(rd.get("consolidation_proposals", []),
                        key=lambda x: x.get("priority", 0), reverse=True)[:8]:
            debt_proposals.append({
                "type": p.get("type"),
                "topic": p.get("topic"),
                "doc_id": p.get("doc_id"),
                "priority": p.get("priority"),
                "rationale": p.get("rationale"),
            })
        for c in rd.get("debt_concepts", [])[:8]:
            debt_concepts.append({
                "concept": c.get("concept"),
                "mentions": c.get("mentions"),
                "reason": c.get("reason"),
            })

    payload = {
        "chosen_hypothesis": top,
        "gap_ranking_source": gap_source,
        "supporting_graph_edges": related,
        "unanswered_questions_sample": [
            q.get("text") for q in ga.get("unanswered_questions", [])[:12]
        ],
        "contradiction_resolutions": resolutions,
        "research_debt": {
            "debt_score": debt_score,
            "consolidation_proposals": debt_proposals,
            "under_explored_concepts": debt_concepts,
        },
        "style_rules": style_rules,
        "tone_notes": tone,
    }
    return (
        "RESEARCH COMPILER GENERATION TASK\n\n"
        "Produce a complete research artifact (Markdown) for the chosen "
        "research hypothesis. It must reproduce the house voice exactly.\n\n"
        "Context (structured):\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n\nReturn JSON: {\"title\":str, \"slug\":str, \"abstract\":str, "
        "\"sections\":[{\"heading\":str,\"body\":str}], \"tags\":[str], "
        "\"references\":[str], \"next_steps\":[str], \"potential_projects\":[str], "
        "\"becomes_software\":bool, \"repo_idea\":str}.\n"
        "The 'sections' MUST follow the canonical structure: "
        "Abstract, The Problem, Existing Approaches, New Concept, Architecture, "
        "Implementation, Code Repository, Experiments, Applications, Future Work, "
        "Conclusion. Each body paragraph >= 120 words. Every claim must be "
        "traceable to the provided graph edges or stated as a hypothesis. "
        "RESEARCH-DEBT STEERING (required when `research_debt.debt_score` > 0): "
        "You MUST address the corpus's accumulated debt. Select the highest-"
        "priority `consolidation_proposals` entry whose `topic` or `doc_id` is "
        "traceable to the provided graph edges, and write the post to resolve it "
        "(deepen a thin post, develop an under-explored concept, or consolidate an "
        "orphan topic). Do NOT default to `chosen_hypothesis` unless no debt "
        "proposal is graph-grounded. In `abstract` and the first section, name the "
        "specific `consolidation_proposals` entry you are addressing and quote its "
        "`rationale`. This makes the post a direct repayment of research debt. "
        "Respond with JSON only."
    )


SYSTEM_PROMPT = """You are the Research Generation compiler pass of an autonomous
research compiler. You turn compiled knowledge (a knowledge graph + gap
analysis + style model) into a new, publishable research post that sounds
exactly like the corpus author: thesis-first, names a failure in the status
quo, resolves it with an inspectable artifact, uses comparison tables, and
ends with forward pointers. Never invent facts not grounded in the provided
graph edges; mark inferences as hypotheses. OUTPUT JSON ONLY."""


def main() -> int:
    ns = parse_port_model(sys.argv[1:])
    return run_model_pass(
        build_dir=ns.build_dir,
        produces=PRODUCES,
        consumes=CONSUMES,
        system_prompt=SYSTEM_PROMPT,
        user_prompt_fn=build_user_prompt,
        port=ns.port,
        model=ns.model,
        timeout=ns.timeout,
        max_tokens=ns.max_tokens,
        prompt_file=os.path.join(os.path.dirname(__file__), "prompt.md"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
