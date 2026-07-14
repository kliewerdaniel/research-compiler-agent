#!/usr/bin/env python3
"""pass-06-repo-generation entrypoint (model-required).

Reads the generated research artifact. If becomes_software==true (or the idea
is clearly engineerable), asks the local model to emit a repository scaffold:
name, README, directory structure, architecture, implementation roadmap,
example code file, and a test file. Writes repo-generation-ir.

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

PRODUCES = "repo-generation-ir"
CONSUMES = ["research-generation-ir"]


def build_user_prompt(inputs: dict) -> str:
    rg = inputs.get("research-generation-ir", {})
    if rg.get("skip"):
        return "No research artifact produced. Return {\"skip\": true}."
    payload = {
        "title": rg.get("title"),
        "abstract": rg.get("abstract"),
        "new_concept": next((s.get("body") for s in rg.get("sections", [])
                             if s.get("heading", "").lower().startswith("new concept")), ""),
        "becomes_software": rg.get("becomes_software"),
        "repo_idea": rg.get("repo_idea"),
        "potential_projects": rg.get("potential_projects", []),
    }
    return (
        "REPOSITORY GENERATION TASK\n\n"
        "Given the research artifact, decide if it should become software. "
        "If yes, emit a complete repository scaffold.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n\nReturn JSON: {\"should_build\":bool, \"repo_name\":str, "
        "\"one_line\":str, \"readme\":str, \"structure\":[{\"path\":str,\"purpose\":str}], "
        "\"architecture\":str, \"roadmap\":[str], \"example_code\":{\"path\":str,\"language\":str,\"code\":str}, "
        "\"test_code\":{\"path\":str,\"language\":str,\"code\":str}}.\n"
        "Prefer Python + local-first (no cloud deps) unless the concept requires "
        "otherwise. The example_code and test_code MUST be runnable skeletons. "
        "Respond with JSON only."
    )


SYSTEM_PROMPT = """You are the Repository Generation compiler pass. You convert a
research idea into deployable engineering artifacts: a repository scaffold with
README, structure, architecture, roadmap, example code, and tests. Keep it
local-first and minimal-dependency. OUTPUT JSON ONLY."""


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
