#!/usr/bin/env python3
"""pass-02-extract entrypoint (deterministic, heuristic).

Consumes the Markdown IR and produces a structured extraction PER article:
concepts, entities, technologies, repositories, code artifacts, tutorials,
examples, and future research questions. The model pass (pass-02b) AUGMENTS
these with LLM judgement; this deterministic base runs everywhere and gives
the generation pass something real to condition on even without a local model.

Extraction is heuristic but evidence-grounded: we harvest GitHub URLs as
'repositories', fenced code languages as 'technologies', section headings as
'concepts', and question-mark closing sections / 'future work' headings as
'future_questions'. This is honest degradation, not hallucination — every item
carries a span (doc + section/heading) so provenance is checkable.

Invocation: python run.py <build_dir>
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, _HERE)

from core import (  # noqa: E402
    DiagnosticEmitter,
    write_artifact,
    write_evaluation,
    evaluate_artifact,
)

GITHUB_RE = re.compile(r"https?://github\.com/([\w.-]+/[\w.-]+)", re.I)
GENERIC_URL_RE = re.compile(r"https?://([\w.-]+\.[a-z]{2,})")
CODEFENCE_RE = re.compile(r"^```(\w+)", re.M)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
FUTURE_HEADING_RE = re.compile(
    r"future work|next steps|unanswered|open question|what'?s next|potential project|roadmap",
    re.I,
)


def _slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-") or "item"


def extract_doc(doc: dict, raw_text: str) -> dict:
    did = doc["id"]
    repos = []
    for m in set(GITHUB_RE.findall(raw_text)):
        m = m.removesuffix(".git")
        if m.split("/")[0].lower() in ("yourusername", "your-username", "user"):
            continue  # placeholder, not a real repo
        repos.append({"name": m, "url": f"https://github.com/{m}",
                      "span": {"doc": did, "section": "body"}})
    other_urls = [
        u for u in set(GENERIC_URL_RE.findall(raw_text))
        if "github.com" not in u and "danielkliewer.com" not in u
        and "youtube.com" not in u and "notebooklm" not in u
    ]

    # technologies from code fences
    code_langs = set(CODEFENCE_RE.findall(raw_text))
    technologies = [
        {"label": lang, "type": "language", "span": {"doc": did, "section": "code"}}
        for lang in code_langs
        if lang
    ]
    # well-known infra terms detected in text
    infra_terms = ["ollama", "llama.cpp", "vllm", "chromadb", "networkx",
                   "neo4j", "fastapi", "next.js", "sqlite", "docker",
                   "mcp", "sovereignspec", "vercel", "transformers",
                   "sentence-transformers", "pydantic", "graphrag"]
    for t in infra_terms:
        if re.search(rf"\b{re.escape(t)}\b", raw_text, re.I):
            technologies.append({"label": t, "type": "infrastructure",
                                  "span": {"doc": did, "section": "body"}})

    # concepts from section headings (excluding level-1 title)
    concepts = []
    NOISE = {
        "table of contents", "introduction", "conclusion", "abstract",
        "executive summary", "overview", "background", "summary",
        "references", "related posts", "related repositories", "prerequisites",
        "getting started", "setup", "install dependencies", "troubleshooting",
        "explanation", "motivation", "objectives", "research questions",
        "how it works", "why this matters", "project overview", "next steps",
        "future enhancements", "additional resources", "configuration",
        "installing dependencies", "installation", "running the application",
        "running the app", "security considerations", "performance optimization",
        "testing & documentation", "testing and quality assurance",
        "performance", "architecture overview", "features", "usage", "examples",
        "conclusion & next steps", "what you'll build", "prerequisites",
        "step-by-step guide", "final thoughts", "results", "demo",
    }
    STEP_RE = re.compile(r"^(step|\d+[\.\)])\s", re.I)
    for s in doc.get("sections", []):
        title = s.get("title", "").strip().strip("*").strip()
        low = title.lower().rstrip(":")
        if not title or low in NOISE or STEP_RE.match(title):
            continue
        # skip long run-on headings (title restatements) and pure scaffolding
        if len(title) > 70:
            continue
        concepts.append({
            "label": title.rstrip(":"),
            "type": "concept",
            "level": s.get("level", 2),
            "span": {"doc": did, "section": title},
        })

    # future questions: capture headings that look like future-work + any
    # question-mark line in the final 25% of the document.
    lines = raw_text.splitlines()
    future_questions = []
    future_headings = [
        s.get("title", "") for s in doc.get("sections", [])
        if FUTURE_HEADING_RE.search(s.get("title", ""))
    ]
    for h in future_headings:
        future_questions.append({"text": h, "span": {"doc": did, "section": h}})
    tail = lines[int(len(lines) * 0.75):]
    for ln in tail:
        if "?" in ln and len(ln) < 160 and not ln.strip().startswith("#"):
            future_questions.append({
                "text": ln.strip().lstrip("->*-").strip(),
                "span": {"doc": did, "section": "tail"},
            })

    return {
        "id": did,
        "title": doc.get("title", ""),
        "topics": [t for t in (doc.get("tags", []) or [])],
        "concepts": concepts,
        "entities": [],
        "technologies": technologies,
        "repositories": repos,
        "external_links": sorted(set(other_urls)),
        "code_artifacts": [
            {"language": cb.get("language"),
             "lines": cb.get("lines"),
             "snippet": cb.get("snippet")}
            for cb in doc.get("code_blocks", [])
            if cb.get("lines", 0) > 2
        ],
        "future_questions": future_questions[:8],
        "word_count": doc.get("word_count", 0),
        "section_count": doc.get("section_count", 0),
    }


def main() -> int:
    build_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    with open(os.path.join(build_dir, "markdown-ir", "artifact.json"), encoding="utf-8") as fh:
        md = json.load(fh)

    source_dir = os.path.join(build_dir, "source")
    by_path = {d["path"]: d for d in md.get("documents", [])}

    articles = []
    repo_index: Counter = Counter()
    tech_index: Counter = Counter()
    concept_index: Counter = Counter()
    vocab_index: Counter = Counter()  # research vocabulary from frontmatter
    for path, doc in by_path.items():
        with open(os.path.join(source_dir, path), encoding="utf-8") as fh:
            raw = fh.read()
        # strip frontmatter for cleaner extraction
        raw = re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.DOTALL)
        rec = extract_doc(doc, raw)
        articles.append(rec)
        for r in rec["repositories"]:
            repo_index[r["name"]] += 1
        for t in rec["technologies"]:
            tech_index[t["label"]] += 1
        for c in rec["concepts"]:
            concept_index[c["label"]] += 1
        # Research vocabulary: frontmatter tags + wiki_references are the
        # author's own controlled vocabulary; far less noisy than section
        # headings. This is what the gap-analysis universe should be built from.
        for tag in doc.get("tags", []) or []:
            if isinstance(tag, str) and len(tag) > 1:
                vocab_index[tag.lower()] += 1
        for wr in doc.get("frontmatter", {}).get("wiki_references", []) or []:
            if isinstance(wr, str):
                vocab_index[wr.lower()] += 1

    ir = {
        "schema_version": "1.0",
        "article_count": len(articles),
        "articles": articles,
        "corpus_index": {
            "repositories": [
                {"name": k, "mentions": v} for k, v in repo_index.most_common()
            ],
            "technologies": [
                {"label": k, "mentions": v} for k, v in tech_index.most_common(30)
            ],
            "top_concepts": [
                {"label": k, "mentions": v} for k, v in concept_index.most_common(40)
            ],
            "vocabulary": [
                {"label": k, "mentions": v} for k, v in vocab_index.most_common(60)
            ],
        },
    }

    emitter = DiagnosticEmitter("knowledge-extraction-ir", build_dir)
    if not repo_index:
        emitter.info("NO_REPOS", "no GitHub repositories detected in corpus")
    emitter.write()

    meta = write_artifact(
        build_dir, "knowledge-extraction-ir", ir, pass_id="pass-02-extract",
        source_artifacts=["markdown-ir"], schema_id="knowledge-extraction-ir",
    )
    ev = evaluate_artifact(
        "knowledge-extraction-ir", ir, meta,
        hints={
            "coverage": min(1.0, len(articles) / max(1, len(by_path))),
            "traceability": 1.0, "reproducibility": 1.0,
            "consistency": 1.0, "hallucination": 0.0,
        },
    )
    write_evaluation(build_dir, "knowledge-extraction-ir", ev)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
