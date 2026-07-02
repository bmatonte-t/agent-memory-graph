# ADR-0002: Synthesis Model Selection Policy

- Status: Accepted
- Date: 2026-07-01
- Owners: AMG core engineering

## Context

EPIC-05 requires deciding whether synthesis model selection should be caller-
configurable per request or fixed by deployment configuration.

## Decision

Use **deployment-fixed model selection** for extraction and synthesis.

- Callers cannot override model names via MCP or REST request payloads.
- Model changes are managed via controlled configuration and release process.

## Consequences

- Predictable behavior and cost profile per environment.
- Reduced attack surface (no prompt-level model switching by callers).
- Slower experimentation compared to per-request override.

## Implementation references

- `src/memory/mindmap_pipeline.py`
- `docs/architecture.md`
- `docs/deployment.md`
