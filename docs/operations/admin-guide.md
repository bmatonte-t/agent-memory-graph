# Admin Guide

This guide covers tenant administration, retention controls, and cost management.

## Tenant Administration

Multi-tenant isolation is enforced with `tenant_id` on all memory operations.

Administrator responsibilities:

- provision tenant identifiers through the calling platform or upstream control plane
- ensure tenant-aware requests are used on all API and MCP entrypoints
- review audit records for cross-tenant access attempts
- enforce least-privilege IAM between tenants and environments

## Retention and Data Lifecycle

Data is split into three memory tiers:

- `CONTEXT`: short-lived conversational state
- `SEMANTIC`: durable reusable facts with cognitive weight
- `AUDIT`: immutable execution and reasoning evidence

Recommended policy baseline:

- context retention: shortest viable period for product needs
- semantic retention: business-driven, with review for stale facts
- audit retention: longest retention, aligned to compliance and incident-response requirements

Audit events are append-only and must never be updated or deleted through the application path.

## Cost Controls

Primary cost drivers:

- Spanner storage and query throughput
- Vertex extraction / synthesis calls
- Cloud Run request volume and concurrency
- observability export volume (logs, traces, metrics)

Control levers:

1. Keep `max_hops`, `max_paths`, and evidence-node limits bounded.
2. Use insufficiency fallback instead of expanding retrieval breadth aggressively.
3. Disable Vertex-backed stages in environments where deterministic adapters are sufficient.
4. Set Cloud Logging and Cloud Trace only where needed for the environment.
5. Review tenants with unusual graph growth or token consumption.

## Audit and Compliance Administration

Administrators should periodically verify:

- audit events exist for MCP tool calls and external integrations
- tenant scoping is present in API, MCP, and graph access paths
- alert policies for latency and tool errors are active
- backup and restore procedures are current

## Configuration Review Checklist

1. Validate environment-specific config files.
2. Confirm service account permissions are least-privilege.
3. Confirm dashboard and alerts target the correct project.
4. Confirm migration set matches deployed schema version.
