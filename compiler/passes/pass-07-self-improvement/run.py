#!/usr/bin/env python3
"""pass-07-self-improvement entrypoint (model-required).

Maintains the agent's capability ledger: current capabilities, missing
capabilities, failed experiments, and improvement ideas. Asks the local model
to propose the single highest-value next improvement to the compiler itself
(recursive self-improvement). Writes self-improvement-ir.

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

PRODUCES = "self-improvement-ir"
CONSUMES = ["research-generation-ir", "repo-generation-ir", "style-model-ir"]


def build_user_prompt(inputs: dict) -> str:
    rg = inputs.get("research-generation-ir", {})
    repo = inputs.get("repo-generation-ir", {})
    style = inputs.get("style-model-ir", {})
    payload = {
        "last_generated_title": rg.get("title"),
        "last_repo_built": repo.get("repo_name") if repo.get("should_build") else None,
        "corpus_size": style.get("corpus_size"),
        "known_capability": [
            "deterministic parse", "style model", "knowledge extraction",
            "gap analysis", "networkx knowledge graph", "research generation",
            "repo generation",
        ],
        "improvement_levers": [
            "better retrieval", "better graph reasoning", "better evaluation",
            "better code generation", "better experiment tracking",
            "better writing reproduction", "incremental re-compilation",
            "agent orchestration",
        ],
    }
    return (
        "SELF-IMPROVEMENT TASK\n\n"
        "You maintain an autonomous research compiler's capability ledger. "
        "Given what was just produced, propose the single highest-value "
        "improvement to the compiler itself.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n\nReturn JSON: {\"capabilities_current\":[str], "
        "\"capabilities_missing\":[str], \"failed_experiments\":[str], "
        "\"improvement_ideas\":[{\"idea\":str,\"rationale\":str,\"effort\":str,\"impact\":str}], "
        "\"next_capability\":str, \"next_capability_spec\":str}.\n"
        "Respond with JSON only."
    )


SYSTEM_PROMPT = """You are the Self-Improvement compiler pass of an autonomous
research compiler. You track what the system can and cannot do, and propose the
next capability that would make the compiler better at turning knowledge into
research + software. Be concrete and recursive: the compiler should be able to
implement your proposed improvement. OUTPUT JSON ONLY."""


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
