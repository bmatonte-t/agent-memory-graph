# Marketplace Readiness Checklist

Purpose: provide a practical pass/fail gate before listing the product on Google Cloud Marketplace.

Scope: phase-one release of the Cognitive Agent Memory Graph.

## 1) Product Positioning

- [ ] Clear one-sentence value proposition is documented.
- [ ] Target buyer profile is explicit (platform, data, or security team).
- [ ] Primary use cases and non-goals are documented and consistent.
- [ ] Competitive differentiation is documented (deterministic grounding, auditability, GCP-native scale).

Evidence:
- Product brief
- README and architecture brief alignment

## 2) Deterministic Trust Model

- [ ] Mine -> Aggregate -> Serialize -> Synthesize is implemented or fully specified.
- [ ] Responses are grounded in serialized graph evidence.
- [ ] Missing evidence returns explicit insufficiency (no guessing).
- [ ] Traceability links answer outputs to evidence paths.

Evidence:
- API behavior examples
- Test cases for insufficiency and grounded responses

## 3) Memory Architecture and Data Model

- [ ] Tripartite memory boundaries are defined and enforced.
- [ ] Semantic nodes and edges include cognitive_weight and last_accessed.
- [ ] Audit memory is append-only by design and controls.
- [ ] Tenant isolation strategy is documented and testable.

Evidence:
- Data model and schema docs
- Policy and validation checks

## 4) Security and Compliance

- [x] IAM least-privilege model is documented.
- [x] Service accounts and key management approach are defined.
- [x] Data handling, retention, and deletion semantics are documented.
- [x] Audit evidence covers tool execution and external API calls.

Evidence:
- Security architecture doc: [docs/marketplace/security-architecture.md](marketplace/security-architecture.md)
- Admin and retention guidance: [docs/operations/admin-guide.md](operations/admin-guide.md)
- Audit controls and tests:
	- `migrations/005_audit_immutability_controls.sql`
	- `tests/unit/test_audit_immutability.py`
	- `tests/unit/test_security_audit.py`

## 5) Reliability and Operations

- [ ] SLOs/SLIs are defined for availability, latency, and error rate.
- [x] Observability stack is documented (logs, traces, metrics, alerts).
- [x] Runbooks exist for top operational failure modes.
- [x] Backup, restore, and disaster recovery approach is documented.

Evidence:
- Ops runbook: [docs/operations/ops-runbook.md](operations/ops-runbook.md)
- Support playbook: [docs/operations/support-playbook.md](operations/support-playbook.md)
- Disaster recovery: [docs/operations/disaster-recovery.md](operations/disaster-recovery.md)
- Monitoring artifacts:
	- `infrastructure/phase2/cloud-monitoring-dashboard.json`
	- `infrastructure/phase2/alert-policies.yaml`

## 6) Performance and Cost

- [x] p95 latency targets are defined and measured.
- [ ] Retrieval horizon strategy is documented to control token/cost growth.
- [x] Cost model is documented (Spanner, Vertex, serving).
- [x] Load test evidence exists for phase-one expected demand.

Evidence:
- Latency and load validation tests:
	- `tests/integration/test_performance.py`
	- `tests/load/test_slo_validation.py`
- Pricing and cost model: [docs/marketplace/pricing-and-editions.md](marketplace/pricing-and-editions.md)

## 7) Deployment and Lifecycle

- [x] Deployment architecture is documented for customer environments.
- [x] Versioning and upgrade path are documented.
- [x] Backward compatibility policy is defined for APIs and schemas.
- [ ] Rollback strategy is documented and tested.

Evidence:
- Deployment guide: [docs/marketplace/deployment-guide.md](marketplace/deployment-guide.md)
- Architecture baseline: [docs/architecture/architecture-brief.md](architecture/architecture-brief.md)

## 8) Buyer-Facing Materials

- [x] Installation and quickstart documentation is complete.
- [x] Admin and operator guides are complete.
- [x] Troubleshooting guide and known limitations are published.
- [x] Support model and escalation path are defined.

Evidence:
- Marketplace docs index: [docs/marketplace/index.md](marketplace/index.md)
- Quickstart: [docs/marketplace/quickstart.md](marketplace/quickstart.md)
- Admin guide: [docs/operations/admin-guide.md](operations/admin-guide.md)
- Troubleshooting: [docs/help/troubleshooting.md](help/troubleshooting.md)
- Support handbook: [docs/operations/support-playbook.md](operations/support-playbook.md)

## 9) Commercial Readiness

- [x] Packaging model is defined (editions/features).
- [x] Pricing approach is documented and reviewable.
- [ ] License/terms readiness is confirmed.
- [x] Private offer process and constraints are documented.

Evidence:
- Commercial package brief: [docs/marketplace/pricing-and-editions.md](marketplace/pricing-and-editions.md)
- Positioning brief: [docs/marketing-pitch.md](marketing-pitch.md)

## Exit Criteria (Phase 1)

Release is Marketplace-ready when:
- All critical checklist items are marked pass.
- No critical security or determinism gaps remain open.
- Required buyer-facing documents are complete and internally reviewed.

## Decision Log

Use this section to track gate reviews.

- Review Date:
- Reviewer(s):
- Result (Pass/Conditional/Fail):
- Blocking Gaps:
- Follow-up Owner and ETA:
