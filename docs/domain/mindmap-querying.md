# MindMap Querying Notes

## Overview

The MindMap query motor is the core anti-hallucination mechanism.

It enforces strict separation between retrieval and generation:
- Retrieval produces a proven evidence subgraph
- Synthesis is constrained to serialized graph evidence

## Pipeline

### Phase 1: Mine (Entity and Intent Extraction)

- Model: Vertex AI Gemini Flash
- Goal: extract structured entities and intent from prompt
- Constraint: JSON-schema output contract

Example output:

```json
{
  "intent": "budget_analysis",
  "entities": [{"id": "proj_alpha", "type": "Project"}]
}
```

### Phase 2: Aggregate (Graph Traversal)

- Engine: Spanner Graph (GQL)
- Goal: retrieve connected evidence from Context and Semantic graphs
- Constraint: apply cognitive horizon filters

Example:

```sql
GRAPH AgentMemoryGraph
MATCH (start:Project {id: 'proj_alpha'})-[r*1..3]->(target)
WHERE r.cognitive_weight > 0.3
RETURN start, r, target
```

### Phase 3: Serialize (MindMap Evidence)

- Engine: middleware serializer
- Goal: transform graph paths into stable factual statements

Example output:

```text
FACT 1: (Project Alpha) -[CONSUMES]-> (Cloud Resources)
FACT 2: (Cloud Resources) -[BILLED_TO]-> (Q3 Budget)
```

### Phase 4: Synthesize (Grounded Response)

- Model: Vertex AI Gemini Pro
- Goal: produce user-facing response from serialized facts only
- Fallback: if facts are insufficient, return explicit insufficiency

Required synthesis rule:
- Never answer from parametric memory when graph evidence is missing.

## Design Constraints

- Deterministic retrieval before generation
- Typed extraction payloads and validation
- Auditable linkage from answer to evidence paths
- Graceful no-result behavior

## Marketplace Alignment Notes

This flow supports marketability by:
- Reducing hallucination risk in customer-facing workflows
- Improving buyer trust through transparent reasoning traces
- Enabling support/debugging through reproducible evidence paths

## Open Questions

- How should intent be encoded as traversal constraints?
- How should breadth/depth be tuned for latency vs coverage?
- What is the best serialization format for both humans and machines?
