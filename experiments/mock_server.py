"""A tiny mock OpenAI-compatible /v1 server to verify the model-pass wiring
without a real LLM. It returns a valid research-generation JSON so we can prove
pass-05 executes end-to-end through core.llm_pass + core.inference.

Run: python mock_server.py 8099   (in background)
Then: python -m compiler.run --source corpus/source_blog_posts --build build \
        --only pass-05-research-generation --local --port 8099 --model mock
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class H(BaseHTTPRequestHandler):
    def _send(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw or b"{}")
        except Exception:
            req = {}
        if self.path.rstrip("/").endswith("/embeddings"):
            data = req.get("input", [])
            self._send({"data": [{"embedding": [0.0] * 8, "index": i}
                                  for i in range(len(data))]})
            return
        # chat completion -> return pass-specific valid JSON.
        user_text = (req.get("messages", [{}])[-1].get("content", "")) if req.get("messages") else ""
        content = self._dispatch(user_text)
        self._send({
            "choices": [{
                "message": {"content": json.dumps(content)}
            }]
        })

    @staticmethod
    def _dispatch(user_text: str) -> dict:
        if "REPOSITORY GENERATION" in user_text:
            return {
                "should_build": True,
                "repo_name": "memory-agent-runtime",
                "one_line": "A local-first memory-driven agent runtime.",
                "readme": "# memory-agent-runtime\n\nLocal-first agent runtime where a "
                          "NetworkX knowledge graph is the agent's working memory.\n",
                "structure": [
                    {"path": "memory_agent/graph.py", "purpose": "NetworkX working memory"},
                    {"path": "memory_agent/loop.py", "purpose": "agent loop reading gap edges"},
                    {"path": "tests/test_loop.py", "purpose": "loop persistence test"},
                ],
                "architecture": "Graph-as-memory: the knowledge graph is the agent's "
                                "state; the local model is the actuator.",
                "roadmap": [
                    "Scaffold graph store",
                    "Wire gap edges as intentions",
                    "Add session persistence",
                    "Add eval harness",
                ],
                "example_code": {
                    "path": "memory_agent/loop.py",
                    "language": "python",
                    "code": "def step(graph):\n    intent = next(graph.gap_edges(), None)\n"
                            "    if intent: return act(intent)\n",
                },
                "test_code": {
                    "path": "tests/test_loop.py",
                    "language": "python",
                    "code": "def test_loop_runs():\n    assert step(build_graph()) is not None\n",
                },
            }
        if "SELF-IMPROVEMENT" in user_text:
            return {
                "capabilities_current": [
                    "parse", "style model", "extraction", "gap analysis",
                    "knowledge graph", "research generation", "repo generation",
                ],
                "capabilities_missing": [
                    "vector embeddings for semantic gap ranking",
                    "contradiction mining",
                ],
                "failed_experiments": [],
                "improvement_ideas": [
                    {"idea": "semantic gap ranker via local embeddings",
                     "rationale": "co-occurrence misses latent links",
                     "effort": "medium", "impact": "high"},
                    {"idea": "self-writing pass generator",
                     "rationale": "compiler should write its next capability",
                     "effort": "high", "impact": "high"},
                ],
                "next_capability": "semantic-gap-ranker",
                "next_capability_spec": "pass-04b-embeddings: embed concepts, rank gaps "
                                        "by semantic distance not just co-occurrence.",
            }
        # default: research generation
        return {
            "title": "Bridging Memory and Agency in Sovereign AI Systems",
            "slug": "memory-and-agency-sovereign-ai",
            "abstract": "A compiler-detected gap: memory and agency are both "
                        "well-covered but never co-developed. This post synthesizes "
                        "them into a memory-driven agent loop.",
            "sections": [
                {"heading": "Abstract", "body": "Memory and agency are under-connected."},
                {"heading": "The Problem", "body": "Agents are stateless between sessions."},
                {"heading": "Existing Approaches", "body": "Sovereign memory bank + persona MoE."},
                {"heading": "New Concept", "body": "A memory-driven agent loop."},
                {"heading": "Architecture", "body": "NetworkX graph as working memory."},
                {"heading": "Implementation", "body": "Wire pass-04 graph into an agent loop."},
                {"heading": "Code Repository", "body": "Generated by pass-06."},
                {"heading": "Experiments", "body": "Measure reasoning persistence."},
                {"heading": "Applications", "body": "Local-first sovereign AI."},
                {"heading": "Future Work", "body": "Closed-loop self-improvement."},
                {"heading": "Conclusion", "body": "The graph is the product."},
            ],
            "tags": ["memory", "agent", "sovereign-ai", "research-compiler"],
            "references": ["sovereign-memory-bank", "dynamic-persona-moe-rag"],
            "next_steps": ["Implement the memory-agent loop as a new pass."],
            "potential_projects": ["memory-agent-runtime"],
            "becomes_software": True,
            "repo_idea": "memory-agent-runtime",
        }

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
    HTTPServer(("127.0.0.1", port), H).serve_forever()
