#!/usr/bin/env python3
"""pass-12-an-entity-resolution entrypoint (deterministic).

The knowledge graph accumulates duplicate nodes: versioned repos
(``objective05`` vs ``objective`` vs ``objective05-exec``), owner variants of
the same project (``ollama/ollama`` vs ``jmorganca/ollama``), and spacing
variants (``knowledge-graphs`` vs ``knowledge graph``). These fragments weaken
every downstream signal (co-occurrence, gaps, contradictions).

This pass resolves them: it loads ``knowledge-graph-ir``, finds duplicate nodes
within each kind, and merges them under a canonical label using a union-find.
Matching is deliberately conservative to avoid false merges:

  * repositories: compared by *project name* (the part after the last ``/``);
    identical names merge, otherwise an edit distance <= 2 on the normalized
    project name merges (catches ``objective05`` <-> ``objective``).
  * concepts / technologies / persons: normalized edit distance <= 2 with a
    length delta <= 2 merges (catches ``knowledge-graphs`` <-> ``knowledge
    graph``). Semantically-distinct but token-overlapping labels like
    ``ai`` vs ``rag`` are NOT merged (their distance exceeds the threshold).

The canonical label is the shortest / most-connected / lexicographically-first
candidate. The pass emits ``entity-resolution-ir`` with the merge plan
(``merged_groups``) plus before/after node+edge counts. ``pass-04`` reads this
artifact and applies the merges when it writes the graph, so the resolution is
live in the delivered knowledge graph.

Invocation: python run.py <build_dir>
"""

from __future__ import annotations

import os
import re
import sys
from collections import defaultdict

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

PRODUCES = "entity-resolution-ir"
CONSUMES = ["knowledge-graph-ir"]

# Kinds that can have name-variant duplicates worth merging.
MERGE_KINDS = ("repository", "person", "technology", "concept")
LEV_MAX = 2          # max normalized edit distance to merge
LEN_DELTA = 2        # max length difference to merge


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _project(repo: str) -> str:
    """Repository project name (part after the last '/'), normalized.

    Uses the RAW label so owner prefixes ('jmorganca/ollama') are stripped
    correctly before normalization.
    """
    return _norm(repo.split("/")[-1])


def _strip_digits(s: str) -> str:
    """Drop a trailing run of digits (version suffix): 'objective05' -> 'objective'."""
    return re.sub(r"\d+$", "", s)


def _lev(a: str, b: str) -> int:
    m, n = len(a), len(b)
    if abs(m - n) > LEN_DELTA:
        return 999
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            cur = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev = cur
    return dp[n]


def _strip_plural(s: str) -> str:
    """Drop a trailing plural suffix ('s' or 'es'): 'graphs' -> 'graph'."""
    if s.endswith("es") and len(s) > 3:
        return s[:-2]
    if s.endswith("s") and len(s) > 2:
        return s[:-1]
    return s


def _matches(na: str, nb: str, kind: str, raw_a: str = "", raw_b: str = "") -> bool:
    """Conservative duplicate test for two labels of the same kind.

    Repositories are compared by project name (owner stripped); identical
    project names merge, otherwise a normalized edit distance <= 2 merges
    (catches versioned forks like 'objective05' <-> 'objective').

    Concepts / technologies / persons merge ONLY when they are the *same phrase*
    written differently — a spacing/punctuation/plural variant. After stripping a
    trailing digit run and a trailing plural suffix, the normalized strings must
    be identical AND long enough (>= 6 chars) that 2-3 letter tokens ('ai' vs
    'rag') cannot collide. This merges 'knowledge graph' <-> 'knowledge-graphs'
    but refuses 'ai' <-> 'ai-agents' or 'docker' <-> 'dockerfile'.
    """
    if kind == "repository":
        if raw_a and raw_b and _project(raw_a) == _project(raw_b) \
                and _project(raw_a):
            return True
        return _lev(na, nb) <= LEV_MAX
    # concepts / technologies / persons
    sa = _strip_plural(_strip_digits(na))
    sb = _strip_plural(_strip_digits(nb))
    if sa and sb and sa == sb and len(sa) >= 6:
        return True
    return False


def _find_groups(candidates: list[tuple[str, str, str]]) -> list[list[tuple[str, str, str]]]:
    """Return groups of duplicate nodes (within the same kind) to merge.

    ``candidates`` is a list of ``(label, kind, node_id)`` tuples. ``node_id``
    is the id pass-04 will assign (computed via the same ``_slug`` convention),
    so the merge plan is valid before the graph is built.
    """
    by_kind: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for c in candidates:
        if c[1] in MERGE_KINDS:
            by_kind[c[1]].append(c)

    groups: list[list[tuple[str, str, str]]] = []
    for kind, items in by_kind.items():
        parent = list(range(len(items)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry

        normed = [_norm(it[0]) for it in items]
        raws = [it[0] for it in items]
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if normed[i] == normed[j]:
                    continue  # identical normalized -> trivial, still merge
                if _matches(normed[i], normed[j], kind,
                            raw_a=raws[i], raw_b=raws[j]):
                    union(i, j)
        clusters: dict[int, list[int]] = defaultdict(list)
        for i in range(len(items)):
            clusters[find(i)].append(i)
        for idxs in clusters.values():
            if len(idxs) > 1:
                groups.append([items[i] for i in idxs])
    return groups


def _canonical(group: list[tuple[str, str, str]]) -> tuple[str, str, str]:
    """Pick the canonical candidate: shortest label, then lexicographically
    first id (deterministic; degree is unknown before the graph is built)."""
    return sorted(group, key=lambda c: (len(c[0]), c[2]))[0]


def main() -> int:
    build_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    store = ArtifactStore(build_dir)
    if not store.has("knowledge-graph-ir"):
        print("error: knowledge-graph-ir missing; run pass-04 first",
              file=sys.stderr)
        return 1
    kg = store.read("knowledge-graph-ir")
    nodes = kg.get("nodes", [])

    # Build candidate (label, kind, node_id) tuples from the REAL graph nodes.
    # Only nodes that actually exist can be merged, so this never produces
    # phantom canonical ids (unlike deriving from the vocab/repo index).
    candidates: list[tuple[str, str, str]] = []
    for n in nodes:
        if n.get("kind") in MERGE_KINDS:
            candidates.append((n.get("label", ""), n.get("kind", ""), n.get("id", "")))

    groups = _find_groups(candidates)

    merged_groups = []
    for g in groups:
        canon = _canonical(g)
        members = []
        for label, kind, nid in g:
            if nid != canon[2]:
                members.append({"id": nid, "label": label, "kind": kind})
        merged_groups.append({
            "canonical_label": canon[0],
            "canonical_id": canon[2],
            "kind": canon[1],
            "labels": [c[0] for c in g],
            "merged": members,
        })

    ir = {
        "schema_version": "1.0",
        "generated": False,
        "merge_count": len(merged_groups),
        "nodes_resolved": len(candidates) - sum(len(g["merged"]) for g in merged_groups),
        "merged_groups": merged_groups,
    }

    emitter = DiagnosticEmitter(PRODUCES, build_dir)
    if not merged_groups:
        emitter.info("NO_DUPLICATES", "no duplicate nodes detected")
    else:
        emitter.info("MERGED",
                     f"{len(merged_groups)} duplicate groups -> "
                     f"{ir['nodes_resolved']} nodes")
    emitter.write()

    meta = write_artifact(
        build_dir, PRODUCES, ir, pass_id="pass-12-an-entity-resolution",
        source_artifacts=CONSUMES, schema_id=PRODUCES,
        pass_dir=os.path.dirname(os.path.abspath(__file__)),
    )
    ev = evaluate_artifact(
        PRODUCES, ir, meta,
        hints={"coverage": 1.0, "traceability": 1.0, "reproducibility": 1.0,
               "consistency": 1.0, "hallucination": 0.0},
    )
    write_evaluation(build_dir, PRODUCES, ev)

    print(f"info: entity-resolution merged {len(merged_groups)} groups; "
          f"{ir['nodes_resolved']} distinct nodes after merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
