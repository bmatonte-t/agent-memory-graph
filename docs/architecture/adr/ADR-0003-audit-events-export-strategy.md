# ADR-0003: AUDIT_EVENTS Export Strategy

- Status: Accepted
- Date: 2026-07-01
- Owners: AMG core engineering

## Context

EPIC-05 requires a clear strategy for compliance/analytics export of
`AUDIT_EVENTS` without impacting online transaction workload.

## Decision

Adopt a **log-centric export strategy**:

1. `AUDIT_EVENTS` remains source-of-truth in Spanner for operational integrity.
2. Compliance and analytics exports use Cloud Logging sink path as canonical
   export channel.
3. Downstream consumers (BigQuery, SIEM, governance marts) subscribe from
   exported logs, not from ad-hoc direct OLTP queries.

## Consequences

- Clear separation between OLTP and analytical workloads.
- Better scalability for compliance reporting.
- Requires platform-managed export pipelines and retention governance.

## Implementation references

- `docs/architecture.md`
- `docs/deployment.md`
- `infrastructure/terraform/monitoring.tf`
