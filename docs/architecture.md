# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Callers                                  │
│   AI Agents  │  Orchestrators  │  Internal Jobs  │  CLI/Tests  │
└──────┬──────────────┬────────────────┬──────────────────────────┘
       │              │                │
       ▼              ▼                ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Cloud Run (gen2)                               │
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │  MCP Service   │  │  MindMap API   │  │  Agent Orch.     │  │
│  │  /mcp/invoke   │  │ /mindmap/exec  │  │ /agent/respond   │  │
│  └───────┬────────┘  └───────┬────────┘  └────────┬─────────┘  │
│          │                   │                     │            │
│          └─────────┬─────────┘                     │            │
│                    ▼                               │            │
│          ┌─────────────────┐                       │            │
│          │  MindMap Pipeline│◄──────────────────────┘            │
│          │  Mine → Agg →   │                                    │
│          │  Serialize →    │                                    │
│          │  Synthesize     │                                    │
│          └────────┬────────┘                                    │
│                   │                                             │
│  ┌────────────────┼──────────────────────────────────────────┐ │
│  │ Support Services                                           │ │
│  │  MemoryAPI │ EvidenceService │ ABAC │ RetryLayer │ Audit   │ │
│  └────────────────┼──────────────────────────────────────────┘ │
└───────────────────┼──────────────────────────────────────────────┘
                    │
          ┌─────────▼──────────┐
          │   Cloud Spanner     │
          │  MemoryNode         │
          │  MemoryEdge         │
          │  AUDIT_EVENTS       │
          │  ENGRAM_EVIDENCE    │
          │  AgentMemoryGraph   │  ◄── GQL property graph
          └─────────────────────┘
```

## Components

### Cloud Run Service

The single deployable unit. Contains the FastAPI application that exposes all endpoints. Runs Python 3.14 with the full dependency graph installed via uv.

- **Startup**: initializes Spanner client and verifies database connectivity
- **Health**: `/health` endpoint returns `{"status": "healthy"}` once Spanner is reachable
- **Concurrency**: Cloud Run gen2 handles concurrency at the container level (async FastAPI)
- **Sizing**: 2 vCPU / 4 Gi, min 1 instance (dev/intg) / 2 instances (prod)

### MCP Service (`src/mcp/service.py`)

The primary interface for AI agents. Receives `MCPInvokeRequest` objects and routes them to the appropriate tool handler after:
1. Validating the request schema
2. Enforcing ABAC authorization (deny-by-default)
3. Writing an audit entry (GRANTED or DENIED with reason code)

The four tools map to internal services:
- `MEMORY_SEARCH` → MindMap pipeline
- `MEMORY_ADD_FACT` → MemoryAPI
- `MEMORY_LOG_TRACE` → MemoryAPI (audit write)
- `MEMORY_RECALL_CONTEXT` → MemoryAPI (context window read)

### MindMap Pipeline (`src/memory/mindmap_pipeline.py`)

Four-stage pipeline: Mine → Aggregate → Serialize → Synthesize. See [MindMap Pipeline](concepts/mindmap-pipeline.md) for full detail.

### MemoryAPI (`src/memory/api.py`)

Service layer over Cloud Spanner. All mutations go through the retry layer and idempotency check. Methods:
- `create_session(tenant_id, session_id)` — initialize session node
- `add_semantic_fact(tenant_id, entity_type, entity_id, attributes, relationship)` — ingest knowledge
- `retrieve_context_window(tenant_id, session_id, window_size)` — recall session turns
- `record_audit_event(tenant_id, source_node_id, event_type, attributes)` — append audit entry

### ABAC Layer (`src/security/governance.py`)

Attribute-Based Access Control. Every MCP tool call specifies an `AuthorizationScope` that limits what the agent is allowed to access:
- `allowed_node_ids` — specific nodes the agent can read/write
- `allowed_labels` — entity types (PERSON, SESSION, etc.)
- `allowed_memory_tiers` — which tiers (CONTEXT, SEMANTIC, AUDIT)
- `allowed_relationship_types` — edge types the agent can traverse

Default: **deny**. An empty or absent scope returns `DENIED_MISSING_AUTHORIZATION_SCOPE`.

### Retry and Idempotency (`src/db/retry.py`, `src/db/idempotency.py`)

All mutations carry a `request_id` used for idempotency. If the same `request_id` is replayed (e.g., after a network timeout), the mutation is a no-op. The retry layer applies exponential backoff for transient Spanner errors.

### Extraction Pipeline (`src/pipelines/`)

An independent ingestion subsystem that reads external data and writes it into the graph. Can run as part of the main service or as a separate process. See [Extraction Pipeline](user-guide/extraction-pipeline.md).

### Cloud Spanner

The graph database. Key properties:
- **External consistency** — all writes are linearizable
- **Property graph** — `AgentMemoryGraph` property graph enables GQL traversal queries
- **Schema** — 9 SQL migrations manage the schema; migrations are idempotent (`IF NOT EXISTS`)
- **Tenant isolation** — `TenantId` on every row; enforced at the application query layer

## Data Flows

### Agent reads memory (MEMORY_SEARCH)

```
Agent
  │─ POST /api/v1/mcp/invoke {tool: MEMORY_SEARCH, query: "...", scope: ...}
  │
  ├─ MCP Service validates request
  ├─ ABAC checks authorization_scope → GRANTED
  ├─ AUDIT_EVENTS write: MCP_AUTHORIZATION_GRANTED
  │
  ├─ MindMap.mine(query) → entities
  ├─ MindMap.aggregate(entities, tenant_id) → graph evidence paths
  ├─ MindMap.serialize(evidence) → structured facts with confidence/freshness
  ├─ MindMap.synthesize(facts) → grounded answer (LLM call)
  │
  └─ Response: {answer, facts, contradictions, evidence_sufficient}
```

### Agent writes a fact (MEMORY_ADD_FACT)

```
Agent
  │─ POST /api/v1/mcp/invoke {tool: MEMORY_ADD_FACT, entity_type: ..., attributes: ...}
  │
  ├─ MCP Service validates + ABAC check → GRANTED
  ├─ AUDIT_EVENTS write: MCP_AUTHORIZATION_GRANTED
  │
  ├─ MemoryAPI.add_semantic_fact(tenant_id, entity, attributes, relationship)
  │   ├─ idempotency check (request_id)
  │   ├─ UPSERT MemoryNode (TenantId, NodeId, Label, Attributes)
  │   └─ UPSERT MemoryEdge if relationship provided
  │
  └─ Response: {success: true}
```

### Document ingested

```
Caller
  │─ POST /api/v1/extract/document {file_bytes, doc_type, tenant_id}
  │
  ├─ DocumentExtractor extracts text blocks and entities
  ├─ FuzzyMatcher deduplicates entities against existing graph
  │
  ├─ For each unique entity:
  │   └─ MemoryAPI.add_semantic_fact(...)
  │
  └─ Response: {entities_extracted, entities_deduplicated, nodes_written}
```

## Security Boundaries

| Boundary | Mechanism |
|---|---|
| Service authentication | Cloud Run IAM (`roles/run.invoker` on the product SA) |
| Agent authorization | ABAC `AuthorizationScope` per request |
| Secret access | Secret Manager (Spanner credentials, app config) |
| Tenant isolation | `TenantId` column enforced at query layer |
| Cross-project Spanner | Product SA impersonates Spanner SA via `roles/iam.serviceAccountTokenCreator` |
| Audit trail | Immutable `AUDIT_EVENTS` — append-only, never deleted |

## Observability

- **Structured logs** — every request/response emits JSON logs with `trace_id`, `tenant_id`, `latency_ms`
- **Cloud Trace** — end-to-end traces with per-stage spans for the MindMap pipeline
- **Cloud Monitoring** — two alert policies (high error rate, high latency p99); configurable notification channels
- **Health endpoint** — `GET /health` returns `{"status": "healthy", "database": "initialized"}` once Spanner is ready
