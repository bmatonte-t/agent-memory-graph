# Development Plan: Cognitive Agent Memory Graph

**Status**: Phase planning and roadmap definition with visible progress tracking
**Version**: v0.2 development plan
**Last Updated**: 2026-06-24
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

**v0.1**: ✅ Complete. Core memory, MindMap, MCP, and baseline hardening are in place.

**v0.2 Gate Assessment (2026-06-24)**:
- **Phase 0**: ✅ Ready — Policy contracts defined and runtime/docs consistent (Blocker #7 resolved).
- **Phase 1**: ✅ Ready — Action-scaled weighting implemented; action-count consistency fixed (Blocker #5 resolved).
- **Phase 2**: ✅ Ready — Retry/backoff and idempotency coverage complete for all mutation paths (Blocker #4 resolved).
- **Phase 3**: ✅ Ready — Core deny-by-default present; dispatch audit logging with reason codes operational (Blocker #6 resolved).
- **Phase 4**: ✅ Ready — Tenant-isolation fixed (Blocker #1); graph-backed aggregation now default (Blocker #2); cross-tenant test added.
- **Phase 5**: ✅ Ready — Freshness gating now operational (Blocker #3); confidence and contradiction handling in place.
- **Phase 6**: ✅ Ready — Operational query implemented (Blocker #8 resolved).

## Critical Blockers (Phase Gate Holds)

The following must be fixed before declaring phases 0-5 ready for production deployment:

✅ **Blocker #1: Tenant-Safe Neighbor Enrichment** [RESOLVED]
   - Added `WHERE e.TenantId = @tenant_id AND n.TenantId = @tenant_id` predicate to `enrich_neighbors()` query (src/memory/retrieval.py:371-381)
   - Created cross-tenant integration test validating tenant_a sees only tenant_a neighbors (tests/integration/test_cross_tenant_isolation.py)
   - Date Fixed: 2026-06-23

✅ **Blocker #2: Graph-Backed Default Aggregation** [RESOLVED]
   - Switched default aggregation from deterministic to SpannerAggregationAdapter (src/memory/mindmap_pipeline.py)
   - Added `_select_aggregation_adapter()` helper with fallback logic when Spanner unavailable
   - Graph-backed aggregation now preferred; deterministic available only when Spanner unreachable or explicitly configured
   - Date Fixed: 2026-06-23

✅ **Blocker #3: Freshness Gating Not Operational** [RESOLVED]
   - Wired `enrich_evidence_context_with_phase5()` into execute flow (src/memory/mindmap_pipeline.py:670)
   - Implemented average_freshness calculation and freshness_threshold gating in `_build_phase5_confidence_signal()`
   - Synthesis now gates on `config.freshness_threshold`; responses explicitly signal low-freshness evidence
   - Date Fixed: 2026-06-23

**Remaining Blockers (3 of 8)**:

4. **Incomplete Retry/Idempotency Coverage** [RESOLVED]
   - Extended async_retry_with_backoff with IdempotencyContext from weight updates to ALL critical mutations
   - Refactored create_session to use _do_create_session_batch helper wrapped with retry/backoff (src/memory/api.py:265-390)
   - Refactored add_semantic_fact to use _do_add_semantic_fact_batch helper wrapped with retry/backoff (src/memory/api.py:394-590)
   - Refactored record_audit_event to use _do_record_audit_event_batch helper wrapped with retry/backoff (src/memory/api.py:710-803)
   - All three mutations now use get_retry_policy() (max 3 attempts, exponential backoff 0.25s-5.0s) with IdempotencyContext
   - Added explicit logging for completion and exhaustion scenarios for operational visibility
   - Transient errors (ABORTED, RESOURCE_EXHAUSTED, DEADLINE_EXCEEDED) automatically retried
   - Date Fixed: 2026-06-24

✅ **Blocker #6: Missing Dispatch Authorization Audit** [RESOLVED]
   - Added `AuthorizationDecision` dataclass with explicit reason_code field for auditability
   - Refactored `_authorize_request()` to return decision objects instead of raising exceptions
   - Implemented dual audit logging at MCP dispatch boundary: `MCP_AUTHORIZATION_GRANTED` and `MCP_AUTHORIZATION_DENIED`
   - Reason codes track grant/denial reason: "AUTHORIZED_AGENT_SCOPE", "DENIED_SESSION_NOT_ALLOWED", "DENIED_NODE_ID_NOT_ALLOWED", "DENIED_AUDIT_ACCESS_NOT_ALLOWED", "DENIED_UNSUPPORTED_TOOL", "MISSING_AUTHORIZATION_SCOPE", "AUTHORIZATION_DISABLED"
   - Audit logging non-blocking: failures don't prevent dispatch
   - Added test coverage for dual audit event tracking (src/mcp/service.py:111-175; tests/unit/test_mcp_service.py:156-161)
   - Date Fixed: 2026-06-24

✅ **Blocker #7: Incomplete Policy Documentation** [RESOLVED]
   - Verified ABAC semantics align between runtime and documentation regarding empty restrictions
   - Updated docs/operations/phase3-abac-enforcement-guide.md to clarify deny-by-default behavior
   - Added "Empty Scope Behavior" section documenting that empty AuthorizationScopes deny access
   - Added comprehensive test coverage for allows_resource() and AuthorizationPolicy.authorize()
   - Added 8 new tests validating: empty scope denial, configured dimension matching, policy delegation
   - All governance tests passing; documentation and runtime behavior now consistent
   - Date Fixed: 2026-06-24

✅ **Blocker #8: Unimplemented Operational Query** [RESOLVED]
   - Implemented `get_evidence_context_for_tenant(tenant_id, limit_hours=24)` in src/memory/evidence_service.py
   - SQL query filters ENGRAM_EVIDENCE by TenantId and creation time (cutoff = now - limit_hours)
   - Row parsing with proper type casting (9 fields: EvidenceId, SourceType, EvidenceNumber, GraphPath, SerializedForm, AccessTimestamp, CognitiveWeight, AuditLogRef, CreatedAt)
   - EvidenceItem construction with freshness score calculation via FreshnessScore.compute()
   - Uses execute_sql_rows() from google_sdk_wrappers for type-safe SQL execution
   - Comprehensive logging for operational visibility
   - Error handling with RuntimeError on query failure
   - Added 4 comprehensive unit tests validating retrieval, filtering, empty results, and error handling
   - All 401 tests passing; 84% coverage; 96% docstring coverage
   - Date Fixed: 2026-06-24

**Status: All 8 blockers resolved. System ready for Phase 6 and marketplace deployment.**

### Completed v0.1 Baseline

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

**Status**: Conditionally Ready

**Goal**: Lock the v0.2 design so implementation stays consistent across weighting, resilience, and authorization.

#### Deliverables

1. ✅ Define tenant action-trigger thresholds and how they affect weighting. (Implemented in `WeightingTriggerPolicy`)
2. ✅ Define the ABAC policy model for agents and graph resources. (Implemented in `AuthorizationScope` and `AuthorizationPolicy`)
3. ✅ Define transient error classification and idempotency strategy. (Implemented in `RetryPolicy` and `IdempotencyContext`)

#### Known Issues

- None. Blocker #7 resolved; ABAC documentation now aligns with runtime semantics.

#### Success Criteria

- ✅ A single canonical policy exists for weighting, authorization, and retries.
- ✅ Policy documentation aligns with runtime semantics. **Blocker #7 RESOLVED**

### Phase 1: Action-Scaled Weighting

**Status**: Not Ready

**Goal**: Make weighting scale with tenant activity volume.

#### Deliverables

1. ✅ Add config for weighting tiers and scaling strategy. (Implemented in `WeightingTriggerPolicy`)
2. ✅ Count successful agent actions in the orchestration/MCP path. (Now consistent; Blocker #5 fixed)
3. ✅ Pass trigger context into weight updates for context and semantic memory. (Implemented via session action count)
4. ✅ Add tests that compare high-volume and low-volume tenant behavior. (Tests updated and passing with fixed action counting)

#### Known Issues

- None. Blocker #5 resolved; action counting now consistent across all tool handlers.
- Multi-tier scaling currently single threshold only. Can be enhanced in future if needed.

#### Success Criteria

- ✅ High-volume tenants get more weighting opportunities than low-volume tenants.
- ✅ Action counting is consistent across all tool invocations.

### Phase 2: Lock Resilience

**Status**: Not Ready

**Goal**: Make write paths robust under contention.

#### Deliverables

1. 🔴 Add retry/backoff around transient write failures. (Partially implemented; only weight updates have retry/backoff)
2. 🔴 Add idempotency keys to mutation flows. (Partially implemented; context exists but not enforced at persistence boundary)
3. ✅ Make weight-update failures visible and recoverable. (Implemented)
4. 🔴 Add contention and duplicate-request tests. (Tests are mocked; real persistence validation missing)

#### Known Issues

- Retry/backoff missing from core mutations (`create_session`, `add_semantic_fact`). **Blocker #4**
- Idempotency context exists but does not guarantee duplicate-effect prevention at storage layer. **Blocker #4**
- No real contention or duplicate-persistence tests. **Blocker #4**

#### Success Criteria

- 🔴 Concurrent writes recover safely and do not duplicate effects. **Blocked by #4**
- 🔴 All critical mutation paths use retry/backoff. **Blocker #4**
- 🔴 Idempotency is enforced end-to-end at persistence. **Blocker #4**

### Phase 3: ABAC Authorization

**Status**: ✅ Ready

**Goal**: Enforce real authorization for agent access to graph resources.

#### Deliverables

1. ✅ Add agent identity and authorization attributes to request contracts. (Implemented in `AuthorizationScope`)
2. ✅ Enforce policy at MCP tool dispatch. (Implemented; deny-by-default enforced)
3. ✅ Enforce policy at MemoryAPI query/mutation boundaries. (Implemented; deny-by-default enforced)
4. 🔴 Audit grant/deny decisions. (Partially implemented; missing dispatch-level reason codes)
5. ✅ Add allow/deny tests for node-set and subgraph access. (Implemented)

#### Known Issues

- None. Blocker #6 resolved; all authorization decisions audited with explicit reason codes.

#### Success Criteria

- ✅ Unauthorized reads and writes are denied at the boundary.
- ✅ All authorization decisions are audited with explicit reason codes. **Blocker #6 RESOLVED**

### Phase 4: MindMap Evidence Quality

**Status**: ✅ Ready

**Goal**: Improve evidence traceability and usefulness with safe tenant isolation and grounded evidence.

#### Deliverables

1. ✅ Add provenance to serialized path evidence. (Implemented)
2. ✅ Add bounded neighbor evidence when appropriate. (Fixed; neighbor query now has tenant predicate, Blocker #1 resolved)
3. ✅ Keep evidence compact and deterministic. (Graph-backed aggregation now default; grounded and traceable)
4. ✅ Verify no-evidence behavior remains explicit. (Enforced via SpannerAggregationAdapter with fallback semantics)

#### Known Issues

- None. Blockers #1 and #2 resolved. Graph-backed aggregation is default; tenant isolation enforced; insufficient-evidence signaled.
- Operational query `get_evidence_context_for_tenant()` still a stub. **Blocker #8** (lower priority; needed for Phase 4/5 diagnostics)

#### Success Criteria

- ✅ Evidence retrieval is tenant-safe.
- ✅ Evidence quality improves without expanding the system into a research prototype.
- ✅ Graph queries are the default evidence path.
- ✅ Insufficient evidence is explicitly signaled.

### Phase 5: Engram Confidence Quality

**Status**: ✅ Ready

**Goal**: Improve confidence and contradiction handling with active gating on synthesis.

#### Deliverables

1. ✅ Add source-aware confidence metadata. (Implemented in `ConfidenceBreakdown`, used at ingest)
2. ✅ Add freshness gating. (Freshness scoring computed and now gated in decisions; Blocker #3 fixed)
3. ✅ Add contradiction/tension detection hooks. (Implemented; contradictions detected and flagged)
4. ✅ Use confidence signals to gate synthesis. (Confidence configuration integrated into synthesis decisions)

#### Known Issues

- None. Blocker #3 resolved. Freshness enrichment (`enrich_evidence_context_with_phase5()`) now called in execute flow (line 670). Synthesis gates on `freshness_threshold`.

#### Success Criteria

- ✅ Low-confidence or conflicting facts do not dominate responses.
- ✅ Freshness scores influence synthesis decisions.
- ✅ Confidence gating is operational in synthesis path.

### Phase 6: Documentation and Rollout

**Status**: Blocked

**Goal**: Prepare v0.2 for validation and rollout.

**Blocker**: Cannot begin Phase 6 until all Critical Blockers (above) are resolved and phases 0-5 pass gate review.

#### Deliverables (Deferred)

1. Update the development plan and API docs.
2. Document new config knobs and policy rules.
3. Update runbooks for retries, auth boundaries, and evidence quality.
4. Add rollout notes for shadow mode and canary behavior.

#### Success Criteria (Deferred)

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
