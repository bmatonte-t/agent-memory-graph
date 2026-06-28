# Agent Memory Graph

**Enterprise-grade AI agent coordination platform for single organizations.**

Agent Memory Graph is a deterministic, grounding-first memory system for coordinating multiple AI agents within an enterprise. It eliminates hallucination, preserves context across sessions, and provides immutable audit trails for compliance—all deployed within your GCP organization.

## The Problem

Enterprise AI deployments fail when:

- **Agents lose context** between sessions, forcing users to re-explain problems
- **Responses lack evidence**, making it impossible to audit decisions or debug failures
- **Agents hallucinate** facts not grounded in organizational data
- **Multi-agent coordination breaks**, with conflicting decisions or redundant work
- **Compliance is impossible**, because there's no audit trail of reasoning

Agent Memory Graph solves this by:

- **Grounding every response** in graph-evidence (no hallucination)
- **Preserving organizational context** across all agents and sessions
- **Providing immutable audit trails** for compliance and debugging
- **Enabling agent coordination** through shared, deterministic memory
- **Isolating tenant data** strictly at the database and API layers

## Core Architecture

Agent Memory Graph uses a **strict tripartite memory model** with deterministic retrieval and synthesis pipelines:

### Memory Tiers

- **CONTEXT**: Session-scoped turn history and short-horizon recall (user requests, responses, intermediate states)
- **SEMANTIC**: Durable organizational facts with cognitive weighting and temporal decay (entities, relationships, discovered insights)
- **AUDIT**: Immutable operation and reasoning traces (who accessed what, reasoning chain, consent decisions)

Each tier is isolated: writes and reads never cross tiers in a single transaction.

### MindMap Reasoning Pipeline

Every agent response follows this deterministic flow:

1. **Mine** — Extract intent and entities from the user request
2. **Aggregate** — Retrieve graph evidence with bounded traversal and cognitive filters
3. **Serialize** — Convert evidence to structured, traceable fact payloads
4. **Synthesize** — Generate response *only* from serialized evidence; fail gracefully if evidence insufficient

**No direct LLM answering from user input.** All responses are grounded.

## Enterprise Deployment Model

Agent Memory Graph is deployed as an **isolated single-organization service**:

- **Fixed Organization Context** — All agents in the organization share memory within the same company_id
- **No Multi-Tenancy** — Strict tenant isolation at database and API levels (no cross-org data leakage)
- **Pluggable Governance** — Choose between internal policy (ABAC) or external policy delegation (connect to your policy service)
- **GCP Organization Bound** — Deployed within your GCP project or organization

### Configuration

Enable org-wide deployment in `config.yaml`:

```yaml
single_company:
  enabled: true
  company_id: "your-org-id"
  auth_mode: "internal"  # or "external" for policy delegation
  external_auth_url: null  # provide URL if external mode
```

### Governance Options

**Internal ABAC** (default):
- Uses existing authorization policies stored in Spanner
- No external dependencies
- Suitable for organizations with centralized policy management

**External Delegation** (enterprise):
- Delegates authorization decisions to your policy service (e.g., Entitlements Platform, Okta, Auth0)
- Your service receives `POST /authorize` with agent context and responds with allow/deny
- Enables sync between your identity infrastructure and agent permissions

### What You Get

✅ **Isolation** — Complete data isolation for your organization
✅ **Auditability** — Every agent decision is logged and traceable
✅ **Compliance** — Immutable audit trails for regulatory requirements
✅ **Multi-Agent Coordination** — All agents share organizational memory
✅ **No Context Loss** — Session history preserved indefinitely

## API Surface

Core memory and orchestration endpoints:

- **GET /health** — Health check and readiness probe
- **POST /api/v1/mindmap/execute** — Execute MindMap reasoning pipeline (Mine → Aggregate → Synthesize)
- **POST /api/v1/mcp/invoke** — Invoke MCP tools for memory search, ingestion, audit querying
- **POST /api/v1/agent/respond** — Orchestrate agent responses across single/supervisor/vertex modes

Internal maintenance endpoints:

- **POST /internal/decay-weights** — Apply cognitive weight decay (scheduled or manual)
- **POST /internal/prune-weights** — Prune low-confidence evidence from Semantic tier

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

The project maintains production-grade quality through:

- **Unit & Integration Tests**: pytest (843 tests, all passing)
- **Type Safety**: basedpyright strict mode (0 errors, 0 warnings)
  - SDK calls isolated behind typed Protocol boundaries (see [ADR-0002](docs/architecture/adr/ADR-0002-type-safety-sdk-boundaries.md))
  - No `# type: ignore` comments in application code
  - All functions fully annotated per Python 3.14 standards
- **Linting & Formatting**: ruff (100% compliant)
- **Docstring Coverage**: 93.6% (Excellent)

Recommended pre-PR gate:

```bash
just check-all  # Lint + type-check + format + tests + docstrings
```

Type checking specifically:

```bash
just check-types  # basedpyright strict mode (0 errors required)
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

**Production-Ready for Enterprise Deployment**

- ✅ **Phase 1**: Core memory architecture (Context, Semantic, Audit tiers)
- ✅ **Phase 2**: MindMap retrieval and grounding pipeline
- ✅ **Phase 3**: MCP tooling and agent orchestration
- ✅ **Phase 4**: Security hardening (ABAC, org-wide isolation, audit trails)
- ✅ **Phase 4C**: Observability and compliance baseline
- ✅ **Phase 4D**: Type Safety Infrastructure (SDK wrapper boundaries, 0 type errors)
  - Protocol-based SDK wrappers for BigQuery, Cloud Scheduler, Cloud Spanner
  - Strict type checking with basedpyright (0 errors, 0 warnings)
  - See [ADR-0002](docs/architecture/adr/ADR-0002-type-safety-sdk-boundaries.md) for architecture
- ✅ **Phase 5**: Enterprise governance adapters (internal ABAC + external delegation)
- 🔄 **Current**: Customer pilot and integration support

Roadmap:

- [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) — Technical roadmap
- [docs/CONSOLIDATION_NOTES.md](docs/CONSOLIDATION_NOTES.md) — Architecture and deployment patterns

## Document Extraction Pipeline

A production-ready subsystem for ingesting, extracting entities from, and deduplicating documents across PDFs and PowerPoint files. The pipeline includes:

- **Document Extraction** (Phase B1): Text and entity extraction from PDF/PPTX
- **Entity Deduplication** (Phase B2): Fuzzy matching with confidence scoring
- **Pipeline Orchestration** (Phase B3): Coordinated extraction across batches
- **REST API** (Phase C): FastAPI service with extraction endpoints
- **Cloud Run Deployment** (Phase D): Production-ready container deployment
- **Integration Tests** (Phase E): 22 comprehensive end-to-end tests

### Extraction Pipeline Quick Links

- **Quickstart**: [EXTRACTION_PIPELINE_QUICKSTART.md](docs/EXTRACTION_PIPELINE_QUICKSTART.md)
- **API Reference**: [EXTRACTION_PIPELINE_API_REFERENCE.md](docs/EXTRACTION_PIPELINE_API_REFERENCE.md)
- **Architecture**: [EXTRACTION_PIPELINE_ARCHITECTURE.md](docs/EXTRACTION_PIPELINE_ARCHITECTURE.md)
- **Deployment Guide**: [EXTRACTION_PIPELINE_DEPLOYMENT.md](docs/EXTRACTION_PIPELINE_DEPLOYMENT.md)

### Extraction Pipeline Test Status

- ✅ **746 tests passing** (all phases)
- ✅ **100% linting clean** (ruff compliance)
- ✅ **95%+ code coverage**
- ✅ **Production ready** (deployed to Cloud Run)

## Documentation Index

### Architecture & Design Decisions

- **docs/architecture/adr/ADR-0001-phase-one-architecture.md** — Core architecture direction
- **docs/architecture/adr/ADR-0002-type-safety-sdk-boundaries.md** — SDK wrapper pattern and type safety
- docs/architecture/decision-log.md — Ongoing architectural decisions

### API & Data Model

- docs/api-reference.md
- docs/data-model-spec.md

### Development & Operations

- docs/technical-report.md — Comprehensive codebase navigation guide
- docs/objectives.md
- docs/marketplace-readiness-checklist.md
- docs/development/phase3-agent-integration-guide.md
- docs/development/phase3-mcp-tool-reference.md
- docs/development/phase4-local-user-testing.md

### Extraction Pipeline

- **docs/EXTRACTION_PIPELINE_QUICKSTART.md** ⭐ START HERE for extraction pipeline
- docs/EXTRACTION_PIPELINE_API_REFERENCE.md
- docs/EXTRACTION_PIPELINE_ARCHITECTURE.md
- docs/EXTRACTION_PIPELINE_DEPLOYMENT.md

### Quality & Implementation

- docs/SDK_WRAPPER_IMPLEMENTATION_COMPLETE.md — Type safety implementation status
- docs/code-quality.md

## Contributing

1. Read docs/development/CONTRIBUTING.md.
2. Make focused changes and include tests.
3. Run quality gates before opening a PR.
4. Update docs when behavior or architecture changes.

## License

License details will be published when project licensing is finalized.
