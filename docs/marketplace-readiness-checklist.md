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

- [ ] IAM least-privilege model is documented.
- [ ] Service accounts and key management approach are defined.
- [ ] Data handling, retention, and deletion semantics are documented.
- [ ] Audit evidence covers tool execution and external API calls.

Evidence:
- Security architecture doc
- Access matrix and audit samples

## 5) Reliability and Operations

- [ ] SLOs/SLIs are defined for availability, latency, and error rate.
- [ ] Observability stack is documented (logs, traces, metrics, alerts).
- [ ] Runbooks exist for top operational failure modes.
- [ ] Backup, restore, and disaster recovery approach is documented.

Evidence:
- Ops runbook
- On-call playbook

## 6) Performance and Cost

- [ ] p95 latency targets are defined and measured.
- [ ] Retrieval horizon strategy is documented to control token/cost growth.
- [ ] Cost model is documented (Spanner, Vertex, serving).
- [ ] Load test evidence exists for phase-one expected demand.

Evidence:
- Benchmark report
- Cost estimation sheet

## 7) Deployment and Lifecycle

- [ ] Deployment architecture is documented for customer environments.
- [ ] Versioning and upgrade path are documented.
- [ ] Backward compatibility policy is defined for APIs and schemas.
- [ ] Rollback strategy is documented and tested.

Evidence:
- Deployment guide
- Release policy

## 8) Buyer-Facing Materials

- [ ] Installation and quickstart documentation is complete.
- [ ] Admin and operator guides are complete.
- [ ] Troubleshooting guide and known limitations are published.
- [ ] Support model and escalation path are defined.

Evidence:
- Buyer documentation set
- Support handbook

## 9) Commercial Readiness

- [ ] Packaging model is defined (editions/features).
- [ ] Pricing approach is documented and reviewable.
- [ ] License/terms readiness is confirmed.
- [ ] Private offer process and constraints are documented.

Evidence:
- Commercial package brief
- Marketplace publishing plan

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
