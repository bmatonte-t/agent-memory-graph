# MindMap Pipeline

The MindMap pipeline is the core reasoning engine that powers `MEMORY_SEARCH`. When an agent asks a question, MindMap retrieves and synthesizes an answer entirely from graph evidence, with no fabrication.

## The Four Stages

```
Query ──► Mine ──► Aggregate ──► Serialize ──► Synthesize ──► Answer
```

### Stage 1 — Mine

**Input:** raw natural-language query string  
**Output:** structured intent + named entities

The mining stage parses the query to extract:
- Intent classification (lookup, comparison, relationship traversal, etc.)
- Named entities with their probable labels (`PERSON`, `SYSTEM`, `PROCESS`, etc.)
- Relationship hints that guide the traversal in Stage 2

Two adapters are available:

| Adapter | How it works | When to use |
|---|---|---|
| `DeterministicMiningAdapter` | Pattern matching and keyword extraction (no LLM) | Development, testing, cost-sensitive deployments |
| `VertexMiningAdapter` | Calls a Gemini / Claude model for entity extraction | Production, complex natural-language queries |

The mining result is a `MiningResult` object carrying `MinedEntity` objects, each with `entity_type`, `entity_value`, and `confidence`.

### Stage 2 — Aggregate

**Input:** `MiningResult`  
**Output:** graph evidence (paths, nodes, edges)

The aggregation stage queries the Spanner property graph to retrieve evidence relevant to the mined entities. It performs bounded multi-hop traversals constrained by `TenantId` and `AuthorizationScope`.

Two adapters:

| Adapter | How it works |
|---|---|
| `SpannerAggregationAdapter` | Executes GQL queries against the live graph (production default) |
| `DeterministicAggregationAdapter` | Returns fixed fixtures from config (testing only) |

The traversal is weight-guided: edges and nodes with higher `LogOddsWeight` are prioritized. The result is an `AggregationResult` containing `EvidencePath` objects — sequences of nodes and edges that support a claim.

### Stage 3 — Serialize

**Input:** `AggregationResult`  
**Output:** structured `SerializedFact` list

The serialization stage converts raw graph paths into structured, LLM-readable facts:

```json
{
  "fact_id": "fact_abc123",
  "claim": "Alice is the Data Owner of the payments dataset",
  "graph_path": "PERSON(alice) -[DATA_OWNER_OF]-> DATASET(payments)",
  "confidence": 0.87,
  "freshness_score": 0.94,
  "contradictions": [],
  "source_type": "path_based"
}
```

Each fact includes:
- **confidence** — derived from the edge weights along the supporting path
- **freshness_score** — exponential decay from `LastAccessed` timestamp; stale evidence scores lower
- **contradictions** — any SEMANTIC node that makes a conflicting claim about the same entities

### Stage 4 — Synthesize

**Input:** `SerializationResult` (list of `SerializedFact`)  
**Output:** grounded natural-language answer

The synthesis stage is the only LLM call in the pipeline. It receives only the serialized facts as context — never the raw graph, never the user's prior conversation. This architectural constraint is what prevents hallucination:

- The model is instructed to answer **only** from the provided facts
- If no facts have sufficient confidence, it returns an explicit **evidence-insufficiency signal** rather than guessing
- Contradictions found in Stage 3 are surfaced to the caller in `MindMapResponse.contradictions`

**Confidence gating:**
- **Soft gate** (default): low-confidence facts are included but flagged; the model is told to hedge
- **Hard gate** (configurable): facts below `confidence_threshold` are excluded from synthesis entirely

## Response Contract

```json
{
  "trace_id": "trace_abc123",
  "answer": "Alice is the Data Owner of the payments dataset as of Q3 2024.",
  "facts": [
    {
      "fact_id": "fact_abc123",
      "claim": "Alice is the Data Owner of the payments dataset",
      "confidence": 0.87,
      "freshness_score": 0.94
    }
  ],
  "contradictions": [],
  "evidence_sufficient": true,
  "latency_ms": {
    "mine": 12,
    "aggregate": 118,
    "serialize": 34,
    "synthesize": 312,
    "total": 476
  }
}
```

## Calling the Pipeline Directly

The pipeline is also exposed as a REST endpoint for orchestrators:

```bash
curl -X POST https://<service-url>/api/v1/mindmap/execute \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Who owns the payments dataset?",
    "session_id": "session_abc"
  }'
```

Most callers reach the pipeline through the `MEMORY_SEARCH` MCP tool, which wraps this endpoint and adds ABAC authorization and audit logging.

## Trace Observability

Every pipeline execution emits:
- A structured log entry with `trace_id`, per-stage latency, and fact count
- A Cloud Trace span covering the full pipeline and each stage as a child span
- A `mindmap_execution` metric in Cloud Monitoring
