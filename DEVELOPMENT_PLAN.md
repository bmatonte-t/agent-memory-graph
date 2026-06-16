# Development Plan: Cognitive Agent Memory Graph

**Status**: Phase planning and roadmap definition  
**Last Updated**: 2026-06-16  
**Target Launch**: Google Cloud Marketplace (end of phase 6)

## Overview

This plan structures the build of the Cognitive Agent Memory Graph from architecture implementation through marketplace launch. Each phase includes specific deliverables, success criteria, and testing gates aligned to the [Marketplace Readiness Checklist](marketplace-readiness-checklist.md) and [ADR-0001](architecture/adr/ADR-0001-phase-one-architecture.md).

## Phase 1: Foundation and Core Memory Layer

**Duration**: 4-6 weeks  
**Goal**: Build and validate the tripartite memory model and Spanner Graph schema.

### Deliverables

1. **Spanner Graph Schema and Schema-as-Code**
   - Define MemoryNode and MemoryEdge tables with interleaving optimization
   - Create property graph mappings for Context, Semantic, and Audit tiers
   - Implement schemaless JSON handling for dynamic attribute growth
   - Version control all DDL

2. **Core Memory APIs**
   - `memory.create_session()` - initialize Context Graph for a session
   - `memory.add_semantic_fact()` - ingest entities into Semantic Graph with baseline weights
   - `memory.record_audit_event()` - append events to Audit Graph
   - `memory.retrieve_context_window()` - fetch recent session history via GQL
   - All APIs return typed responses and error handling

3. **Cognitive Weighting Implementation**
   - Implement `cognitive_weight` and `last_accessed` fields on all semantic nodes/edges
   - Build baseline weight assignment (e.g., 0.50 for new facts)
   - Implement weight update logic: confirmation bias loop (+0.15 on successful use)
   - Implement temporal decay background job (Cloud Run + Cloud Scheduler)

4. **Testing and Validation**
   - Unit tests for memory API contracts
   - Integration tests for tripartite memory isolation
   - Load test for schema performance (10K nodes, 100K edges)
   - Audit trail verification tests

### Success Criteria

- Schema deployed on test Spanner instance with baseline performance metrics
- Memory APIs pass all unit and integration tests
- Cognitive weight updates are transactional and auditable
- Decay job runs idempotently and maintains data consistency
- Documentation: data model spec and API reference

---

## Phase 2: MindMap Query Pipeline

**Duration**: 4-6 weeks  
**Goal**: Implement the Mine -> Aggregate -> Serialize -> Synthesize pipeline with grounding enforcement.

### Deliverables

1. **Mining and Entity Extraction**
   - Vertex AI Gemini Flash integration for intent/entity extraction
   - JSON Schema output constraint for structured entity payloads
   - Type validation for extracted entities
   - Telemetry: track extraction latency and error rates

2. **Graph Aggregation (GQL)**
   - GQL-based variable-length path traversal with cognitive horizon filtering
   - Implement retrieval that respects `cognitive_weight > 0.30` (configurable)
   - Query optimization for multi-hop traversal on interleaved schema
   - Support for Context + Semantic graph simultaneous traversal
   - Return edge metadata for provenance linking

3. **Evidence Serialization**
   - Convert GQL result sets to structured fact statements (markdown or JSON)
   - Include edge labels and weights in serialized output
   - Support human-readable and machine-parseable formats
   - Validation: facts match GQL results bidirectionally

4. **Grounded Synthesis**
   - Vertex AI Gemini Pro integration for response generation
   - System prompt enforcement: "Use ONLY provided facts; if insufficient, return 'Insufficient graph evidence.'"
   - Response validation: all claims trace back to serialized facts
   - Fallback behavior when graph evidence is incomplete

5. **Traceability and Audit**
   - Link each response to (mined entities) -> (traversal paths) -> (serialized facts)
   - Record MindMap execution subgraph in Audit memory
   - Create example reasoning chains for documentation

6. **Testing and Validation**
   - Unit tests for each pipeline stage (mine, aggregate, serialize, synthesize)
   - Integration tests for end-to-end MindMap flow
   - Adversarial tests: prompts with insufficient evidence should trigger insufficiency
   - Latency benchmarks for p95 retrieval + synthesis
   - Traceability verification tests

### Success Criteria

- MindMap pipeline passes all integration tests
- Response grounding is demonstrable with audit trail
- Insufficient evidence returns explicit statement (no guessing)
- Latency targets: extraction <500ms, aggregation <2s, synthesis <3s (p95)
- Documentation: pipeline architecture, example reasoning chains, error handling

---

## Phase 3: Agent Orchestration and Tool Integration

**Duration**: 3-4 weeks  
**Goal**: Wire memory layer to Vertex AI agents via Model Context Protocol (MCP).

### Deliverables

1. **MCP Server Implementation**
   - Expose memory layer as MCP tools:
     - `memory_search(query)` - invoke MindMap pipeline
     - `memory_add_fact(entity, attributes)` - ingest into Semantic Graph
     - `memory_log_trace(decision_context)` - record reasoning step to Audit
     - `memory_recall_context()` - fetch session context window
   - Tool error contract and fallback handling
   - Tool execution telemetry (latency, errors, token usage)

2. **Agent Framework Integration**
   - Connect Vertex AI agent to MCP server
   - Implement agent orchestration loop: prompt -> MCP call -> response
   - Support supervisor/worker agent pattern if multi-agent required
   - Enforce MCP tools as primary memory interaction path

3. **Testing and Validation**
   - Unit tests for MCP tool contracts
   - Agent end-to-end tests (multi-turn conversation with memory)
   - Memory consistency tests across agent sessions
   - Load test: concurrent agent sessions
   - Observability validation (tracing shows request ID through tool chain)

### Success Criteria

- MCP server deployment on Cloud Run with auto-scaling
- Agent successfully uses memory tools
- Memory updates are visible in subsequent turns
- Observability shows end-to-end request tracing
- Documentation: MCP tool reference, agent integration guide

---

## Phase 4: Security, Observability, and Marketplace Readiness

**Duration**: 4-6 weeks  
**Goal**: Harden system for enterprise and marketplace standards.

### Deliverables

1. **Security Hardening**
   - IAM policies: least-privilege service accounts
   - Audit memory immutability: controls that reject deletion/updates
   - Tenant isolation if multi-tenant (append tenant_id to all nodes)
   - Input validation on all API boundaries
   - Error messages that don't leak system internals

2. **Observability Stack**
   - Cloud Trace integration: propagate request ID through entire pipeline
   - Cloud Logging: structured logs for all memory operations
   - Cloud Monitoring: SLI dashboards for availability, latency, error rate
   - Custom metrics: cognitive weight distribution, graph size, token consumption
   - Alert rules for SLO violations

3. **Documentation and Runbooks**
   - Operations guide: deployment architecture, scaling, backups
   - Troubleshooting guide: common failure modes and diagnostics
   - Admin guide: tenant management, retention policies, cost controls
   - Support playbook: escalation paths and RCA process

4. **Testing and Compliance**
   - Security audit: IAM, data handling, compliance controls
   - Penetration testing basics (input injection, access boundary violations)
   - Compliance checklist review (CCPA, GDPR readiness basics)
   - SLO and SLI validation under load
   - Chaos/resilience testing for failure modes

5. **Marketplace Package**
   - Publish security architecture document
   - Create quickstart and deployment guide for buyers
   - Define pricing/editions model (if applicable)
   - Prepare listing assets (screenshots, architecture diagrams, demo)

### Success Criteria

- Security audit passes with no critical findings
- Observability dashboard shows system health metrics
- Runbooks and troubleshooting guide are complete and validated
- All items in [Marketplace Readiness Checklist](marketplace-readiness-checklist.md) are marked pass
- Deployment on test marketplace instance is successful
- Documentation review by internal security and product teams passes

---

## Phase 5: Comparative User Testing Pilot

**Duration**: 3-4 weeks  
**Goal**: Design and execute a structured user testing pilot that compares this agent with similar tools available in GCP Marketplace.

### Deliverables

1. **Comparative Study Design**
   - Define competitor set (3-5 similar Marketplace tools by category and use case)
   - Define user profiles and tasks (operators, developers, data teams)
   - Define test protocol: moderated tasks, scripted prompts, and scoring rubric
   - Pre-register evaluation criteria to reduce bias

2. **Evaluation Framework and Instrumentation**
   - Standardize scenarios and data across all tools
   - Metrics: task success rate, time-to-completion, perceived trust, explainability, and setup effort
   - Technical metrics: latency, error rate, grounding confidence, and operational complexity
   - Add survey instruments (SUS or equivalent, confidence/trust questions)

3. **Pilot Execution**
   - Recruit 8-15 participants across target buyer profiles
   - Run A/B or round-robin sessions across compared tools
   - Collect quantitative and qualitative feedback
   - Capture friction logs and support burden observations

4. **Analysis and Product Actions**
   - Build comparative scorecard and strengths/gaps analysis
   - Prioritize remediation backlog from pilot findings
   - Update messaging and differentiation based on evidence
   - Update docs, onboarding, and UX gaps discovered in pilot

### Success Criteria

- Comparative test completes with enough participant coverage
- Scorecard clearly demonstrates strengths/weaknesses vs similar tools
- Top-priority usability and trust issues are converted into actionable backlog
- Updated value proposition is evidence-backed and buyer-relevant

---

## Phase 6: Marketplace Launch and Go-Live

**Duration**: 2-4 weeks  
**Goal**: Finalize listing, launch, and establish stable support operations.

### Deliverables

1. **Marketplace Listing**
   - Submit to Google Cloud Marketplace with all required materials
   - Coordinate with Google for review and approval
   - Prepare launch communication (blog, announcement)

2. **Go-Live Support**
   - Establish support process (Slack, email, ticketing)
   - Prepare incident response team
   - Document known limitations for launch
   - Prepare week-1 and week-4 launch health reviews

3. **Post-Launch Validation**
   - Validate production SLO metrics and support SLAs
   - Track onboarding completion and time-to-value
   - Confirm top pilot remediations are reflected in launch artifacts

### Success Criteria

- Marketplace approval is granted
- Go-live metrics meet or exceed targets (availability >99.9%, p95 latency <5s)
- Support process is operational
- Launch KPIs and support KPIs are stable for first 30 days

---

## Development Practices

### Specification-Driven Approach

Before implementing each phase, a detailed spec is reviewed and approved:
- Acceptance criteria are explicit
- Interfaces and contracts are defined
- Architecture decisions are documented
- Testing strategy is planned upfront

### Test-Driven Development

- Unit tests are written before implementation
- Integration tests validate contracts across components
- Load and chaos tests ensure operational readiness
- All tests pass before code review

### Incremental Implementation

- Each phase delivers a working, testable increment
- Features are decoupled to allow partial progress
- Backward compatibility is maintained across phases
- Rollback strategy exists for each phase

### Code Review and Quality

- All code changes pass peer review across five dimensions:
  - Correctness: code works and handles edge cases
  - Readability: clear intent and maintainability
  - Architecture: alignment with mandates and decisions
  - Security: no data leaks, proper auth/audit
  - Performance: meets latency and cost targets
- Automated checks: lint, type checking, test coverage

### Observability from Day One

- Instrumentation is built into every phase
- Request IDs propagate through all layers
- Metrics are exported continuously
- Runbooks are written in parallel with features

---

## Success Metrics

### Phase-Level Gates

| Phase | Go/No-Go Gate | Owner |
|-------|---------------|-------|
| Phase 1 | Schema deployed, memory APIs functional | Eng Lead |
| Phase 2 | MindMap pipeline passes end-to-end tests | Eng Lead |
| Phase 3 | Agent orchestration live and tested | Eng Lead |
| Phase 4 | Marketplace Readiness Checklist all pass | Product + Eng |
| Phase 5 | Comparative user testing completed and analyzed | Product Research |
| Phase 6 | Marketplace launch approved and stable | Product Lead |

### Product Metrics (Phase 4+)

- Availability: 99.9% (multi-region Spanner SLA)
- Latency (p95): <5s for end-to-end response
- Hallucination rate: <2% (graph-grounded responses)
- Token efficiency: 40-80% reduction vs. baseline RAG
- Auditability: 100% of responses traceable to evidence
- User testing delta: measurable gain in trust and task success vs compared tools

---

## Dependencies and Risks

### Critical Dependencies

- Google Cloud Spanner Graph availability and maturity
- Vertex AI Gemini Flash/Pro availability
- GCP quota and service limits for pilot/launch scale
- Availability of comparable Marketplace tools for fair benchmarking

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Spanner performance degrades with scale | Medium | High | Load test early, optimize schema interleaving |
| MindMap latency exceeds targets | Medium | High | Profile and optimize GQL query planning |
| Marketplace approval delayed | Low | Medium | Engage Google early, follow all guidelines |
| Comparative pilot is biased or inconclusive | Medium | High | Pre-register rubric, standardize scenarios, independent review |
| Security audit finds critical issues | Low | High | Security review in phase 4, penetration test early |

---

## Next Steps

1. Approve this plan and assign phase leads
2. Create detailed task breakdown for Phase 1 (schema and core APIs)
3. Create comparative testing protocol draft and tool short-list for Phase 5
4. Set up development environment (test Spanner instance, Cloud Run project)
5. Begin Phase 1 with spec-driven approach (write API specs before code)
