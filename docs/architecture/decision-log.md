# Decision Log

Use this file to track debated decisions before formal ADRs.

## Template

- Decision:
- Date:
- Context:
- Options Considered:
- Chosen Direction:
- Rationale:
- Risks:
- Revisit Trigger:
- Objective Impact:
  - Determinism and grounding:
  - Auditability and compliance:
  - Cost and latency:
  - Marketplace readiness:

## Open

- Memory unit granularity: fact, episode, concept node, or mixed model?
- Retrieval strategy: deterministic traversal first, semantic first, or adaptive?
- Prioritization policy: recency, utility, uncertainty, or blended score?
- Initial launch packaging: single-tenant first or tenant-aware from day one?
- Marketplace offer model: direct listing, private offer support, or both?

## Decisions

- Decision: Enforce deny-by-default ABAC at the MCP boundary and MemoryAPI boundary with auditable allow/deny events.
- Date: 2026-06-22
- Context: Phase 0 now includes real authorization enforcement, not just contract placeholders. The system needs deterministic boundary checks that prevent unauthorized reads, writes, and trace logging while keeping the decision visible for support and compliance.
- Options Considered:
  - Tenant-only access with no resource scoping.
  - MCP-only authorization checks with MemoryAPI trusting callers.
  - Deny-by-default checks at both MCP dispatch and MemoryAPI operations, with audit events for each decision.
- Chosen Direction: Deny by default at both layers, require an explicit authorization scope for protected actions, and record allow/deny decisions without recursive policy evaluation.
- Rationale: Dual enforcement reduces bypass risk, keeps the policy model explicit, and preserves a clean audit trail for enterprise review.
- Risks: Scope evaluation can become too strict if resource predicates are underspecified; tests must keep the public contract aligned with the policy model.
- Revisit Trigger: Re-open if the request contract needs richer hierarchy-based policy evaluation or if a future customer requirement needs row-level or relationship-path exceptions.
- Objective Impact:
  - Determinism and grounding: stronger boundary behavior and fewer hidden access paths.
  - Auditability and compliance: every allow/deny decision is visible and traceable.
  - Cost and latency: small overhead from policy checks and audit writes.
  - Marketplace readiness: improves trust and enterprise adoption posture.

## Active ADRs

- ADR-0001 (proposed): [Phase-One Architecture Direction](adr/ADR-0001-phase-one-architecture.md)

## Readiness Gate

- Marketplace readiness checklist: [docs/marketplace-readiness-checklist.md](../marketplace-readiness-checklist.md)
