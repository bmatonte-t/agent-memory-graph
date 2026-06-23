# Ops Runbook

This runbook describes how to operate Agent Memory Graph in a production GCP environment.

## Deployment Topology

- API and MCP entrypoints run on Cloud Run.
- MindMap pipeline executes inside the application service and uses Vertex AI for model-backed stages when enabled.
- Persistent graph storage lives in Cloud Spanner.
- Background cognitive-weight decay is designed for Cloud Scheduler + Cloud Run job execution.
- Observability uses Cloud Trace, Cloud Logging, Cloud Monitoring dashboards, and alert policies under `infrastructure/phase2/cloud-monitoring-dashboard.json` and `infrastructure/phase2/alert-policies.yaml`.

## Routine Operations

### Startup Validation

Run these checks after deploy:

```bash
just test
just test-coverage
```

Confirm the following runtime signals:

- `/health` returns `healthy`.
- Cloud Run revision is serving 100% traffic for the intended release.
- Spanner database is reachable from the service account.
- Trace, log, and metric signals appear in the observability dashboard.

### Scaling Guidance

- Cloud Run concurrency should be tuned based on p95 MindMap latency.
- Increase min instances if cold-start jitter pushes p95 over SLO.
- Scale Spanner capacity when graph traversal latency or write contention increases.
- Keep `max_hops`, `max_paths`, and evidence-node limits conservative to bound latency and cost.

### Required Runtime Configuration

- `cloud_trace.enabled`
- `cloud_trace.project_id`
- `cloud_logging.enabled`
- `cloud_logging.project_id`
- Spanner project / instance / database identifiers
- Vertex model names when Vertex-backed stages are enabled

## Backup and Recovery Hooks

- Use Spanner-managed backups for point-in-time restore strategy.
- Keep migration files under `migrations/` as the schema source of truth.
- Restore procedures and RTO/RPO guidance are documented in [operations/disaster-recovery.md](disaster-recovery.md).

## Operator Checklists

### Before Release

1. Run `just test`.
2. Run `just test-coverage`.
3. Validate dashboard and alert configs are in sync with metric names.
4. Confirm rollback target revision exists.

### After Release

1. Validate health endpoint.
2. Confirm orchestrator, MCP, and MindMap traces appear end-to-end.
3. Confirm no spike in `mcp.tool.errors`.
4. Confirm p95 `mindmap.pipeline.execution_ms` is within target.

## Runbook Links

- Product troubleshooting: [help/troubleshooting.md](../help/troubleshooting.md)
- Tenant and cost administration: [operations/admin-guide.md](admin-guide.md)
- Incident handling and RCA: [operations/support-playbook.md](support-playbook.md)
- Disaster recovery: [operations/disaster-recovery.md](disaster-recovery.md)
