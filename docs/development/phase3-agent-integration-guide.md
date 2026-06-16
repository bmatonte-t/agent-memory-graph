# Phase 3 Agent Integration Guide

This guide explains how the Phase 3 orchestration flow uses MCP tools as the primary memory path.

## Endpoints

- MCP invoke: `/api/v1/mcp/invoke`
- Agent respond: `/api/v1/agent/respond`

## Orchestration Flow

1. Receive user prompt and session context.
2. Recall context via `memory_recall_context`.
3. Search memory graph via `memory_search`.
4. Produce grounded response or insufficiency fallback.
5. Persist turn reasoning with `memory_log_trace`.

## Execution Modes

- `single`: Current baseline implementation.
- `supervisor_worker`: Supported contract path, currently executes baseline single flow.
- `vertex`: Uses Vertex adapter when configured, otherwise falls back to single with a structured warning log.

## Request Correlation

- `request_id` is accepted in orchestration request.
- The same `request_id` is propagated to all MCP tool calls.
- Response includes `request_id` and per-tool traces with request ids.

## Observability

Structured logs are emitted for:

- `agent_orchestration_start`
- `agent_orchestration_finish`
- `mcp_tool_invoke_start`
- `mcp_tool_invoke_finish`

Each record includes request correlation, latency, and status fields.

## Extension Points

- Replace `NotConfiguredVertexAdapter` with a concrete Vertex ADK implementation.
- Add real supervisor/worker task planner while preserving the same response contract.

## Validation Checklist

- Unit tests pass for MCP service and API contracts.
- Unit tests pass for orchestration and mode behavior.
- Integration tests pass for multi-turn memory visibility and session isolation.
- Integration tests pass for request id observability and concurrent session behavior.
