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

Agent Memory Graph is deployed as an **isolated single-organization service**, one deployment per team within a GCP organization:

- **Project-per-team isolation** — Each adopting team gets its own triad of GCP projects (dev/intg/prod) with a dedicated Cloud Run service, Spanner instance, and Artifact Registry
- **No shared infrastructure** — No shared Spanner instances, no shared IAM, no cross-project data access
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

- Deny-by-default with `AuthorizationScope` per request
- Dual audit logging (GRANTED/DENIED decisions)
- Suitable for organizations with centralized policy management

**External Delegation** (enterprise):

- Delegates authorization decisions to your policy service (e.g., Entitlements Platform, Okta, Auth0)
- Your service receives `POST /authorize` with agent context and responds with allow/deny
- Enables sync between your identity infrastructure and agent permissions

## API Surface

Core memory and orchestration endpoints:

| Endpoint | Description |
| --- | --- |
| `GET /health` | Health check and readiness probe |
| `POST /api/v1/mindmap/execute` | Execute MindMap reasoning pipeline (Mine → Aggregate → Serialize → Synthesize) |
| `POST /api/v1/mcp/invoke` | Invoke MCP tools: `MEMORY_SEARCH`, `MEMORY_ADD_FACT`, `MEMORY_ADD_FACT_BATCH`, `MEMORY_LOG_TRACE`, `MEMORY_RECALL_CONTEXT` |
| `POST /api/v1/agent/respond` | Orchestrate agent responses across single/supervisor/gemini modes |
| `GET /api/v1/graph/export` | Export tenant-scoped graph snapshot in JSON-LD |

Internal maintenance endpoints:

| Endpoint | Description |
| --- | --- |
| `POST /internal/decay-weights` | Apply temporal cognitive weight decay (scheduled or manual) |
| `POST /internal/prune-weights` | Prune low-confidence evidence below configurable threshold |

## Technology Stack

| Component | Technology |
| --- | --- |
| Runtime | Python 3.14, FastAPI, uvicorn |
| Database | Google Cloud Spanner (property graph with GQL) |
| AI Engine | Gemini Enterprise Agent Platform (Gemini 1.5 Flash for extraction, Gemini 1.5 Pro for synthesis) |
| Compute | Cloud Run gen2 (2 vCPU / 4 Gi) |
| Observability | Cloud Logging, Cloud Trace, Cloud Monitoring |
| Infrastructure | Terraform (workspace-per-environment: dev/intg/prod) |
| Package Manager | uv |
| Task Runner | just |
| CI/CD | GitHub Actions (code quality) + GitLab CI (deployment) |

## Quickstart

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- [just](https://github.com/casey/just)

### Install Dependencies

```bash
uv sync --all-groups
```

Optional pre-commit hook setup:

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

### Run with Spanner Emulator

```bash
source scripts/start-emulator.sh
uv run uvicorn src.api.main:app --reload
```

Alternative Docker Compose workflow:

```bash
just emulator-up
uv run uvicorn src.api.main:app --reload
```

Use emulator-focused settings file:

```bash
export AGENT_MEMORY_GRAPH_CONFIG_FILE=config.emulator.yaml
```

Run emulator round-trip integration suite:

```bash
just test-e2e-emulator
```

## Developer Commands

```bash
just --list          # Show all available commands

# Quality checks
just lint            # Run ruff linter
just check-types     # basedpyright strict mode
just check-format    # Check formatting without changes
just test            # Run all tests
just test-coverage   # Run tests with coverage report
just docstring-coverage  # Check docstring coverage
just check-all       # Run ALL quality gates (lint + types + format + tests + docstrings)

# Fix/format
just format          # Auto-format code
just lint-fix        # Auto-fix lint issues

# Documentation
just serve-docs      # Local MkDocs with live reload
just build-docs      # Build static documentation site
just docs-publish-site  # Publish to documentation.tryolabs.com

# Deployment
just phase3-render-cloudrun <project_id>   # Render Cloud Run manifest
just phase3-build-image <project_id>       # Build container with Cloud Build
just phase3-deploy-cloudrun <project_id>   # Deploy to Cloud Run

# Emulator DX
just emulator-up       # Start local Spanner emulator container
just emulator-down     # Stop local emulator container
just test-e2e-emulator # Run MCP end-to-end round-trip suite for emulator runtime
```

## API Additions

- `POST /internal/ingest/bigquery`: asynchronous BigQuery ingestion job trigger.
- `GET /api/v1/graph/export`: tenant-scoped JSON-LD graph snapshot export.
- MCP tool `memory_add_fact_batch`: bulk semantic ingestion with per-item partial-failure reporting.

Observability hardening additions:

- Structured logging schema fields on API and MCP paths: `trace_id`, `tenant_id`, `tool_name`, `latency_ms`, `error_code`.
- Cloud Trace stage spans: `mindmap.stage.mine`, `mindmap.stage.aggregate`, `mindmap.stage.serialize`, `mindmap.stage.synthesize`.

## Testing and Quality

| Metric | Status |
| --- | --- |
| Tests | 889 collected (886 passing, 3 skipped) in latest local full gate |
| Type Safety | basedpyright strict mode — 0 errors, 0 warnings |
| Linting | ruff — 100% compliant |
| Formatting | ruff format — 100% compliant |
| Docstring Coverage | 93.9% (Excellent) |

Test categories:

- **Unit tests** (`tests/unit/`) — Core memory, MindMap pipeline, MCP tools, governance, cognitive weighting, pipelines
- **Integration tests** (`tests/integration/`) — Cross-tenant isolation, ABAC enforcement, agent concurrency, audit trails, evidence synthesis
- **Chaos tests** (`tests/chaos/`) — Resilience under failure conditions
- **Load tests** (`tests/load/`) — SLO validation, comparative weighting, emulator workloads

Pre-PR gate (runs all checks):

```bash
just check-all
```

Testing governance operations:

```bash
just test-governance-audit
just test-governance-enforce
just test-gate-pr-functional
just test-gate-full-functional
just test-gate-non-functional
just test-health-dashboard
```

## Project Structure

```text
src/
├── api/              # FastAPI application and route handlers
├── agent/            # Agent orchestrator and Vertex AI adapter
├── client/           # HTTP client with retry and rate limiting
├── db/               # Spanner client and database access
├── deployment/       # Cloud Run configuration helpers
├── integrations/     # Typed SDK wrappers (BigQuery, Scheduler, Spanner)
├── mcp/              # MCP tool service (5 tools)
├── memory/           # Core memory: MindMap pipeline, cognitive weighting, retrieval, evidence
├── models/           # Pydantic schemas for all API contracts
├── observability/    # Structured logging, metrics, distributed tracing
├── pipelines/        # Data ingestion pipelines
│   ├── api/              # Extraction REST API endpoints
│   ├── bigquery_ingestion/   # BigQuery → Spanner graph ingestion (POLE+ classification)
│   ├── document_ingestion/   # PDF/PPTX text and entity extraction
│   ├── entity_linking/       # Fuzzy deduplication with confidence tiers
│   └── services/             # Pipeline orchestration
├── project_base/     # Settings, logging configuration
└── security/         # Governance, ABAC, tenant context, validators

tests/
├── unit/             # 25+ test modules covering all src/ modules
│   ├── deployment/       # Cloud Run config tests
│   └── pipelines/        # Pipeline-specific tests (8 modules)
├── integration/      # 23 integration test modules
├── chaos/            # Resilience tests
└── load/             # Performance and SLO tests

infrastructure/
├── terraform/        # Full Terraform module (Cloud Run, Spanner, IAM, Secrets, Monitoring, Registry)
├── docker/           # Container configuration
├── documentation/    # MkDocs documentation server
├── phase2/           # Phase 2 infrastructure artifacts
└── phase3/           # Cloud Run service manifests

migrations/           # 9 Spanner DDL migrations (nodes, edges, property graph, audit, evidence)
docs/                 # MkDocs documentation source
scripts/              # Utility scripts (deploy, metrics, rendering)
```

## Infrastructure

All infrastructure is provisioned by a Terraform module at `infrastructure/terraform/`:

| Resource | Description |
| --- | --- |
| Cloud Run service | 2 vCPU / 4 Gi, min 1 instance |
| Spanner instance | 100 PU (dev/intg), 200 PU (prod) |
| Spanner database | 9 migrations auto-applied |
| Artifact Registry | Docker repository for container images |
| Service Accounts | Product SA + Spanner SA with least-privilege IAM |
| Secret Manager | Spanner credentials + app config |
| Cloud Monitoring | Alert policies for error rate and p99 latency |

Terraform is workspace-aware (`dev`, `intg`, `prod`) and state is stored in GCS.

## CI/CD

### GitHub Actions

- **Code Quality** (`code-quality.yaml`) — Runs on every push: lint, format, types, tests, docstring coverage
- **PR Style** (`check-pr-style.yaml`) — Validates PR titles and labels
- **Documentation** (`build-and-publish-documentation.yaml`) — Builds and publishes MkDocs site
- **Code Complexity** (`code-complexity-metrics.yaml`) — Tracks complexity metrics
- **Pre-commit Autoupdate** (`pre-commit-autoupdate.yaml`) — Keeps hooks current

### GitLab CI (Deployment)

- Docker build and push to Artifact Registry
- Terraform plan/apply with workspace-aware environments
- Human approval gate on production deployments

## Database Schema

9 migrations in `migrations/`:

1. `MemoryNode` table with cognitive weight and temporal metadata
2. `MemoryEdge` table with relationship types and weights
3. Property graph definition (GQL-queryable)
4. Tenant isolation (`TenantId` column)
5. Audit immutability controls (cannot UPDATE/DELETE audit events)
6. Session action count for weighting
7. Property graph session action count integration
8. `ENGRAM_EVIDENCE` table for fact grounding
9. Confidence metadata on evidence records

## Documentation

Full documentation is served via MkDocs:

```bash
just serve-docs  # http://localhost:8000
```

### Documentation Structure

| Section | Contents |
| --- | --- |
| [Concepts](docs/concepts/tripartite-memory.md) | Tripartite memory model, MindMap pipeline, cognitive weighting |
| [Architecture](docs/architecture.md) | System components, data flows, tech stack |
| [User Guide — MCP Tools](docs/user-guide/mcp-tools.md) | The four MCP tools with request/response examples |
| [User Guide — REST API](docs/user-guide/api-reference.md) | Every HTTP endpoint with examples |
| [User Guide — Extraction Pipeline](docs/user-guide/extraction-pipeline.md) | Document and BigQuery ingestion |
| [Deployment](docs/deployment.md) | Adoption model, project-by-project rollout, onboarding steps |
| [Infrastructure](docs/infrastructure.md) | Terraform resources, CI/CD pipeline, GCP configuration |
| [Testing Governance](docs/testing-governance.md) | Canonical policy, test admission and retirement rules |
| [Testing Health Dashboard](docs/testing-health-dashboard.md) | Governance metrics and cadence |
| [Backlog](docs/backlog.md) | Active pending work and design decisions on hold |

## Project Status

**Production-Ready** — awaiting first real GCP deployment.

- ✅ **Phase 1**: Core memory architecture (Context, Semantic, Audit tiers)
- ✅ **Phase 2**: MindMap retrieval and grounding pipeline
- ✅ **Phase 3**: MCP tooling and agent orchestration
- ✅ **Phase 4**: Security hardening (ABAC, org-wide isolation, audit trails)
- ✅ **Phase 4C**: Observability and compliance baseline (Cloud Logging, Cloud Trace, Monitoring alerts)
- ✅ **Phase 4D**: Type Safety Infrastructure (Protocol-based SDK wrappers, 0 type errors)
- ✅ **Phase 5**: Enterprise governance adapters (internal ABAC + external delegation)
- ✅ **Extraction Pipeline**: Document (PDF/PPTX) and BigQuery ingestion with entity deduplication
- 🔄 **Current**: First deployment to LATAM GCP projects

## Contributing

1. Read [CONTRIBUTING.md](CONTRIBUTING.md).
2. Make focused changes and include tests.
3. Run `just check-all` before opening a PR.
4. Update docs when behavior or architecture changes.

## License

License details will be published when project licensing is finalized.
