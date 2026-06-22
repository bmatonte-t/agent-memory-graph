# Development Plan: Cognitive Agent Memory Graph

**Status**: Phase planning and roadmap definition with visible progress tracking
**Version**: v0.2 development plan
**Last Updated**: 2026-06-22
**Target Launch**: Google Cloud Marketplace

## Overview

Version 0.1 established the tripartite memory baseline, MindMap pipeline, MCP orchestration, and the first security/observability pass.

Version 0.2 expands the product into a harder production system with:

- tenant-scaled cognitive weighting tied to agent activity volume,
- better lock resilience for semantic and audit writes,
- real authorization for agents over subgraphs and node sets,
- selected MindMap evidence-quality improvements,
- selected Engram confidence and contradiction improvements.

This document keeps v0.1 as the completed foundation and defines the development path for v0.2.

## Progress Snapshot

- v0.1: Complete. Core memory, MindMap, MCP, and baseline hardening are in place.
- v0.2: Planned/in progress. Hardening, authorization, resilience, and evidence-quality work are the current focus.

### Completed v0.1 Baseline

- Tripartite memory model, schema, and audit trail foundation.
- Grounded MindMap retrieval and synthesis with traceability.
- MCP tool contract and orchestration integration.
- Observability safety baseline and local validation guidance.

## v0.2 Development Goals

### 1. Tenant-Scaled Cognitive Weighting

Add configuration so cognitive weighting frequency and/or strength can scale with tenant agent activity volume.

#### What this means

- A tenant with 1 million agent actions per day should receive more weighting opportunities than a tenant with 100 actions per day.
- Keep the current baseline behavior available as a safe default.
- Prefer thresholded tiers over simple per-call linear scaling.

#### Deliverables

- Add config and settings options for weighting tiers.
- Count successful agent actions at orchestration/MCP boundaries.
- Feed trigger tier context into existing weight updates.
- Preserve immediate weighting as a fallback when tiering is disabled.

#### Success Criteria

- High-volume tenants trigger more weighting than low-volume tenants.
- Phase 0 baseline is in place with the cumulative session counter feeding the weighting trigger path.
- Existing APIs still work with the new config disabled.

### 2. Lock Resilience and Write Safety

Improve concurrent write behavior so semantic and audit paths survive contention and retries without duplicating effects.

#### Deliverables

- Classify transient Spanner failures.
- Add bounded retry/backoff for write operations.
- Add idempotency boundaries for mutation paths.
- Make critical weight-update behavior observable instead of silent-best-effort.

#### Success Criteria

- Concurrent writes do not create duplicate semantic side effects.
- Transient contention errors recover automatically within bounded retry limits.
- Audit writes remain append-only and traceable.

### 3. Real Agent Authorization

Replace binary tenant-only access with ABAC rules that can scope agents to specific subgraphs, node sets, labels, and relationship families.

#### Deliverables

- Extend request contracts with agent identity and policy attributes.
- Enforce ABAC at MCP dispatch.
- Enforce ABAC on MemoryAPI reads and writes.
- Audit grant/deny decisions with reason codes.
- Support resource predicates based on tenant, tier, node IDs, labels, and path scope.

#### Success Criteria

- A denied agent cannot read or write outside its allowed subgraph.
- Authorization failures are auditable and client-safe.
- The current implementation already enforces deny-by-default checks at MCP and MemoryAPI boundaries for the core memory and trace paths.

### 4. MindMap-Inspired Evidence Quality

Adopt the useful parts of the original MindMap implementation without adopting the research-script architecture wholesale. Take ideas from [MindMap](https://github.com/wyl-willing/MindMap) to improve evidence provenance, neighbor-based enrichment, and deterministic retrieval.

#### Deliverables

- Add richer evidence provenance to serialized paths.
- Add bounded neighbor-based enrichment where it improves grounding.
- Keep retrieval deterministic and compact.
- Preserve explicit insufficient-evidence behavior.

#### Success Criteria

- Evidence is easier to inspect and trace.
- Returned context stays bounded and policy-compliant.

### 5. Engram-Inspired Confidence Quality

Adopt the useful parts of Engram’s confidence and contradiction handling without replacing the current memory model. Take ideas from [Engram](https://github.com/Harshitk-cp/engram) to improve confidence metadata, freshness awareness, and contradiction detection.

#### Deliverables

- Add source-aware confidence metadata.
- Add freshness awareness to synthesis eligibility.
- Add a lightweight contradiction/tension detection hook at ingest.
- Gate high-impact synthesis claims on confidence and contradiction status.

#### Success Criteria

- Confidence and freshness influence whether a fact is used.
- Conflicting facts are visible rather than silently absorbed.

## v0.2 Phases

### Phase 0: Decision Freeze

**Goal**: Lock the v0.2 design so implementation stays consistent across weighting, resilience, and authorization.

#### Deliverables

1. Define tenant action-trigger thresholds and how they affect weighting.
2. Define the ABAC policy model for agents and graph resources.
3. Define transient error classification and idempotency strategy.

#### Success Criteria

- A single canonical policy exists for weighting, authorization, and retries.

### Phase 1: Action-Scaled Weighting

**Goal**: Make weighting scale with tenant activity volume.

#### Deliverables

1. Add config for weighting tiers and scaling strategy.
2. Count successful agent actions in the orchestration/MCP path.
3. Pass trigger context into weight updates for context and semantic memory.
4. Add tests that compare high-volume and low-volume tenant behavior.

#### Success Criteria

- High-volume tenants get more weighting opportunities than low-volume tenants.

### Phase 2: Lock Resilience

**Goal**: Make write paths robust under contention.

#### Deliverables

1. Add retry/backoff around transient write failures.
2. Add idempotency keys to mutation flows.
3. Make weight-update failures visible and recoverable.
4. Add contention and duplicate-request tests.

#### Success Criteria

- Concurrent writes recover safely and do not duplicate effects.

### Phase 3: ABAC Authorization

**Goal**: Enforce real authorization for agent access to graph resources.

#### Deliverables

1. Add agent identity and authorization attributes to request contracts.
2. Enforce policy at MCP tool dispatch.
3. Enforce policy at MemoryAPI query/mutation boundaries.
4. Audit grant/deny decisions.
5. Add allow/deny tests for node-set and subgraph access.

#### Success Criteria

- Unauthorized reads and writes are denied at the boundary.

### Phase 4: MindMap Evidence Quality

**Goal**: Improve evidence traceability and usefulness.

#### Deliverables

1. Add provenance to serialized path evidence.
2. Add bounded neighbor evidence when appropriate.
3. Keep evidence compact and deterministic.
4. Verify no-evidence behavior remains explicit.

#### Success Criteria

- Evidence quality improves without expanding the system into a research prototype.

### Phase 5: Engram Confidence Quality

**Goal**: Improve confidence and contradiction handling.

#### Deliverables

1. Add source-aware confidence metadata.
2. Add freshness gating.
3. Add contradiction/tension detection hooks.
4. Use confidence signals to gate synthesis.

#### Success Criteria

- Low-confidence or conflicting facts do not dominate responses.

### Phase 6: Documentation and Rollout

**Goal**: Prepare v0.2 for validation and rollout.

#### Deliverables

1. Update the development plan and API docs.
2. Document new config knobs and policy rules.
3. Update runbooks for retries, auth boundaries, and evidence quality.
4. Add rollout notes for shadow mode and canary behavior.

#### Success Criteria

- v0.2 is documented, testable, and safe to roll out incrementally.

## Development Practices

### Specification-Driven Approach

Before implementing each phase, a detailed spec is reviewed and approved:

- Acceptance criteria are explicit.
- Interfaces and contracts are defined.
- Architecture decisions are documented.
- Testing strategy is planned upfront.

### Test-Driven Development

- Unit tests are written before implementation.
- Integration tests validate contracts across components.
- Load and chaos tests ensure operational readiness.
- All tests pass before code review.

### Incremental Implementation

- Each phase delivers a working, testable increment.
- Features are decoupled to allow partial progress.
- Backward compatibility is maintained across phases.
- Rollback strategy exists for each phase.

### Code Review and Quality

- All code changes pass peer review across five dimensions:
  - Correctness: code works and handles edge cases.
  - Readability: clear intent and maintainability.
  - Architecture: alignment with mandates and decisions.
  - Security: no data leaks, proper auth/audit.
  - Performance: meets latency and cost targets.
- Automated checks: lint, type checking, test coverage.

### Observability from Day One

- Instrumentation is built into every phase.
- Request IDs propagate through all layers.
- Metrics are exported continuously.
- Runbooks are written in parallel with features.

## Success Metrics

### Phase-Level Gates

- Phase 0 gate: policy and implementation contracts frozen.
- Phase 1 gate: tenant-scaled weighting works and is configurable.
- Phase 2 gate: retry/idempotency behavior survives contention.
- Phase 3 gate: ABAC is enforced for tool and subgraph access.
- Phase 4 gate: MindMap evidence quality improvements are in place.
- Phase 5 gate: Engram-inspired confidence handling is in place.
- Phase 6 gate: docs and rollout plan are ready for internal validation.

### Product Metrics (v0.2)

- Availability: 99.9% target.
- Latency (p95): stable end-to-end response within current SLO.
- Authorization coverage: all agent actions checked against policy.
- Auditability: 100% of denied and granted policy decisions logged.
- Weighting fairness: high-volume tenants trigger more weighting than low-volume tenants.
- Evidence quality: grounded responses stay compact, traceable, and explicit when evidence is insufficient.

## Dependencies and Risks

### Critical Dependencies

- Google Cloud Spanner Graph contention behavior.
- Settings/config wiring for new v0.2 options.
- Final ABAC policy source of truth.
- Availability of the selected MindMap and Engram ideas that fit this architecture.

### Risks and Mitigations

- Risk: weighting becomes noisy for heavy tenants. Mitigation: thresholded tiers and bounded updates.
- Risk: retry hides real data issues. Mitigation: classify transient vs permanent failures clearly.
- Risk: ABAC becomes hard to reason about. Mitigation: keep policies declarative and audit every decision.
- Risk: evidence enrichment expands context too much. Mitigation: cap neighbors and preserve deterministic insufficiency behavior.
- Risk: contradiction handling causes false positives. Mitigation: start with annotate-only mode, then gate synthesis later.

## Next Steps

1. Approve this v0.2 plan.
2. Break Phase 0 into implementation tickets.
3. Define the new settings model and policy contract.
4. Start Phase 1 with tests for tenant-scaled weighting tiers.
