# Agent Memory Graph

Agent Memory Graph is a GCP-native shared memory platform for AI agents.

It is designed for multi-agent environments where trust, grounding, and auditability matter as much as answer quality. The system combines a strict tripartite memory model with deterministic retrieval and synthesis stages so responses are tied to graph evidence instead of model guesswork.

## What Problem It Solves

Most agent systems degrade in production because they:

- lose short-term context,
- hallucinate unsupported claims, or
- cannot explain how an answer was produced.

Agent Memory Graph addresses this with:

- memory tier isolation (Context, Semantic, Audit),
- a grounding-first MindMap pipeline,
- typed MCP tools for stable orchestration,
- immutable audit traces for reproducibility.

## Core Architecture

### Tripartite Memory Topology

- CONTEXT
  - Session-scoped turn history and short-horizon recall.

- SEMANTIC
  - Durable entities and facts with cognitive weighting and temporal decay.

- AUDIT
  - Immutable operation and reasoning traces for compliance and debugging.

### MindMap Reasoning Pipeline

1. Mine
   - Extract intent and entities from user query.

2. Aggregate
   - Retrieve graph evidence with bounded traversal and cognitive horizon filters.

3. Serialize
   - Convert graph evidence into traceable fact payloads.

4. Synthesize
   - Generate response only from serialized evidence.
   - If evidence is insufficient, return explicit insufficiency.

## Runtime Capabilities

- FastAPI API surface for memory and orchestration operations.
- MCP tool service for memory search, fact ingestion, audit logging, and context recall.
- Agent orchestration modes: single, supervisor_worker, vertex.
- Structured logging, tracing hooks, and metrics instrumentation.
- Tenant-aware memory access patterns and hardened error envelopes.

## API Endpoints

Primary endpoints:

- GET /health
- POST /api/v1/mindmap/execute
- POST /api/v1/mcp/invoke
- POST /api/v1/agent/respond

Internal maintenance endpoints:

- POST /internal/decay-weights
- POST /internal/prune-weights

## Quickstart

### Prerequisites

- Python 3.14+
- uv
- just

### Install Dependencies

```bash
uv sync --all-groups
```

Optional hook setup:

```bash
just setup-hooks
```

### Run Locally

```bash
uv run uvicorn src.api.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## Developer Commands

Common commands from justfile:

```bash
just test
just lint
just check-types
just check-format
just format
just test-coverage
just check-all
```

Documentation tasks:

```bash
just serve-docs
just build-docs
```

## Testing and Quality

The project uses:

- pytest for unit and integration testing,
- ruff for linting and formatting,
- basedpyright for type checking,
- docstr-coverage for docstring coverage checks.

Recommended pre-PR gate:

```bash
just check-all
```

## Deployment (Phase 3 Scaffold)

Cloud Run helper tasks are available:

```bash
just phase3-render-cloudrun <project_id>
just phase3-build-image <project_id>
just phase3-deploy-cloudrun <project_id>
```

Deployment templates and scripts:

- infrastructure/phase3/cloudrun-service.yaml
- scripts/render_phase3_cloudrun_manifest.py

## Project Status

- Phase 1: Foundation and core memory layer complete.
- Phase 2: MindMap retrieval and grounding pipeline complete.
- Phase 3: MCP tooling and orchestration integration complete.
- Phase 4: Security, observability, and marketplace hardening in progress.
- Phase 4C: Observability safety baseline complete.
- Phase 5-6: Comparative pilot and launch preparation planned.

Roadmap reference:

- DEVELOPMENT_PLAN.md

## Documentation Index

- docs/api-reference.md
- docs/data-model-spec.md
- docs/objectives.md
- docs/marketplace-readiness-checklist.md
- docs/architecture/adr/
- docs/development/phase3-agent-integration-guide.md
- docs/development/phase3-mcp-tool-reference.md
- docs/development/phase4-local-user-testing.md

## Contributing

1. Read docs/development/CONTRIBUTING.md.
2. Make focused changes and include tests.
3. Run quality gates before opening a PR.
4. Update docs when behavior or architecture changes.

## License

License details will be published when project licensing is finalized.
