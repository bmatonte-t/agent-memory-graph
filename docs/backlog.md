# Backlog

## Current State (as of 2026-06-30)

Agent Memory Graph is **production-ready** on the `develop` branch. The core graph store, MindMap pipeline, ABAC authorization, audit logging, and extraction pipeline are implemented and tested. The Terraform module provisions all required GCP resources, and the GitLab CI pipeline covers dev→intg→prod promotion with a human approval gate on prod.

The project has not yet been deployed to a real GCP project — the infrastructure is fully specified but requires LATAM-owned GCP project IDs to run.

### What works

- **Graph storage**: `MemoryNode` and `MemoryEdge` tables with `TenantId` isolation, immutable `AUDIT_EVENTS`, and `ENGRAM_EVIDENCE` for fact grounding. All 9 migrations applied cleanly.
- **MindMap pipeline**: all four stages (Mine, Aggregate, Serialize, Synthesize) with per-stage latency tracing.
- **MCP tools**: all four tools (`MEMORY_SEARCH`, `MEMORY_ADD_FACT`, `MEMORY_LOG_TRACE`, `MEMORY_RECALL_CONTEXT`) implemented and returning stable response envelopes.
- **ABAC authorization**: deny-by-default, `AuthorizationScope` per request, dual audit logging (GRANTED/DENIED).
- **Cognitive weighting**: `LogOddsWeight` on nodes and edges, temporal decay, action-count scaling, weight pruning at configurable threshold.
- **Document extraction**: PDF and PPTX extraction, fuzzy deduplication with confidence tiers (high/medium/low).
- **BigQuery ingestion**: POLE+ entity classification, schema analysis, batch write to Spanner.
- **Terraform module**: Cloud Run, Spanner, IAM, Secret Manager, Artifact Registry, Monitoring — all workspace-aware (dev/intg/prod).
- **GitLab CI**: Docker build+push, tfvars generation from CI variables, workspace-aware apply, advana workflow on intg, human approval gate on prod.

### Known limitations

- **No REST endpoint for BigQuery ingestion**: the ingestion orchestrator must be invoked programmatically or as a Cloud Run job. A `POST /internal/ingest/bigquery` endpoint is planned (see below).
- **No Cloud Scheduler configuration in Terraform**: decay-weights and prune-weights jobs are not yet wired to a Cloud Scheduler job resource. Must be configured manually or via the YAML guide.
- **No `.terraform.lock.hcl` committed**: the lock file should be committed for reproducible Terraform runs. Blocked until a first `terraform init` is run against real GCP project IDs.
- **Single-tenant only**: the `single_company` config enforces one tenant per deployment. Multi-tenant support (multiple `TenantId` values under one Spanner instance) is architecturally possible but not yet wired.
- **No MCP server manifest**: the service does not expose a standard MCP server discovery endpoint (e.g., `GET /.well-known/mcp`). MCP clients must be configured manually with the service URL.
- **`MEMORY_SEARCH` uses synchronous LLM calls**: the Synthesize stage calls an LLM synchronously. Under high concurrency, this becomes a bottleneck. Async batching is planned.

---

## Open Work Items

### Deployment

- [ ] **First real deployment** — set GCP project IDs in GitLab CI variables, run the pipeline against real projects, commit `.terraform.lock.hcl`.
- [ ] **Cloud Scheduler Terraform resource** — add `google_cloud_scheduler_job` resources to `monitoring.tf` (or a new `scheduler.tf`) for daily decay-weights and weekly prune-weights.
- [ ] **MCP server discovery endpoint** — add `GET /.well-known/mcp` returning the tool manifest so MCP clients can auto-configure.

### API surface

- [ ] **BigQuery ingestion REST endpoint** — `POST /internal/ingest/bigquery` that accepts `{project_id, dataset_id, table_id, tenant_id}` and runs the ingestion orchestrator asynchronously. Needed for Cloud Scheduler integration.
- [ ] **Pagination on `MEMORY_RECALL_CONTEXT`** — the current `window_size` parameter is a simple limit. Add cursor-based pagination for sessions with thousands of turns.
- [ ] **Batch `MEMORY_ADD_FACT`** — accept an array of facts in a single request to reduce round-trips for bulk ingestion.
- [ ] **Graph export endpoint** — `GET /api/v1/graph/export` that returns the full tenant graph as JSON-LD or RDF/Turtle. Useful for backups and debugging.

### Observability

- [ ] **Per-stage Cloud Trace spans** — the MindMap pipeline emits latency breakdowns in the response but does not yet create Cloud Trace child spans per stage. Add OpenTelemetry instrumentation to Mine, Aggregate, Serialize, and Synthesize.
- [ ] **Alert policy for Spanner latency** — `spanner.googleapis.com/api/request_latencies` > 200 ms p99 is not yet monitored. Add to `monitoring.tf`.
- [ ] **Structured log schema** — standardize JSON log fields (`trace_id`, `tenant_id`, `tool_name`, `latency_ms`, `error_code`) across all endpoints for consistent Cloud Logging queries.

### Security

- [ ] **Workload Identity Federation for CI** — replace the `GOOGLE_CREDENTIALS` JSON key with WIF so the CI pipeline authenticates via OIDC token. Eliminates the need to rotate a long-lived SA key.
- [ ] **VPC connector** — Cloud Run currently egresses to the public internet to reach Spanner. Add a VPC connector and use private service access so traffic stays on Google's internal network.
- [ ] **Audit log retention policy** — `AUDIT_EVENTS` rows are never deleted by design, but a retention policy (e.g., 7 years) should be documented and enforced via a Spanner TTL column or periodic export to BigQuery.

### Developer experience

- [ ] **Local dev setup with emulator** — Cloud Spanner emulator support so developers can run the full stack locally without a real GCP project. `SPANNER_EMULATOR_HOST` env var support exists in the Spanner client; needs a `docker-compose.yml` and a `dev` config.
- [ ] **End-to-end integration test suite** — tests that spin up the FastAPI app against a real (or emulated) Spanner instance and exercise the full MCP tool round-trip.
- [ ] **`terraform.tfvars.example` with real region options** — document that `us-east1` is the default but LATAM also operates in `southamerica-east1`. Add notes on Spanner regional vs. multi-region configs.

### LATAM-specific

- [ ] **Adoption playbook** — a step-by-step checklist for onboarding a new LATAM team, including how to request the GCP project triad, who to contact for the Terraform state bucket, and how to register in the Cosmos service catalog.
- [ ] **Service catalog registration** — register `agent-memory-graph` in Cosmos Backstage with owner, tech stack, endpoints, and SLO targets.
- [ ] **SLO definitions** — define and document availability (99.5% uptime), latency (p95 < 2000 ms for `MEMORY_SEARCH`), and error rate (< 1% 5xx) targets. Wire to Cloud Monitoring SLO resources in Terraform.

---

## Design Decisions on Hold

These are questions the team has not yet resolved. They block certain work items above.

| Question | Impact |
|---|---|
| Should each team get its own Spanner instance or share one with namespace isolation? | Affects adoption model, cost, and multi-tenant wiring |
| Should the Synthesize stage use a fixed model (e.g., Claude Haiku 4.5) or pass through to the caller's model preference? | Affects cost, latency, and the request/response contract |
| Should `AUDIT_EVENTS` ever be exported to BigQuery for compliance reporting? | Affects the retention policy and audit tooling |
| Should `weight_pruning_threshold` be configurable per tenant or global? | Affects the governance config surface area |
