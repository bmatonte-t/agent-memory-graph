# Security Architecture

## Purpose

This document summarizes the security controls and trust boundaries for Agent Memory Graph enterprise deployments.

## Security Objectives

- Protect tenant isolation across all memory operations.
- Prevent unauthorized mutation of immutable audit records.
- Reduce leakage of internal implementation details in client responses.
- Preserve deterministic, auditable response generation.

## Control Domains

### Identity and Access

- Service-to-service access is intended to use least-privilege service accounts.
- Memory operations are tenant-scoped at API, service, and persistence layers.
- Cross-tenant access attempts are rejected by validation and query scoping.

### Data Protection and Handling

- Tripartite memory model separates Context, Semantic, and Audit tiers.
- Audit events are append-only with mutation safeguards.
- Request validation and error handling avoid exposing stack traces and internal paths.

### Auditability and Traceability

- Tool execution and orchestration traces are recorded as audit events.
- MindMap execution records include evidence linkage metadata.
- Observability signals (logs, traces, metrics) provide investigation context.

### Resilience and Operational Security

- Alert policies and dashboards support early detection of reliability or safety regressions.
- Operations and support runbooks define response procedures.
- Disaster recovery guidance defines restoration and continuity expectations.

## Key Implementation Evidence

- Tenant and audit hardening:
  - `migrations/004_add_tenant_id.sql`
  - `migrations/005_audit_immutability_controls.sql`
  - `src/memory/api.py`
  - `src/db/spanner_client.py`
- Validation and security boundaries:
  - `src/security/validators.py`
  - `src/api/main.py`
- Observability and monitoring:
  - `src/observability/`
  - `infrastructure/phase2/alert-policies.yaml`
  - `infrastructure/phase2/cloud-monitoring-dashboard.json`
- Security-oriented tests:
  - `tests/unit/test_security_audit.py`
  - `tests/unit/test_injection_security.py`
  - `tests/unit/test_audit_immutability.py`
  - `tests/unit/test_observability_safety.py`

## Threat Scenarios and Current Mitigations

1. Cross-tenant data access attempts.
- Mitigation: tenant_id validation and tenant-scoped queries.

2. Unauthorized audit tampering.
- Mitigation: audit immutability controls in persistence and service layers.

3. Information disclosure through validation errors.
- Mitigation: sanitized validation responses and observability safety tests.

4. Ungrounded or unverifiable responses.
- Mitigation: MindMap deterministic pipeline and explicit insufficient-evidence behavior.

## Compliance Readiness Notes

The current implementation provides baseline controls aligned with common enterprise expectations for:

- isolation,
- auditability,
- deterministic behavior,
- and operational traceability.

Formal legal/compliance attestations (for example, contractual CCPA/GDPR commitments) should be completed as part of commercial/legal review before listing submission.
