# MCP Tools

Agent Memory Graph exposes six tools through the Model Context Protocol (MCP).

## Discovery endpoint

Clients can auto-configure against the versioned discovery manifest:

```http
GET /.well-known/mcp
```

Optional query parameter:

- `version`: contract version requested by the client. Current supported value: `1.0`.

Example:

```bash
curl -s "https://<service-url>/.well-known/mcp?version=1.0"
```

The response includes:

- `manifest_version` and `supported_versions`.
- `invoke_endpoint` used for tool execution.
- `tools` and `tool_catalog` with parameter metadata.
- Stable error catalog and compatibility notes.

## Invocation endpoint

All tools are executed via the same endpoint:

```http
POST /api/v1/mcp/invoke
```

Every request follows the same envelope:

```json
{
  "tenant_id": "latam-airlines",
  "tool_name": "memory_search",
  "arguments": { ... },
  "session_id": "session_abc123",
  "agent_id": "agent_xyz",
  "request_id": "req_unique_id",
  "authorization_scope": {
    "agent_id": "agent_xyz",
    "allowed_node_ids": [],
    "allowed_labels": ["SESSION", "PERSON", "CONCEPT"],
    "allowed_memory_tiers": ["CONTEXT", "SEMANTIC"],
    "allowed_relationship_types": ["REFERENCES", "AUTHORED_BY"]
  }
}
```

Every response follows the same envelope:

```json
{
  "tool_name": "memory_search",
  "success": true,
  "latency_ms": 312.4,
  "result": { ... },
  "error": null,
  "token_usage": {
    "input_tokens": 156,
    "output_tokens": 432,
    "total_tokens": 588,
    "estimated": true
  }
}
```

## Authorization

All tools require a valid `authorization_scope`. The scope is an allowlist — anything not explicitly permitted is denied. An absent or empty scope returns a `DENIED_MISSING_AUTHORIZATION_SCOPE` error and writes a DENIED audit entry; the tool is not executed.

| Field | Type | Effect |
|---|---|---|
| `allowed_node_ids` | `string[]` | Restrict reads/writes to specific node IDs |
| `allowed_labels` | `string[]` | Restrict to specific entity types |
| `allowed_memory_tiers` | `string[]` | `CONTEXT`, `SEMANTIC`, `AUDIT` |
| `allowed_relationship_types` | `string[]` | Edge types the agent may traverse |

Pass empty arrays only for fields you intentionally want to deny access to. To allow all labels, pass the full set of labels your workflow uses.

---

## MEMORY_SEARCH

Answers a natural-language query by retrieving and synthesizing evidence from the graph. This is the primary tool for grounded question answering.

**Arguments:**

| Field | Type | Required | Description |
|---|---|---|---|
| `query` | string | Yes | Natural-language question |
| `session_id` | string | No | Session ID for context scoping |

**Example request:**

```json
{
  "tenant_id": "latam-airlines",
  "tool_name": "memory_search",
  "arguments": {
    "query": "Who is the data owner of the revenue dataset?",
    "session_id": "session_abc123"
  },
  "agent_id": "agent_xyz",
  "request_id": "req_001",
  "authorization_scope": {
    "agent_id": "agent_xyz",
    "allowed_labels": ["PERSON", "DATASET", "ROLE"],
    "allowed_memory_tiers": ["SEMANTIC"],
    "allowed_relationship_types": ["DATA_OWNER_OF", "HAS_ROLE"]
  }
}
```

**Example response:**

```json
{
  "tool_name": "memory_search",
  "success": true,
  "latency_ms": 476.2,
  "result": {
    "trace_id": "trace_abc123",
    "answer": "Carlos Mendez is the Data Owner of the revenue dataset as of Q3 2024.",
    "facts": [
      {
        "fact_id": "fact_001",
        "claim": "Carlos Mendez holds the DATA_OWNER_OF relationship to the revenue dataset",
        "confidence": 0.91,
        "freshness_score": 0.88
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
}
```

**When `evidence_sufficient` is false:**

The answer field contains an explicit insufficiency statement rather than a fabricated answer. The caller should treat this as a knowledge gap signal — the fact is not in the graph yet.

---

## MEMORY_ADD_FACT

Ingests a semantic fact into the graph. Use this when an agent discovers or confirms organizational knowledge that should be persisted for future queries.

**Arguments:**

| Field | Type | Required | Description |
|---|---|---|---|
| `entity_type` | string | Yes | Node label (e.g., `PERSON`, `DATASET`, `PROCESS`) |
| `entity_id` | string | Yes | Unique identifier for this entity |
| `attributes` | object | Yes | Free-form JSON properties for the node |
| `relationship` | object | No | Edge to another node (see below) |

**Relationship object:**

```json
{
  "rel_type": "DATA_OWNER_OF",
  "target_node_id": "dataset_revenue",
  "target_node_type": "DATASET",
  "weight": 0.9
}
```

**Example request:**

```json
{
  "tenant_id": "latam-airlines",
  "tool_name": "memory_add_fact",
  "arguments": {
    "entity_type": "PERSON",
    "entity_id": "person_carlos_mendez",
    "attributes": {
      "name": "Carlos Mendez",
      "email": "carlos.mendez@latam.com",
      "squad": "Revenue Analytics"
    },
    "relationship": {
      "rel_type": "DATA_OWNER_OF",
      "target_node_id": "dataset_revenue",
      "target_node_type": "DATASET",
      "weight": 0.9
    }
  },
  "agent_id": "agent_xyz",
  "request_id": "req_002",
  "authorization_scope": {
    "agent_id": "agent_xyz",
    "allowed_labels": ["PERSON", "DATASET"],
    "allowed_memory_tiers": ["SEMANTIC"],
    "allowed_relationship_types": ["DATA_OWNER_OF"]
  }
}
```

**Example response:**

```json
{
  "tool_name": "memory_add_fact",
  "success": true,
  "latency_ms": 48.3,
  "result": {
    "node_id": "person_carlos_mendez",
    "edge_written": true,
    "idempotent": false
  }
}
```

`idempotent: true` means the same `request_id` was seen before — the mutation was a no-op (safe to retry).

---

## MEMORY_LOG_TRACE

Writes an audit event to the immutable audit log. Use this to record reasoning steps, consent decisions, or compliance checkpoints.

**Arguments:**

| Field | Type | Required | Description |
|---|---|---|---|
| `event_type` | string | Yes | Event classification (e.g., `REASONING_STEP`, `CONSENT_GRANTED`) |
| `source_node_id` | string | Yes | The session or node that triggered this event |
| `decision_context` | object | Yes | Free-form JSON context for the event |

**Example request:**

```json
{
  "tenant_id": "latam-airlines",
  "tool_name": "memory_log_trace",
  "arguments": {
    "event_type": "POLICY_CHECK_PASSED",
    "source_node_id": "session_abc123",
    "decision_context": {
      "policy": "data_access_policy_v2",
      "resource": "dataset_revenue",
      "decision": "ALLOW",
      "reason": "user has DATA_STEWARD role"
    }
  },
  "agent_id": "agent_xyz",
  "request_id": "req_003",
  "authorization_scope": {
    "agent_id": "agent_xyz",
    "allowed_memory_tiers": ["AUDIT"],
    "allowed_node_ids": ["session_abc123"]
  }
}
```

**Example response:**

```json
{
  "tool_name": "memory_log_trace",
  "success": true,
  "latency_ms": 21.1,
  "result": {
    "event_id": "event_abc456",
    "written_at": "2025-03-15T14:23:01Z"
  }
}
```

Audit events are immutable. There is no update or delete operation.

---

## MEMORY_RECALL_CONTEXT

Retrieves the most recent turns from the current session's CONTEXT tier. Use this at the start of a response to load working memory without passing the full conversation history in the prompt.

**Arguments:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `session_id` | string | Yes | — | The session to recall |
| `window_size` | integer | No | 10 | Number of recent turns to return |

**Example request:**

```json
{
  "tenant_id": "latam-airlines",
  "tool_name": "memory_recall_context",
  "arguments": {
    "session_id": "session_abc123",
    "window_size": 5
  },
  "agent_id": "agent_xyz",
  "request_id": "req_004",
  "authorization_scope": {
    "agent_id": "agent_xyz",
    "allowed_memory_tiers": ["CONTEXT"],
    "allowed_node_ids": ["session_abc123"]
  }
}
```

**Example response:**

```json
{
  "tool_name": "memory_recall_context",
  "success": true,
  "latency_ms": 34.7,
  "result": {
    "session_id": "session_abc123",
    "turns": [
      {
        "node_id": "turn_003",
        "label": "TURN",
        "attributes": {
          "role": "user",
          "content": "Who owns the revenue dataset?",
          "timestamp": "2025-03-15T14:22:48Z"
        },
        "log_odds_weight": 0.75
      },
      {
        "node_id": "turn_004",
        "label": "TURN",
        "attributes": {
          "role": "assistant",
          "content": "Carlos Mendez is the Data Owner.",
          "timestamp": "2025-03-15T14:23:01Z"
        },
        "log_odds_weight": 0.75
      }
    ],
    "total_returned": 2
  }
}
```

---

## Error Codes

When `success` is `false`, the response includes an error object:

```json
{
  "success": false,
  "error": {
    "code": "validation_error",
    "message": "authorization_scope is required",
    "retryable": false
  }
}
```

| Code | Retryable | Meaning |
|---|---|---|
| `validation_error` | No | Request schema is invalid |
| `denied_missing_scope` | No | `authorization_scope` absent |
| `denied_scope_violation` | No | Requested resource not in scope |
| `retrieval_error` | Yes | Spanner read failed transiently |
| `grounding_error` | No | Evidence found but synthesis failed |
| `backend_error` | Yes | Unexpected server error |
| `timeout_error` | Yes | Pipeline exceeded deadline |
