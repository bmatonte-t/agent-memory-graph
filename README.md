# Agent Memory Graph

Agent Memory Graph is a GCP-native shared memory system for AI agents built around a tripartite graph model, grounded responses, and auditable orchestration.

The product is designed for multiple agents operating inside the same GCP project or organization, with deterministic behavior, strict safety boundaries, low token-spending retrieval, and low-hallucination output generation.

It combines:
- Durable long-term knowledge in Google Cloud Spanner Graph
- Session-aware recall for multi-turn agents
- Immutable operational traceability for trust, compliance, and debugging

## Why This Project Exists

Most agent systems fail in one of three ways: they forget context, invent unsupported answers, or cannot explain how a response was produced.

This repository addresses those gaps with:
- A structured memory topology (Context, Semantic, Audit)
- A grounding-first retrieval and synthesis pipeline (MindMap)
- MCP tool contracts for stable integration with orchestrators and agent runtimes
- End-to-end request correlation and telemetry
- Explicit no-evidence behavior (the system reports insufficient graph evidence instead of guessing)

## Memory Topology

The system models memory as three strictly isolated graph tiers with auditable cross-tier references:

- CONTEXT
  - Session-scoped conversation and turn history.
  - Optimized for short-horizon retrieval in active interactions.

- SEMANTIC
  - Durable entities, facts, and relationships with cognitive weighting.
  - Supports relevance through weighting and temporal maintenance strategies.

- AUDIT
  - Immutable reasoning and operation traces.
  - Enables reproducibility, observability, and compliance-oriented inspection.

## Core Runtime Capabilities

- MindMap pipeline execution for retrieval-grounded answers
- MCP tool service with typed contracts and stable error model
- Agent orchestration loop with execution modes:
  - single
  - supervisor_worker
  - vertex (env-gated adapter seam)
- Request id propagation across orchestration and tool invocation chain
- Structured operational logging and token/latency telemetry

## API Surface

Main FastAPI entrypoint:
- src/api/main.py

Primary endpoints:
- GET /health
- POST /api/v1/mindmap/execute
- POST /api/v1/mcp/invoke
- POST /api/v1/agent/respond

## Quick Start

### Prerequisites

- Python 3.14+
- uv
- just

### Install

1. Sync dependencies (all groups):
   uv sync --all-groups

2. Optional: install pre-commit hooks:
   just setup-hooks

### Run Locally

1. Start API server:
   uv run uvicorn src.api.main:app --reload

2. Health check:
   curl http://127.0.0.1:8000/health

## Developer Workflow

Common commands are defined in justfile:

- Run full tests:
  just test

- Run lint:
  just lint

- Run type checking:
  just check-types

- Run all quality gates:
  just check-all

- Build documentation:
  just build-docs

## Testing and Quality

Current repository test status is green in local validation for this branch, including unit and integration coverage for:

- Agent orchestration behavior and mode handling
- MCP API and service contracts
- MindMap API/pipeline behavior
- Memory API and audit trail flows
- Concurrency and multi-turn integration scenarios

## Phase Status Snapshot

- Phase 1: Foundation and core memory layer implemented
- Phase 2: MindMap query pipeline implemented behind API contract
- Phase 3: MCP tools, orchestration loop, and deployment scaffolding implemented
- Phase 4+: Hardening, marketplace readiness, pilot testing, and launch planning in progress

Reference roadmap:
- DEVELOPMENT_PLAN.md

## Deployment (Phase 3 Scaffold)

Cloud Run deployment helpers are available via just tasks:

1. Render manifest:
   just phase3-render-cloudrun <project_id>

2. Build image:
   just phase3-build-image <project_id>

3. Deploy service:
   just phase3-deploy-cloudrun <project_id>

Template artifacts:
- infrastructure/phase3/cloudrun-service.yaml
- scripts/render_phase3_cloudrun_manifest.py

## Documentation Index

- docs/api-reference.md
- docs/data-model-spec.md
- docs/phase1-validation-report.md
- docs/architecture/adr/
- docs/development/phase3-agent-integration-guide.md
- docs/development/phase3-mcp-tool-reference.md
- docs/marketplace-readiness-checklist.md
- docs/objectives.md

## Contributing

If you want to contribute:

1. Read docs/development/CONTRIBUTING.md
2. Run quality checks before opening a pull request
3. Include tests for behavior changes
4. Keep architecture and operational docs updated with implementation changes

## License

Add project license information here when licensing is finalized.
