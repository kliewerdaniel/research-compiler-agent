#!/usr/bin/env bash
# Research Compiler Agent — launcher.
# Uses the Python 3.11 venv that has openai + networkx + pyyaml.
# Deterministic passes need only networkx + pyyaml; model passes (--local)
# additionally need 'openai' and a running local inference server.
set -euo pipefail
cd "$(dirname "$0")"
VPY="${HERMES_VENV:-$HOME/.hermes/hermes-agent/venv/bin/python}"
PORT="${KC_PORT:-8099}"
MODEL="${KC_MODEL:-mock}"

if [ "${1:-}" = "mock" ]; then
  # start the pass-aware mock server, run the full pipeline, stop it.
  "$VPY" experiments/mock_server.py "$PORT" &
  SRV=$!
  trap 'kill $SRV 2>/dev/null || true' EXIT
  sleep 1
  "$VPY" -m compiler.run --source corpus/source_blog_posts --build build \
    --local --port "$PORT" --model "$MODEL" --max-tokens 4096
  "$VPY" -m compiler.orchestration.loop --source corpus/source_blog_posts --build build --cycles 1
else
  # default: deterministic analysis only (no model required)
  "$VPY" -m compiler.run --source corpus/source_blog_posts --build build
  "$VPY" -m compiler.orchestration.loop --source corpus/source_blog_posts --build build --cycles 1
fi
