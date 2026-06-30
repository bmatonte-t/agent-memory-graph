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
|---|---|
| [Concepts](concepts/tripartite-memory.md) | Tripartite memory model, MindMap pipeline, cognitive weighting |
| [Architecture](architecture.md) | System components, data flows, tech stack |
| [User Guide — MCP Tools](user-guide/mcp-tools.md) | The four MCP tools with request/response examples |
| [User Guide — REST API](user-guide/api-reference.md) | Every HTTP endpoint with examples |
| [User Guide — Extraction Pipeline](user-guide/extraction-pipeline.md) | Document and BigQuery ingestion |
| [Deployment](deployment.md) | LATAM adoption model, project-by-project rollout, manual steps |
| [Infrastructure](infrastructure.md) | Terraform resources, CI/CD pipeline, GCP configuration |
| [Backlog](backlog.md) | Current state, open work, known limitations |

## Quick orientation

The product exposes two surfaces:

1. **MCP tools** (`POST /api/v1/mcp/invoke`) — the primary interface for AI agents. Agents call one of four tools: `MEMORY_SEARCH`, `MEMORY_ADD_FACT`, `MEMORY_LOG_TRACE`, `MEMORY_RECALL_CONTEXT`.
2. **REST API** — management and orchestration endpoints used by orchestrators and internal maintenance jobs.

Underneath both surfaces, the same graph database (Cloud Spanner) and the same four-stage MindMap pipeline power all responses.

## Technology

| Component | Technology |
|---|---|
| Runtime | Python 3.14, FastAPI |
| Database | Cloud Spanner (with property graph / GQL) |
| Compute | Cloud Run gen2 (2 vCPU / 4 Gi) |
| Secrets | Secret Manager |
| Observability | Cloud Logging, Cloud Trace, Cloud Monitoring |
| Package manager | uv |
| Infrastructure | Terraform (workspace-per-environment) |
| CI/CD | GitLab CI (Cosmos shared templates) |
