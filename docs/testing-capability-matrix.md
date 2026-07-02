# Testing Capability Matrix

## Scope

This matrix defines canonical coverage for critical capabilities.

Rules:
- One critical behavior, one canonical test.
- Integration remains boundary-focused.
- New tests must map to an existing row in this matrix.

## Capability To Risk To Test

| capability | critical_risks | component canonical tests | contract canonical tests | integration canonical tests | owner |
|---|---|---|---|---|---|
| authorization and tenant isolation | cross-tenant access and scope escalation | tests/unit/test_authorization_boundary.py, tests/unit/test_validators.py, tests/unit/test_governance_adapter.py | tests/unit/test_governance.py, tests/unit/test_security_audit.py | tests/integration/test_phase3_abac_enforcement.py, tests/integration/test_cross_tenant_isolation.py | platform security |
| audit immutability and compliance | missing evidence and mutable audit trail | tests/unit/test_audit_immutability.py | tests/unit/test_memory_api.py | tests/integration/test_audit_trail.py, tests/integration/test_phase4_hardening_integration.py | platform governance |
| mindmap retrieval and synthesis | ungrounded responses and incorrect path retrieval | tests/unit/test_mindmap_pipeline.py, tests/unit/test_phase5c_evidence_service.py | tests/unit/test_mcp_service.py, tests/unit/test_mcp_api.py | tests/integration/test_phase4b_path_retrieval.py, tests/integration/test_phase4e_evidence_synthesis.py, tests/integration/test_mindmap_integration.py | memory domain |
| cognitive weighting and decay | stale memory prioritization and pruning regressions | tests/unit/test_cognitive_weighting.py | tests/unit/test_memory_api.py | tests/integration/test_weight_update_resilience.py, tests/load/test_comparative_weighting.py | memory domain |
| ingestion and extraction pipelines | data loss, duplicate entities, and broken orchestration | tests/unit/pipelines/test_bigquery_ingestion_phase_a1.py, tests/unit/pipelines/test_bigquery_ingestion_phase_a2.py, tests/unit/pipelines/test_bigquery_ingestion_phase_a3.py, tests/unit/pipelines/test_document_extractor_phase_b1.py | tests/unit/pipelines/test_extraction_api_phase_c.py, tests/unit/pipelines/test_extraction_orchestrator_phase_b3.py | tests/integration/test_extraction_pipeline_phase_e.py, tests/integration/test_scheduler_integration.py | data pipeline |
| external adapters and clients | retry failures, auth adapter mismatch, and contract drift | tests/unit/test_client_base.py, tests/unit/test_client_retry.py, tests/unit/test_client_rate_limit.py | tests/unit/test_vertex_adapter.py, tests/unit/test_agent_api.py | tests/integration/test_client_integration.py, tests/integration/test_external_auth_adapter.py | api platform |
| observability and operations | missing traces and weak operational signals | tests/unit/test_cloud_logging_export.py, tests/unit/test_metrics_emission.py, tests/unit/test_observability_safety.py | tests/unit/test_agent_orchestrator.py | tests/integration/test_cloud_trace_export.py, tests/integration/test_agent_observability.py | sre platform |
| scalability and concurrency | race conditions and session consistency regressions | tests/unit/test_spanner_client.py, tests/unit/test_memory_api.py | tests/unit/test_governance_adapter.py | tests/integration/test_concurrent_writes.py, tests/integration/test_agent_concurrency.py, tests/integration/test_org_wide_scale.py, tests/integration/test_org_wide_mode.py | platform runtime |

## Freeze Policy

Effective immediately, creation of non-canonical tests is frozen.

A test is mergeable only when all conditions are met:
- It maps to one row in this matrix.
- It names the capability and the target layer in the test docstring.
- It does not duplicate behavior already covered by the row canonical suite.
- If it replaces an older test, the old test is retired in the same pull request.

## Review Workflow

- Quarterly: review owners and risks for each row.
- Sprintly: review governance inventory and reclassification candidates.
- Before release: verify there are no unapproved governance violations.
