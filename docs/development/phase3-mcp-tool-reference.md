# Phase 3 MCP Tool Reference

This document describes the Phase 3 MCP tool contract implemented by the API endpoint `/api/v1/mcp/invoke`.

## Request Contract

- `tool_name`: One of `memory_search`, `memory_add_fact`, `memory_log_trace`, `memory_recall_context`.
- `arguments`: Tool-specific JSON object.
- `session_id`: Optional session identifier.
- `request_id`: Optional request correlation identifier.

## Response Contract

- `tool_name`: Echo of requested tool.
- `request_id`: Echo of request identifier.
- `success`: Indicates whether invocation completed successfully.
- `latency_ms`: Invocation duration.
- `result`: Tool payload when successful.
- `error`: Error object when failed.
- `token_usage`: Estimated token telemetry fields.

## Error Model

- `validation_error`: Input contract violations.
- `backend_error`: Internal runtime or backend dependency failures.
- Pipeline stage error codes from MindMap are surfaced for search-specific failures.

## Fallback Policy

- Invalid input always returns `validation_error` and does not mutate memory.
- Backend failures are marked `retryable=true` where appropriate.
- Agent orchestration falls back to `Insufficient graph evidence.` when search fails or returns ungrounded data.

## Telemetry Fields

Each invocation emits structured logs for:

- Start event: tool name, request id, session id.
- Finish event: success, latency, error code, total estimated tokens.

## Tool Examples

### memory_search

Arguments:

```json
{
  "query": "What happened to project alpha budget?",
  "session_id": "session_1"
}
```

### memory_add_fact

Arguments:

```json
{
  "entity_type": "PERSON",
  "entity_id": "user_123",
  "attributes": {"name": "Alex"}
}
```

### memory_log_trace

Arguments:

```json
{
  "event_type": "AGENT_ORCHESTRATION_TURN",
  "source_node_id": "session_1",
  "decision_context": {"step": "search"}
}
```

### memory_recall_context

Arguments:

```json
{
  "session_id": "session_1",
  "window_size": 10
}
```
