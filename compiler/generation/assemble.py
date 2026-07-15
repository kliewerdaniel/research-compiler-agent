#!/usr/bin/env python3
"""Assemble a generated research artifact into a publishable Markdown post.

Reads <build>/research-generation-ir/artifact.json (produced by the model pass)
and renders the canonical research-post template to
generated_posts/<YYYY-MM-DD>-<slug>.md using the *full authored frontmatter*
style of the live blog (layout: post, og:*, canonical_url, draft: false) so a
generated post drops straight into content/blog/.

If the model pass hasn't run (no --local), it falls back to rendering a
*research brief* from the deterministic gap analysis so the pipeline always
yields a concrete, inspectable artifact.

Also writes a repo scaffold to generated_posts/<slug>/ when
repo-generation-ir indicates should_build.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date as _date

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(ROOT, "compiler"))


def _today_fm() -> str:
    """Live-blog frontmatter date convention: MM-DD-YYYY."""
    return _date.today().strftime("%m-%d-%Y")


def _meta_desc(abstract: str, limit: int = 200) -> str:
    """Meta description must be concise (SEO: <= ~155 chars is ideal; we allow
    a little headroom). Truncate on a word boundary and elide with an ellipsis
    so the field stays drop-in ready for the live blog."""
    a = (abstract or "").strip()
    if len(a) <= limit:
        return a
    cut = a[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",.;: ") + "…"


def _date_prefix() -> str:
    """Live-blog filename / canonical convention: YYYY-MM-DD-<slug>."""
    return _date.today().strftime("%Y-%m-%d")


def _slugify(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in (s or "untitled")).strip("-")


def _frontmatter(post: dict, canonical_slug: str) -> str:
    """Emit the FULL authored frontmatter style used by the live blog so a
    generated post is ready to drop into content/blog/. The model supplies
    title/slug/abstract/tags; date + canonical + image are derived here."""
    title = post.get("title", "Untitled Research")
    abstract = (post.get("abstract") or "").strip()
    meta_desc = _meta_desc(abstract)
    date_fm = post.get("date") or _today_fm()
    image = f"/images/{canonical_slug}.png"
    canonical = f"/blog/{_date_prefix()}-{canonical_slug}"
    fm = [
        "---",
        "author: Daniel Kliewer",
        f"canonical_url: {canonical}",
        f"date: {date_fm}",
        f"description: \"{meta_desc}\"",
        f"image: {image}",
        "layout: post",
        f"title: '{title}'",
        f"og:description: \"{meta_desc}\"",
        f"og:image: {image}",
        f"og:title: '{title}'",
        "og:type: article",
        f"og:url: {canonical}",
        "tags:",
    ]
    for t in post.get("tags", []) or []:
        fm.append(f"  - {t}")
    fm.append("draft: false")
    fm.append("---")
    return "\n".join(fm)


def render_post(post: dict) -> str:
    slug = _slugify(post.get("slug", "untitled"))
    out = [_frontmatter(post, slug), ""]
    out.append(f"# {post.get('title', 'Untitled')}")
    out.append("")
    # Render an Abstract heading only if the post has an abstract AND its first
    # section is not already an Abstract (avoids duplication when the body
    # already leads with Abstract).
    first_heading = (post.get("sections", []) or [{}])[0].get("heading", "").lower()
    if post.get("abstract") and first_heading != "abstract":
        out.append("## Abstract")
        out.append("")
        out.append(post["abstract"])
        out.append("")
    for s in post.get("sections", []) or []:
        out.append(f"## {s.get('heading', 'Section')}")
        out.append("")
        out.append(s.get("body", ""))
        out.append("")
    if post.get("references"):
        out.append("## References")
        out.append("")
        for r in post["references"]:
            out.append(f"- {r}")
        out.append("")
    if post.get("next_steps"):
        out.append("## Next Steps")
        out.append("")
        for n in post["next_steps"]:
            out.append(f"- {n}")
        out.append("")
    if post.get("potential_projects"):
        out.append("## Potential Projects")
        out.append("")
        for p in post["potential_projects"]:
            out.append(f"- {p}")
        out.append("")
    return "\n".join(out)


def render_brief(gap: dict, build_dir: str) -> dict:
    """Fallback: build a research brief from deterministic gap analysis."""
    import json as _json
    kg = _json.load(open(os.path.join(build_dir, "knowledge-graph-ir", "artifact.json")))
    style = _json.load(open(os.path.join(build_dir, "style-model-ir", "artifact.json")))
    connects = gap.get("connects", [])
    title = gap.get("title", "Research Direction")
    slug = "-".join(connects) if connects else "research-direction"
    sections = [
        {"heading": "Abstract",
         "body": f"This is a compiler-generated research brief for the hypothesis: "
                 f"\"{title}\". It was produced deterministically from the corpus "
                 f"knowledge graph before any local model inference was available. "
                 f"The graph records {kg['edge_count']} edges across {kg['node_count']} "
                 f"nodes; this direction is a ranked research gap."},
        {"heading": "The Problem",
         "body": f"The concepts '{connects[0] if connects else ''}' and "
                 f"'{connects[1] if len(connects) > 1 else ''}' are both well-covered "
                 f"in the corpus but never co-developed in a single artifact "
                 f"(co-occurrence = {gap.get('co_occurrence', 0)}). This is a structural "
                 f"gap the compiler detected by reasoning over the knowledge graph."},
        {"heading": "Existing Approaches",
         "body": "See the co-occurrence edges in knowledge-graph-ir for the closest "
                 "existing treatments. Run the model pass (pass-05) with --local to "
                 "expand this section with retrieved evidence."},
        {"heading": "New Concept",
         "body": gap.get("rationale", "A synthesis of the two under-connected concepts.")},
        {"heading": "Architecture", "body": "To be generated by pass-05 with --local."},
        {"heading": "Implementation", "body": "To be generated by pass-05 with --local."},
        {"heading": "Code Repository", "body": "To be generated by pass-06 with --local."},
        {"heading": "Experiments", "body": "Proposed once the concept is fleshed out."},
        {"heading": "Applications", "body": "Local-first AI, sovereign knowledge systems."},
        {"heading": "Future Work", "body": "Run the full pipeline with a local model to "
                                          "expand every section into the house voice."},
        {"heading": "Conclusion", "body": "The compiler identified this direction as a "
                                        "high-priority, currently-unfilled research gap."},
    ]
    return {
        "title": f"Research Brief: {title}",
        "slug": f"brief-{slug}",
        "abstract": f"Compiler-detected research gap: {title}.",
        "sections": sections,
        "tags": connects + ["research-compiler", "gap"],
        "references": [],
        "next_steps": ["Run `python -m compiler.run --source corpus/source_blog_posts "
                       "--build build --local --port 8080 --model <name>` to expand."],
        "potential_projects": [],
        "source_gap": title,
        "date": "",
    }


def main() -> int:
    build_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build")
    out_dir = os.path.join(ROOT, "generated_posts")
    os.makedirs(out_dir, exist_ok=True)

    gen_path = os.path.join(build_dir, "research-generation-ir", "artifact.json")
    if os.path.isfile(gen_path):
        post = json.load(open(gen_path))
        if post.get("skip"):
            print("research-generation-ir marked skip; nothing to render")
            return 0
    else:
        # Fallback: render a brief from the top gap.
        ga_path = os.path.join(build_dir, "gap-analysis-ir", "artifact.json")
        if not os.path.isfile(ga_path):
            print("no research-generation-ir or gap-analysis-ir; run the pipeline first",
                  file=sys.stderr)
            return 1
        ga = json.load(open(ga_path))
        hypotheses = ga.get("candidate_hypotheses", [])
        if not hypotheses:
            print("no candidate hypotheses; nothing to render", file=sys.stderr)
            return 1
        post = render_brief(hypotheses[0], build_dir)

    md = render_post(post)
    slug = _slugify(post.get("slug", "untitled"))
    is_brief = (post.get("slug") or "").startswith("brief-")
    fname = (f"{_date_prefix()}-{slug}.md") if not is_brief else f"{slug}.md"
    out_file = os.path.join(out_dir, fname)
    with open(out_file, "w", encoding="utf-8") as fh:
        fh.write(md)
    print(f"wrote research post: {out_file}")

    # Repo scaffold (if model produced one)
    repo_path = os.path.join(build_dir, "repo-generation-ir", "artifact.json")
    if os.path.isfile(repo_path):
        repo = json.load(open(repo_path))
        if repo.get("should_build"):
            rdir = os.path.join(out_dir, repo.get("repo_name", "generated-repo"))
            os.makedirs(rdir, exist_ok=True)
            with open(os.path.join(rdir, "README.md"), "w", encoding="utf-8") as fh:
                fh.write(repo.get("readme", "# Generated Repository\n"))
            ex = repo.get("example_code") or {}
            if ex.get("path") and ex.get("code"):
                p = os.path.join(rdir, ex["path"])
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(ex["code"])
            tc = repo.get("test_code") or {}
            if tc.get("path") and tc.get("code"):
                p = os.path.join(rdir, tc["path"])
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(tc["code"])
            print(f"wrote repo scaffold: {rdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
