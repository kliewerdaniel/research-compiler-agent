#!/usr/bin/env python3
"""research-compiler-agent CLI driver.

Mirrors the Knowledge Compiler SDK's `knowledgec` driver but operates on this
project's compiler/passes. Stages corpus Markdown into the build dir, discovers
passes declaratively, and runs them (deterministic for free; model passes when
--local points at a running OpenAI-compatible inference server).

Usage:
    python -m compiler.run --source corpus/source_blog_posts --build build \
        [--target gap-analysis-ir] [--local --port 8080 --model NAME]

The deterministic passes (parse, style, extraction, gap, graph) run with NO
model and produce real, inspectable artifacts. The model passes (research
generation, repo generation, self-improvement) require --local.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from core import Compiler, PassRegistry  # noqa: E402

PASSES_ROOT = os.path.join(_HERE, "passes")
DEFAULT_BUILD = os.path.join(os.getcwd(), "build")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="researchc", description=__doc__)
    ap.add_argument("--source", required=True, help="Corpus dir of .md files.")
    ap.add_argument("--build", default=DEFAULT_BUILD, help="Build dir.")
    ap.add_argument("--target", default=None,
                    help="Target artifact type (omit = run everything).")
    ap.add_argument("--dry", action="store_true", help="Plan only.")
    ap.add_argument("--local", action="store_true",
                    help="Run model passes against a local inference server.")
    ap.add_argument("--port", type=int, default=int(os.environ.get("KC_PORT", "8080")))
    ap.add_argument("--model", default=os.environ.get("KC_MODEL"))
    ap.add_argument("--embed-model", default=os.environ.get("KC_EMBED_MODEL"))
    ap.add_argument("--timeout", type=float, default=float(os.environ.get("KC_TIMEOUT", "900")))
    ap.add_argument("--max-tokens", type=int, default=int(os.environ.get("KC_MAX_TOKENS", "8192")))
    ap.add_argument("--no-cache", action="store_true",
                    help="Disable incremental re-compilation; rebuild all passes.")
    ap.add_argument("--only", default=None, help="Run only this pass id.")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args(argv)

    build_dir = os.path.abspath(args.build)
    source_dir = os.path.join(build_dir, "source")
    os.makedirs(source_dir, exist_ok=True)
    src = os.path.abspath(args.source)
    if os.path.isdir(src):
        copied = 0
        for fn in os.listdir(src):
            if fn.endswith(".md"):
                shutil.copy(os.path.join(src, fn), os.path.join(source_dir, fn))
                copied += 1
        print(f"staged {copied} corpus files into {source_dir}")
    else:
        print(f"error: source not found: {src}", file=sys.stderr)
        return 2

    registry = PassRegistry(PASSES_ROOT)
    print(f"discovered {len(registry.passes)} passes: " + ", ".join(registry.passes.keys()))

    compiler = Compiler(registry, build_dir)
    summary = compiler.run(
        target=args.target, dry_run=args.dry, local=args.local, port=args.port,
        model=args.model, incremental=not args.no_cache or args.resume,
        only=args.only, embed_model=args.embed_model,
        timeout=args.timeout, max_tokens=args.max_tokens,
    )
    steps = summary["plan"]["steps"]
    skipped = summary["plan"]["skipped"]
    print(f"\nplan: {len(steps)} step(s), {len(skipped)} skipped")
    flagmap = {"ok": "✓", "failed": "✗", "skipped": "·", "cached": "≡"}
    for rec in summary["records"]:
        extra = f" ({rec['reason']})" if rec.get("reason") else ""
        print(f"  {flagmap.get(rec['status'], '?')} {rec['pass_id']:<24} -> {rec['produces']}{extra}")
    print(f"\nbuild dir: {build_dir}")
    print(f"summary:   {os.path.join(build_dir, 'plan.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
