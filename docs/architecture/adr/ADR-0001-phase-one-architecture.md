# ADR-0001: Phase-One Architecture Direction

- Status: Proposed
- Date: 2026-06-16
- Decision Owners: Architecture Working Group

## Context

The project needs a phase-one architecture that maximizes:
- deterministic grounding and auditability
- GCP-native operational simplicity
- enterprise trust and supportability
- speed to a marketable Google Cloud Marketplace release

Three options were evaluated in [docs/architecture/options.md](../options.md):
- Option A: Graph-first Memory Core
- Option B: Hybrid Graph + Vector Sidecar
- Option C: Event-sourced Cognitive Pipeline

## Decision

Adopt **Option A (Graph-first Memory Core)** for phase one.

Core constraints:
- Enforce Mine -> Aggregate -> Serialize -> Synthesize flow.
- Use tripartite memory boundaries (Context, Semantic, Audit).
- Treat Audit memory as append-only.
- Require explicit insufficiency when graph evidence is missing.

## Rationale

Option A best fits phase-one objectives because it:
- provides strong deterministic behavior with fewer moving parts
- reduces reliability risk versus dual-store synchronization
- accelerates path to enterprise-ready operations on GCP
- strengthens buyer confidence with a simpler, auditable architecture

## Consequences

Positive:
- clearer architecture narrative for buyers and security reviewers
- lower operational complexity for initial release
- easier observability and support model

Trade-offs:
- semantic-heavy retrieval flexibility may be lower than hybrid approaches
- schema discipline is required as cognition models evolve

## Rejected Alternatives

### Option B (Hybrid Graph + Vector Sidecar)

Rejected for phase one due to:
- dual-write and consistency risk
- higher operational and support complexity

May be revisited if retrieval quality requirements exceed graph-first limits.

### Option C (Event-sourced Cognitive Pipeline)

Rejected for phase one due to:
- longer implementation runway
- eventual consistency complexity for derived views

May be revisited for stricter replay/compliance requirements in later phases.

## Objective Impact

- Determinism and grounding: strong alignment
- Auditability and compliance: strong alignment
- Cost and latency: good near-term predictability
- Marketplace readiness: strong launch fit

## Revisit Triggers

Re-open this ADR if any of the following occur:
- retrieval quality fails agreed acceptance criteria in production pilots
- latency or cost SLOs cannot be met with graph-first strategy
- customer requirements mandate stronger replay/event-sourcing guarantees
- marketplace review requires packaging changes that alter architecture boundaries

## Related Documents

- [docs/objectives.md](../../objectives.md)
- [docs/architecture/options.md](../options.md)
- [docs/architecture/architecture-brief.md](../architecture-brief.md)
- [docs/marketplace-readiness-checklist.md](../../marketplace-readiness-checklist.md)
