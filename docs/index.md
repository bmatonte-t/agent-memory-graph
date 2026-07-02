# Agent Memory Graph

Agent Memory Graph (AMG) is an enterprise-grade persistent memory layer for AI agents. It gives agents access to a shared, organization-wide knowledge graph that survives across sessions, prevents hallucination by grounding every response in verifiable evidence, and provides immutable audit trails for compliance.

## What it does

- **Eliminates hallucination** — responses are generated only from facts retrieved from the graph; unsupported claims are rejected with an evidence-insufficiency signal
- **Preserves context across sessions** — agents pick up where they left off without receiving prior conversation history in the prompt
- **Coordinates agents** — all agents in the organization share the same graph, enabling multi-agent workflows without a shared message bus
- **Reads your data** — ingests from documents (PDF, PPTX) and BigQuery tables; deduplicates entities with fuzzy matching
- **Provides compliance** — every access, authorization decision, and reasoning step is written to an immutable audit log

## Documentation

| Section | Contents |
| --- | --- |
| [Concepts](concepts/tripartite-memory.md) | Tripartite memory model, MindMap pipeline, cognitive weighting |
| [Architecture](architecture.md) | System components, data flows, tech stack |
| [User Guide — MCP Tools](user-guide/mcp-tools.md) | The six MCP tools and discovery contract with request/response examples |
| [User Guide — REST API](user-guide/api-reference.md) | Every HTTP endpoint with examples |
| [User Guide — Extraction Pipeline](user-guide/extraction-pipeline.md) | Document and BigQuery ingestion |
| [Deployment](deployment.md) | LATAM adoption model, project-by-project rollout, manual steps |
| [Infrastructure](infrastructure.md) | Terraform resources, CI/CD pipeline, GCP configuration |
| [Testing Governance](testing-governance.md) | Canonical test policy, gates, admission and retirement rules |
| [Testing Health Dashboard](testing-health-dashboard.md) | Unified governance metrics and review cadence |
| [EPIC-06 Incident Protocol](epic-06-slo-incident-protocol.md) | SLO-driven incident response, severity, and postmortem standards |
| [EPIC-07 Adoption Playbook](epic-07-adoption-playbook.md) | Step-by-step onboarding model for new LATAM teams |
| [EPIC-07 Onboarding Checklist](epic-07-onboarding-checklist.md) | Prerequisites by role: platform, security, data owner, AMG core |
| [EPIC-07 Support Model](epic-07-support-model.md) | Internal SLA, escalation levels, and operational channels |
| [EPIC-07 Pilot Report](epic-07-pilot-onboarding-report.md) | Local pilot evidence, lessons learned, and external blockers |
| [Backlog](backlog.md) | Active pending work and decisions on hold |
| [ADRs](architecture/adr/README.md) | Accepted architecture decisions and rationale |

## Latest delivery status

- API surface closed for the current cycle, including batch fact ingestion and JSON-LD graph export.
- Observability closed for the current cycle, including per-stage tracing and structured logging schema.
- Security closed for the current cycle, including WIF-ready CI flow, VPC connector wiring, and audit retention controls.
- Developer experience closed for the current cycle, including emulator compose flow and E2E MCP round-trip test path.

## Quick orientation

The product exposes two surfaces:

1. **MCP discovery + tools** (`GET /.well-known/mcp`, `POST /api/v1/mcp/invoke`) — the primary interface for AI agents. Agents can discover and call six tools: `MEMORY_SEARCH`, `MEMORY_ADD_FACT`, `MEMORY_ADD_FACT_BATCH`, `MEMORY_LOG_TRACE`, `MEMORY_RECALL_CONTEXT`, `MEMORY_END_SESSION`.
2. **REST API** — management and orchestration endpoints used by orchestrators and internal maintenance jobs.

Underneath both surfaces, the same graph database (Cloud Spanner) and the same four-stage MindMap pipeline power all responses.

## Technology

| Component | Technology |
| --- | --- |
| Runtime | Python 3.14, FastAPI |
| Database | Cloud Spanner (with property graph / GQL) |
| Compute | Cloud Run gen2 (2 vCPU / 4 Gi) |
| Secrets | Secret Manager |
| Observability | Cloud Logging, Cloud Trace, Cloud Monitoring |
| Package manager | uv |
| Infrastructure | Terraform (workspace-per-environment) |
| CI/CD | GitLab CI (Cosmos shared templates) |
