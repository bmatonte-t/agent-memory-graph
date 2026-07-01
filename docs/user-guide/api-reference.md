# REST API Reference

Base URL: `https://<cloud-run-service-url>`

All requests accept and return `application/json`. Error responses use a stable envelope with `code` and `error` fields.

---

## Health

### `GET /health`

Liveness and readiness probe. Returns `200 OK` once the Spanner database is initialized and reachable.

**Example:**

```bash
curl http://localhost:8000/health
```

**Response:**

```json
{
  "status": "healthy",
  "database": "initialized",
  "timestamp": "2025-03-15T14:22:48Z"
}
```

**Error (503):** returned if Spanner is not yet reachable at startup.

Used by: Cloud Run liveness and startup probes. Also useful for manual health checks after deployment.

---

## MCP Tools

### `POST /api/v1/mcp/invoke`

Invoke one MCP tool. This is the primary interface for AI agents.

See [MCP Tools](mcp-tools.md) for full documentation of each tool, request envelopes, and response contracts.

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/mcp/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "acme",
    "tool_name": "memory_search",
    "arguments": {
      "query": "Who owns the payments dataset?",
      "session_id": "session_abc123"
    },
    "agent_id": "agent_xyz",
    "request_id": "req_001",
    "authorization_scope": {
      "agent_id": "agent_xyz",
      "allowed_labels": ["PERSON", "DATASET"],
      "allowed_memory_tiers": ["SEMANTIC"],
      "allowed_relationship_types": ["DATA_OWNER_OF"]
    }
  }'
```

**Request body:** `MCPInvokeRequest`
**Response body:** `MCPInvokeResponse`

**Error responses:**

| Status | Code | When |
|---|---|---|
| 400 | `validation_error` | Request body fails schema validation |
| 403 | `denied_*` | Authorization denied |
| 500 | `backend_error` | Unexpected server error |

---

## MindMap Pipeline

### `POST /api/v1/mindmap/execute`

Execute the MindMap reasoning pipeline directly. For orchestrators that want to call the pipeline without going through MCP authorization.

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/mindmap/execute \
  -H "Content-Type: application/json" \
  -d '{"query": "Who approved the merger?", "session_id": "session_abc123"}'
```

**Request body:**

```json
{
  "query": "Who is the data owner of the revenue dataset?",
  "session_id": "session_abc123"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `query` | string | Yes | Natural-language question |
| `session_id` | string | No | Session context for graph scoping |

**Response body:**

```json
{
  "trace_id": "trace_abc123",
  "answer": "Carlos Mendez is the Data Owner of the revenue dataset.",
  "facts": [
    {
      "fact_id": "fact_001",
      "claim": "Carlos Mendez holds DATA_OWNER_OF on revenue dataset",
      "confidence": 0.91,
      "freshness_score": 0.88,
      "graph_path": "PERSON(carlos)-[DATA_OWNER_OF]->DATASET(revenue)"
    }
  ],
  "contradictions": [],
  "evidence_sufficient": true,
  "latency_ms": {
    "mine": 15,
    "aggregate": 124,
    "serialize": 38,
    "synthesize": 299,
    "total": 476
  }
}
```

**Note:** this endpoint does not enforce ABAC authorization. Use `POST /api/v1/mcp/invoke` with `tool_name: memory_search` for agent-facing calls that need authorization gating and audit logging.

---

## Agent Orchestration

### `POST /api/v1/agent/respond`

Execute one full agent cycle: receives a prompt, runs tool calls through the MCP service, and returns a synthesized response. Supports three execution modes.

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/agent/respond \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Who owns the revenue dataset and what is their email?",
    "session_id": "session_abc123",
    "tenant_id": "acme",
    "mode": "SINGLE",
    "authorization_scope": {
      "agent_id": "agent_xyz",
      "allowed_labels": ["PERSON", "DATASET"],
      "allowed_memory_tiers": ["SEMANTIC"],
      "allowed_relationship_types": ["DATA_OWNER_OF"]
    }
  }'
```

**Request body:**

```json
{
  "prompt": "Who owns the revenue dataset and what is their email?",
  "session_id": "session_abc123",
  "tenant_id": "latam-airlines",
  "mode": "SINGLE",
  "authorization_scope": {
    "agent_id": "agent_xyz",
    "allowed_labels": ["PERSON", "DATASET"],
    "allowed_memory_tiers": ["SEMANTIC"],
    "allowed_relationship_types": ["DATA_OWNER_OF"]
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `prompt` | string | Yes | User prompt |
| `session_id` | string | Yes | Session identifier |
| `tenant_id` | string | Yes | Tenant identifier |
| `mode` | string | No | `SINGLE` (default), `SUPERVISOR_WORKER`, or `VERTEX` |
| `authorization_scope` | object | Yes | ABAC scope applied to all MCP calls in this cycle |

**Execution modes:**

| Mode | Description |
|---|---|
| `SINGLE` | One agent processes the prompt and calls MCP tools directly |
| `SUPERVISOR_WORKER` | A supervisor agent decomposes the task and dispatches worker agents |
| `VERTEX` | Routes through Vertex AI (Claude or Gemini) for the model call |

**Response body:**

```json
{
  "response_text": "Carlos Mendez (carlos.mendez@latam.com) is the Data Owner.",
  "tool_calls": [
    {
      "tool_name": "memory_search",
      "success": true,
      "latency_ms": 476.2
    }
  ],
  "execution_mode": "SINGLE",
  "session_action_count": 4,
  "latency_ms": 521.0
}
```

---

## Internal Maintenance

These endpoints are not exposed to agents. They are called by Cloud Scheduler jobs using the product service account.

### `POST /internal/decay-weights`

Apply temporal decay to all node and edge weights in the tenant graph. Intended to run on a daily schedule.

**Example:**

```bash
curl -X POST http://localhost:8000/internal/decay-weights \
  -H "Content-Type: application/json" \
  -d '{"decay_rate": 0.05}'
```

**Request body:** empty `{}` (or pass `decay_rate` float 0.0–1.0, default `0.05`)

**Response:**

```json
{
  "status": "ok",
  "operation": "decay_weights",
  "decay_rate": 0.05,
  "updated_nodes": 1842
}
```

### `POST /internal/prune-weights`

Remove nodes whose `LogOddsWeight` has fallen below the configured pruning threshold. Only SEMANTIC nodes without active edges are removed.

**Example:**

```bash
curl -X POST http://localhost:8000/internal/prune-weights \
  -H "Content-Type: application/json" \
  -d '{"threshold": 0.30}'
```

**Request body:** empty `{}` (or pass `threshold` float 0.0–1.0, default `0.30`)

**Response:**

```json
{
  "status": "ok",
  "operation": "prune_weights",
  "threshold": 0.3,
  "updated_nodes": 47
}
```

---

## Error Response Format

All error responses use a stable envelope:

```json
{
  "code": "validation_error",
  "error": "field 'query' is required",
  "request_id": "req_abc123"
}
```

| Status | When |
|---|---|
| 400 | Validation error (missing field, invalid type) |
| 403 | Permission denied (ABAC rejection) |
| 422 | Request body does not match schema |
| 500 | Unhandled server error |
