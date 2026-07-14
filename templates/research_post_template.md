# Research Post Template

> Canonical structure every generated research artifact must follow. This is the
> shape `pass-05-research-generation` fills and `compiler/generation/assemble.py`
> renders. It is derived from the recurring section pattern of the source corpus.

```markdown
---
title: "<Title — a thesis statement, not a headline>"
slug: <kebab-case-slug>
date: <YYYY-MM-DD>
author: Research Compiler Agent
description: <one-sentence summary>
tags:
- <concept-a>
- <concept-b>
- research-compiler
generated_by: research-compiler-agent
source_gap: <the gap edge this post closes>
---

# <Title>

## Abstract
<2-3 sentences: the gap, the new concept, why it matters.>

## The Problem
<Name a failure in the status quo (RAG, cloud, chat, telemetry-as-governance).
 State it as a systems-design failure.>

## Existing Approaches
<Survey the closest existing treatments, grounded in knowledge-graph edges.
 Use a comparison table where it helps.>

## New Concept
<The synthesis. Name it. Define it. State what it replaces and why.>

## Architecture
<Diagram (Mermaid/PlantUML) + a layered description. Reference the graph nodes.>

## Implementation
<Concrete steps. Reference technologies. Include a code block if applicable.>

## Code Repository
<If becomes_software: link the generated repo, its structure, its roadmap.>

## Experiments
<How to validate the claim. Metrics. What a negative result would mean.>

## Applications
<Where this helps: local-first AI, sovereign knowledge systems, ...>

## Future Work
<The next gaps this opens. Pointers to sibling concepts in the graph.>

## Conclusion
<Restate the thesis. The artifact is the point, not the prose.>

## References
- <source post / repo / paper, with provenance>

## Next Steps
- <actionable items>

## Potential Projects
- <software that could be built from this>
```

### Rules enforced by the generation pass

1. Open by naming a failure in the status quo.
2. Resolve with an inspectable artifact or a build step.
3. Use comparison tables to make abstract claims concrete.
4. Keep every claim traceable to a graph edge; mark inferences as hypotheses.
5. End with forward pointers (Next Steps / Future Work / Potential Projects).
