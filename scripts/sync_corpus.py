#!/usr/bin/env python3
"""Sync the live blog into the compiler's ingestion corpus.

Usage:
    python scripts/sync_corpus.py            # copy new/changed posts
    python scripts/sync_corpus.py --dry      # show what would change

Copies every .md from the real blog (excluding temp.md and draft-only files)
into corpus/source_blog_posts/, so the compiler ingests the *full and evolving*
blog each run. Idempotent: only copies files whose size/mtime changed, so the
compiler's incremental cache stays valid for unchanged posts.

This is the bridge that lets the compiler ingest full blog posts and absorb new
ones you add later — point it at your blog and re-run the compiler.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "corpus", "source_blog_posts")
DEFAULT_BLOG = "/Users/danielkliewer/a10/sovereign-ai-site/content/blog"
EXCLUDE = {"temp.md"}


def _is_draft(path: str) -> bool:
    """Skip posts explicitly marked draft: true (not ready for synthesis)."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            head = fh.read(4000)
    except OSError:
        return False
    if not head.startswith("---"):
        return False
    fm = head.split("---", 2)
    if len(fm) < 3:
        return False
    return "draft: true" in fm[1].lower()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--blog", default=DEFAULT_BLOG, help="Source blog posts dir")
    ap.add_argument("--corpus", default=CORPUS, help="Compiler corpus dir")
    ap.add_argument("--dry", action="store_true", help="Show changes, don't copy")
    args = ap.parse_args()

    if not os.path.isdir(args.blog):
        print(f"error: blog dir not found: {args.blog}", file=sys.stderr)
        return 2
    os.makedirs(args.corpus, exist_ok=True)

    copied = skipped = drafts = 0
    for fn in sorted(os.listdir(args.blog)):
        if not fn.endswith(".md") or fn in EXCLUDE:
            continue
        src = os.path.join(args.blog, fn)
        if _is_draft(src):
            drafts += 1
            continue
        dst = os.path.join(args.corpus, fn)
        same = os.path.exists(dst) and os.path.getsize(src) == os.path.getsize(dst)
        if same:
            skipped += 1
            continue
        if args.dry:
            print(f"  would copy {fn}")
        else:
            shutil.copy(src, dst)
            print(f"  copied {fn}")
        copied += 1

    print(
        f"sync done: {copied} copied, {skipped} up-to-date"
        + (f", {drafts} drafts skipped" if drafts else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
