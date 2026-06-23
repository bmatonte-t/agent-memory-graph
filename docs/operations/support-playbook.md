# Support Playbook

This playbook defines incident handling, escalation paths, and RCA expectations.

## Severity Levels

- Sev 1: production outage, cross-tenant risk, or data integrity breach
- Sev 2: major degradation affecting key user flows or SLO breach
- Sev 3: partial degradation, recoverable operational issue, or repeated customer friction
- Sev 4: documentation gap, low-risk bug, or minor support request

## Initial Response Checklist

1. Record the incident start time.
2. Capture request IDs, tenant IDs, trace IDs, and affected sessions.
3. Check alert policies and dashboards for latency, error, and throughput anomalies.
4. Identify whether the issue is application, data, or infrastructure-scoped.
5. Decide whether rollback or traffic reduction is required.

## Escalation Paths

- Product support -> on-call engineering for Sev 2+
- On-call engineering -> security owner for tenant isolation, audit, or access-boundary issues
- On-call engineering -> platform owner for Cloud Run / Spanner / observability platform issues
- Engineering lead -> stakeholder update for Sev 1 and customer-visible Sev 2 incidents

## Evidence Collection

Collect and preserve:

- request ID
- tenant ID
- Cloud Trace span chain
- structured log lines from orchestrator, MCP, and MindMap pipeline
- relevant audit events
- deployment revision and config version

## RCA Process

Minimum RCA structure:

1. Summary
2. Impact
3. Timeline
4. Detection method
5. Root cause
6. Mitigation / rollback taken
7. Corrective actions
8. Follow-up owner and due date

## Customer Communication Guidance

- state impact clearly
- avoid speculative root-cause claims before confirmation
- provide next update time when mitigation is ongoing
- publish known limitations and workarounds when a fix is not immediate
