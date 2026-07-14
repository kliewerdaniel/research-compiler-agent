#!/usr/bin/env python3
"""The recursive self-improvement loop.

Drives the compiler through one cycle:
  1. Run the deterministic analysis pipeline (parse -> style -> extract ->
     gap -> graph). Always works, no model.
  2. If --local, run the model passes (research generation -> repo generation ->
     self-improvement) and assemble a post + repo scaffold.
  3. Record a cycle entry into agents/self_improvement.md (the capability ledger)
     and emit a "next capability" proposal.

The loop is honest: without --local it produces the deterministic knowledge
graph + gap brief; with --local it produces a full research artifact.

Usage:
    python -m compiler.orchestration.loop --source corpus/source_blog_posts \
        --build build [--local --port 8080 --model NAME] [--cycles 1]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(ROOT, "compiler"))

from core import Compiler, PassRegistry  # noqa: E402

PASSES_ROOT = os.path.join(ROOT, "compiler", "passes")


def run_cycle(source: str, build: str, local: bool, port: int, model,
              timeout: float, max_tokens: int) -> dict:
    # stage source
    src_dir = os.path.join(build, "source")
    os.makedirs(src_dir, exist_ok=True)
    for fn in os.listdir(source):
        if fn.endswith(".md"):
            import shutil
            shutil.copy(os.path.join(source, fn), os.path.join(src_dir, fn))

    reg = PassRegistry(PASSES_ROOT)
    compiler = Compiler(reg, build)

    # 1. deterministic analysis always
    compiler.run(target="knowledge-graph-ir", local=False)
    # 2. model passes if local
    if local:
        try:
            compiler.run(target="research-generation-ir", local=True, port=port,
                         model=model, timeout=timeout, max_tokens=max_tokens)
            compiler.run(target="repo-generation-ir", local=True, port=port,
                         model=model, timeout=timeout, max_tokens=max_tokens)
            compiler.run(target="self-improvement-ir", local=True, port=port,
                         model=model, timeout=timeout, max_tokens=max_tokens)
        except Exception as e:  # pragma: no cover
            print(f"warn: model pass failed: {e}", file=sys.stderr)

    # assemble post (+ brief fallback)
    import importlib
    sys.path.insert(0, os.path.join(ROOT, "compiler", "generation"))
    assemble = importlib.import_module("assemble")
    sys.argv = ["assemble", build]
    assemble.main()

    # collect a summary
    summary = {"build": build, "local": local, "timestamp": dt.datetime.now().isoformat()}
    for art in ("knowledge-graph-ir", "gap-analysis-ir", "research-generation-ir",
                "repo-generation-ir", "self-improvement-ir"):
        p = os.path.join(build, art, "artifact.json")
        if os.path.isfile(p):
            d = json.load(open(p))
            if art == "knowledge-graph-ir":
                summary["graph"] = {"nodes": d.get("node_count"),
                                    "edges": d.get("edge_count"),
                                    "gaps": d.get("research_gap_edge_count")}
            elif art == "gap-analysis-ir":
                summary["gaps"] = len(d.get("candidate_hypotheses", []))
            elif art == "research-generation-ir":
                summary["generated_post"] = d.get("title")
            elif art == "repo-generation-ir":
                summary["generated_repo"] = d.get("repo_name") if d.get("should_build") else None
            elif art == "self-improvement-ir":
                summary["next_capability"] = d.get("next_capability")
    return summary


def append_ledger(entry: dict) -> None:
    ledger_path = os.path.join(ROOT, "agents", "self_improvement.md")
    os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
    line = (
        f"\n## Cycle {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"- graph nodes/edges: {entry.get('graph', {}).get('nodes')}/"
        f"{entry.get('graph', {}).get('edges')}\n"
        f"- research gaps detected: {entry.get('gaps')}\n"
        f"- generated post: {entry.get('generated_post')}\n"
        f"- generated repo: {entry.get('generated_repo')}\n"
        f"- proposed next capability: {entry.get('next_capability')}\n"
    )
    with open(ledger_path, "a", encoding="utf-8") as fh:
        fh.write(line)
    print(f"appended cycle to {ledger_path}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default=os.path.join(ROOT, "corpus", "source_blog_posts"))
    ap.add_argument("--build", default=os.path.join(ROOT, "build"))
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--port", type=int, default=int(os.environ.get("KC_PORT", "8080")))
    ap.add_argument("--model", default=os.environ.get("KC_MODEL"))
    ap.add_argument("--timeout", type=float, default=float(os.environ.get("KC_TIMEOUT", "900")))
    ap.add_argument("--max-tokens", type=int, default=int(os.environ.get("KC_MAX_TOKENS", "8192")))
    ap.add_argument("--cycles", type=int, default=1)
    args = ap.parse_args()

    for i in range(max(1, args.cycles)):
        print(f"\n=== cycle {i+1}/{args.cycles} ===")
        entry = run_cycle(args.source, args.build, args.local, args.port, args.model,
                          args.timeout, args.max_tokens)
        append_ledger(entry)
        print(json.dumps({k: v for k, v in entry.items() if k != "build"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
