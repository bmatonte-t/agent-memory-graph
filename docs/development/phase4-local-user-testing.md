# Phase 4 Local User Testing Guide

This guide shows how to exercise the product locally during Phase 4 using the repo's simulators and offline stubs. It is designed for validation on a laptop without needing deployed GCP infrastructure.

## What This Covers

- Spanner emulator for persistence and audit-flow testing.
- Local Vertex stub mode for deterministic agent behavior.
- FastAPI endpoints for memory, MCP, and agent orchestration.
- Negative validation scenarios that verify redaction and guardrails.

## Prerequisites

- Python 3.14 with `uv` installed.
- Google Cloud SDK installed if you want to run the Spanner emulator helper script.
- A fresh checkout with dependencies installed via `just install` or `uv sync --all-groups`.

## Local Simulator Setup

Open one terminal for the Spanner emulator and a second terminal for the application.

### 1. Start the Spanner emulator

```bash
./scripts/start-emulator.sh
```

This helper starts the local Spanner emulator, creates the test instance and database, and exports the emulator host for the current shell session.

### 2. Enable the local Vertex stub

For offline Phase 4 testing, use the deterministic stub path instead of the hosted Vertex adapter:

```bash
export AGENT_VERTEX_ENABLED=true
export AGENT_VERTEX_STUB_ENABLED=true
export AGENT_VERTEX_STUB_RESPONSE="Local stub Vertex response."
export AGENT_VERTEX_STUB_GROUNDED=true
```

The stub is defined in [src/agent/vertex_adapter.py](../../src/agent/vertex_adapter.py) and lets you test the orchestration path without external model calls.

### 3. Start the API

```bash
uv run uvicorn src.api.main:app --reload
```

If you want a reproducible preflight check before testing, run:

```bash
just check-all
```

## Recommended Test Flow

### Smoke test 1: Health and startup

```bash
curl http://127.0.0.1:8000/health
```

Expected result:

- HTTP 200.
- Status is `healthy`.
- No stack traces or tenant identifiers in the response.

### Smoke test 2: MindMap execution

```bash
curl -X POST http://127.0.0.1:8000/api/v1/mindmap/execute \
  -H 'Content-Type: application/json' \
  -d '{"query":"Explain project alpha budget trend","session_id":"sess_local_1"}'
```

Expected result:

- A grounded response with trace metadata.
- A trace object containing mined entities, path IDs, and fact IDs.
- If evidence is insufficient, the response should be exactly `Insufficient graph evidence.`

### Smoke test 3: MCP tool invocation

```bash
curl -X POST http://127.0.0.1:8000/api/v1/mcp/invoke \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"tenant_local","tool_name":"memory_search","session_id":"sess_local_1","arguments":{"query":"Explain project alpha budget trend"}}'
```

Expected result:

- Stable MCP response envelope.
- Token usage included.
- Request ID echoed back when provided.

### Smoke test 4: Agent orchestration

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agent/respond \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"tenant_local","prompt":"What changed?","session_id":"sess_local_1","mode":"vertex"}'
```

Expected result:

- The Vertex stub path returns the configured stub response.
- The response is grounded when the stub is configured that way.
- Tool calls are still traced through the orchestration envelope.

## Negative Tests

Run these to confirm Phase 4 hardening:

1. Invalid tool name in `/api/v1/mcp/invoke` should return a sanitized validation error and should not expose the full tool enum.
2. Missing `tenant_id` should return a helpful field-level validation message without leaking internal schema details.
3. Direct audit mutation attempts should be rejected, including prefixed SQL forms such as comment-wrapped or CTE-wrapped statements.
4. Error responses should not include file paths, line numbers, or Python tracebacks.

## Validation Checklist

- The Spanner emulator starts cleanly and the test database is available.
- The API boots with the local Vertex stub enabled.
- `mindmap/execute`, `mcp/invoke`, and `agent/respond` all complete locally.
- Sanitized validation errors are returned for bad input.
- Audit writes remain append-only.
- Logs include request correlation but not raw sensitive payloads.

## Useful References

- [Phase 3 Agent Integration Guide](phase3-agent-integration-guide.md)
- [Phase 3 MCP Tool Reference](phase3-mcp-tool-reference.md)
- [Testing Changes](testing_changes.md)
- [Project README](../../README.md)
