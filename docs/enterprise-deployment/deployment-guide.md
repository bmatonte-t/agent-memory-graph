# Deployment Guide

## Purpose

Provide step-by-step procedures for deploying Agent Memory Graph in an enterprise customer's GCP organization.

## Deployment Architecture

For architecture context, review:

- [docs/architecture/architecture-brief.md](../architecture/architecture-brief.md)
- [docs/operations/ops-runbook.md](../operations/ops-runbook.md)

## Prerequisites

- Runtime environment with Python 3.14 support.
- Access to required cloud services for target environment.
- Configuration values prepared for tenant, observability, and persistence settings.

## Deployment Steps

1. Prepare environment configuration.
- Review `config.yaml` and `config.dev.yaml`.

2. Apply schema migrations in order.
- `migrations/001_memory_node_table.sql`
- `migrations/002_memory_edge_table.sql`
- `migrations/003_property_graph.sql`
- `migrations/004_add_tenant_id.sql`
- `migrations/005_audit_immutability_controls.sql`

3. Validate service configuration and startup.
- API entrypoint: `src/api/main.py`
- Settings models: `src/project_base/settings/models.py`

4. Run quality and smoke checks.

```bash
just check-all
uv run pytest tests/unit/test_setup.py -q
```

5. Validate observability deployment artifacts.
- `infrastructure/phase2/cloud-monitoring-dashboard.json`
- `infrastructure/phase2/alert-policies.yaml`

## Upgrade Policy

- Follow semantic versioning for release tags.
- Apply backward-compatible schema changes by additive migration when possible.
- Run contract tests before and after upgrade.

## Backward Compatibility Policy

- Preserve API envelope structure for existing clients.
- Avoid breaking model fields without deprecation notice.
- Document schema-affecting changes in release notes.

## Rollback Strategy

1. Stop rollout when health regressions exceed SLO thresholds.
2. Revert service version to last known-good release.
3. Restore data-path behavior using validated migration rollback approach where applicable.
4. Re-run smoke checks and critical path tests.

## Post-Deployment Validation

- Health endpoint and core API routes respond successfully.
- Error responses remain sanitized.
- Audit writes remain append-only.
- Monitoring and alerts are active.
