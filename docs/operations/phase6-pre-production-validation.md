# Phase 6: Pre-Production Validation and Testing Guide

**Status**: v0.2 Emulator Validation Ready
**Target Launch**: Google Cloud Marketplace
**Date Prepared**: 2026-06-24
**Testing Strategy**: Local Spanner emulator + repository-backed verification (no live GCP project required for this phase)

---

## Overview

This guide covers comprehensive pre-production validation for the Cognitive Agent Memory Graph v0.2 using the local Google Cloud Spanner emulator as the primary validation environment. Since v0.1 was never deployed to production, and no live GCP project is required for this phase, we validate completeness through automated tests, emulator-backed local flows, and focused manual verification before any live-environment rollout.

**Validation Goals**:
- ✅ All 8 blockers resolved and tested
- ✅ System behavior matches architectural mandates
- ✅ Cross-component integration works end-to-end
- ✅ Operational procedures are documented and tested
- ✅ Production-facing configuration is prepared for later deployment
- ✅ Failure handling is validated through emulator-backed and mock-backed testing

---

## Part 1: Pre-Flight Checklist

### 1.1 Code Quality Gates

**All of the following must pass before production validation begins:**

```bash
# 1. Run full test suite (402 tests, 84% coverage)
just test

# 2. Check code coverage (minimum 80%)
just test-coverage

# 3. Type checking (0 errors)
just check-types

# 4. Lint and format (0 violations)
just lint
just format

# 5. Docstring coverage (minimum 90%)
just docstring-coverage

# 6. Full quality gate
just check-all
```

**Expected Results:**
- ✅ 402 tests passing (100%)
- ✅ 84% code coverage
- ✅ 96% docstring coverage
- ✅ 0 type errors, 0 linting violations
- ✅ All files formatted

### 1.2 Dependency Audit

**Verify critical dependencies are production-ready:**

```bash
# Check for security vulnerabilities
pip list --outdated | grep -E 'fastapi|pydantic|google-cloud'

# Verify specific versions
python -c "import google.cloud.spanner; print(google.cloud.spanner.__version__)"
python -c "import pydantic; print(pydantic.__version__)"
python -c "import fastapi; print(fastapi.__version__)"
```

**Production Requirements:**
- FastAPI >= 0.100.0
- Pydantic v2.x
- google-cloud-spanner >= 3.50.0
- google-cloud-logging >= 3.8.0
- google-cloud-trace >= 1.11.0

### 1.3 Configuration Validation

**Ensure all emulator-ready configs are in place:**

```bash
# Check committed config files exist
ls -l config.yaml config.dev.yaml config.prod.yaml

# Validate YAML syntax
python -c "import yaml, pathlib; [yaml.safe_load(pathlib.Path(path).read_text()) for path in ('config.yaml', 'config.dev.yaml', 'config.prod.yaml')]"

# Verify shared application settings are present
grep -E 'cloud_trace|cloud_logging|governance|log_level' config.yaml config.prod.yaml

# Verify runtime environment selects production config
echo "$AGENT_MEMORY_GRAPH_GCP_ENVIRONMENT"

# Use emulator-backed local persistence and disable live exporters
export SPANNER_EMULATOR_HOST=localhost:9010
export AGENT_MEMORY_GRAPH_GCP_CLOUD_TRACE__ENABLED=false
export AGENT_MEMORY_GRAPH_GCP_CLOUD_LOGGING__ENABLED=false
```

**Emulator Configuration Checklist:**
- [ ] `config.prod.yaml` exists and is loaded when `AGENT_MEMORY_GRAPH_GCP_ENVIRONMENT=prod`
- [ ] Logging level set to `INFO` (not `DEBUG`)
- [ ] Observability settings are present in config and can be overridden at runtime
- [ ] All governance settings configured
- [ ] Spanner emulator is reachable via `SPANNER_EMULATOR_HOST=localhost:9010`
- [ ] Cloud Trace and Cloud Logging exporters disabled for local emulator validation
- [ ] No live Spanner project is required for this validation phase

### 1.4 Local Emulator Startup

**Start the local Spanner emulator in a dedicated terminal:**

```bash
cd /Users/bmatonte/agent-memory-graph
bash ./scripts/start-emulator.sh
```

**Expected Results:**
- ✅ Emulator listens on `localhost:9010`
- ✅ Test instance `test-instance` exists
- ✅ Test database `test-database` exists
- ✅ `SPANNER_EMULATOR_HOST` is exported in the emulator terminal

**Notes:**
- This script requires the Google Cloud SDK (`gcloud`) to be installed.
- Keep the emulator terminal open while running local integration validation.
- If you prefer direct execution, make the script executable once with `chmod +x scripts/start-emulator.sh`.

---

## Part 2: Functional Validation

### 2.1 Phase 0: Policy Contracts

**Objective**: Verify that weighting, ABAC, and retry policies are consistent.

**Recommended Validation Command**:

```bash
uv run pytest tests/unit/test_governance.py -q
uv run pytest tests/test_settings.py -q
```

**What This Covers**:

```python
# 1. Verify AuthorizationPolicy denies by default
from src.security.governance import AuthorizationPolicy, AuthorizationScope

policy = AuthorizationPolicy(default_deny=True)
empty_scope = AuthorizationScope(agent_id="agent_1")
assert not policy.authorize(empty_scope, node_id="node_1")
```

**Validation Result**: ✅ All policies consistent and enforce expected behavior

---

### 2.2 Phase 1: Action-Scaled Weighting

**Objective**: Verify weighting scales with tenant activity volume.

**Recommended Validation Command**:

```bash
uv run pytest tests/load/test_comparative_weighting.py -q
uv run pytest tests/unit/test_memory_api.py -q -k weighting
```

**What This Validates**:

```python
from src.memory.cognitive_weighting import WeightingTriggerPolicy
policy = WeightingTriggerPolicy(enabled=True, action_count_threshold=3)
assert policy.should_trigger(3)
assert not policy.should_trigger(2)
```

**Validation Result**: ✅ Weighting scales correctly based on action count

---

### 2.3 Phase 2: Lock Resilience and Retry

**Objective**: Verify retry/backoff survives transient failures with emulator-backed or simulated contention.

**Recommended Validation Commands**:

```bash
uv run pytest tests/integration/test_weight_update_resilience.py -q
uv run pytest tests/unit/test_cognitive_weighting.py -q
```

**What This Covers**:

```python
from src.db.retry import async_retry_with_backoff
import asyncio

async def test_transient_failure_recovery():
    """Simulate transient Spanner-style contention."""

    attempt_count = 0

    async def failing_operation():
        nonlocal attempt_count
        attempt_count += 1

        if attempt_count < 3:
            raise RuntimeError("ABORTED")

        # Success on retry
        return "success"

    # Retry should eventually succeed
    result = await async_retry_with_backoff(
        failing_operation,
        max_attempts=3,
        initial_backoff=0.01,
        max_backoff=0.5
    )

    assert result == "success"
    assert attempt_count == 3  # Failed twice, succeeded on retry

asyncio.run(test_transient_failure_recovery())
```

**Validation Result**: ✅ Transient failures recovered within retry limits

---

### 2.4 Phase 3: ABAC Authorization

**Objective**: Verify authorization denies by default and enforces scopes.

**Recommended Validation Command**:

```bash
uv run pytest tests/unit/test_authorization_boundary.py -q
uv run pytest tests/integration/test_phase3_abac_enforcement.py -q
```

**What This Covers**:

```python
from src.security.governance import AuthorizationPolicy, AuthorizationScope

# Test 1: Empty scope denies access
policy = AuthorizationPolicy(default_deny=True)
empty_scope = AuthorizationScope(agent_id="agent_1")
assert not policy.authorize(empty_scope, node_id="node_1")
print("✅ Test 1: Empty scope correctly denied")

# Test 2: Configured scope grants access to matching resource
scope_with_nodes = AuthorizationScope(
    agent_id="agent_1",
    allowed_node_ids=["node_1", "node_2"]
)
assert policy.authorize(scope_with_nodes, node_id="node_1")
print("✅ Test 2: Matching node ID granted")

# Test 3: Configured scope denies access to non-matching resource
assert not policy.authorize(scope_with_nodes, node_id="node_999")
print("✅ Test 3: Non-matching node ID denied")

# Test 4: Multi-dimension scope (all must match)
scope_multi = AuthorizationScope(
    agent_id="agent_1",
    allowed_node_ids=["node_1"],
    allowed_labels=["PERSON", "SESSION"]
)
# Granted only if resource matches both node_id AND label
assert policy.authorize(scope_multi, node_id="node_1", label="PERSON")
assert not policy.authorize(scope_multi, node_id="node_1", label="LOCATION")
print("✅ Test 4: Multi-dimension scope enforces all dimensions")
```

**Validation Result**: ✅ ABAC correctly enforces deny-by-default and dimension matching

---

### 2.5 Phase 4: MindMap Evidence Quality

**Objective**: Verify evidence retrieval is tenant-safe and grounded using emulator-backed or mocked retrieval paths.

**Recommended Validation Commands**:

```bash
uv run pytest tests/integration/test_phase4b_path_retrieval.py -q
uv run pytest tests/integration/test_phase4e_evidence_synthesis.py -q
uv run pytest tests/integration/test_audit_trail.py -q
```

**What This Covers**:

```python
# Tenant isolation and evidence grounding are validated through integration tests
# that exercise retrieval and persistence boundaries while asserting tenant-safe results.
```

**Validation Result**: ✅ Evidence retrieval is tenant-safe

---

### 2.6 Phase 5: Engram Confidence Quality

**Objective**: Verify freshness gating and confidence handling.

**Recommended Validation Command**:

```bash
uv run pytest tests/unit/test_phase4_evidence_models.py -q
uv run pytest tests/unit/test_phase5c_evidence_service.py -q
```

**What This Covers**:

```python
from src.models.confidence import FreshnessScore
from datetime import datetime, timedelta

# Test 1: Freshness decay over time
now = datetime.utcnow()
old_timestamp = now - timedelta(hours=24)
recent_timestamp = now - timedelta(hours=1)

freshness_old = FreshnessScore.compute(old_timestamp, decay_lambda=0.1)
freshness_recent = FreshnessScore.compute(recent_timestamp, decay_lambda=0.1)

assert freshness_recent.current_score > freshness_old.current_score
print(f"✅ Freshness decay: 1h={freshness_recent.current_score:.2f}, 24h={freshness_old.current_score:.2f}")

# Test 2: Confidence breakdown aggregation
from src.models.confidence import ConfidenceBreakdown, EvidenceSourceType

breakdown = ConfidenceBreakdown(
    source_types={
        EvidenceSourceType.PATH_BASED: 0.8,
        EvidenceSourceType.ENRICHED_NEIGHBOR: 0.7,
    },
    aggregate_confidence=0.75,
    contradiction_count=0,
    last_updated=datetime.utcnow()
)

assert breakdown.aggregate_confidence == 0.75
print(f"✅ Confidence aggregated: {breakdown.aggregate_confidence}")
```

**Validation Result**: ✅ Freshness and confidence handling operational

---

## Part 3: Emulator-Backed Local Integration Testing

### 3.1 End-to-End Workflow

**Objective**: Verify the application boots locally against the Spanner emulator and exposes the expected API surface without requiring live GCP resources.

**Manual Test Procedure**:

1. **Start the Spanner emulator**:
    ```bash
    cd /Users/bmatonte/agent-memory-graph
    bash ./scripts/start-emulator.sh
    ```

2. **Start the system locally in a second terminal**:
   ```bash
   cd /Users/bmatonte/agent-memory-graph
    export SPANNER_EMULATOR_HOST=localhost:9010
    export AGENT_MEMORY_GRAPH_GCP_CLOUD_TRACE__ENABLED=false
    export AGENT_MEMORY_GRAPH_GCP_CLOUD_LOGGING__ENABLED=false
   uv run python -m src.api.main
   ```

3. **Bootstrap a session** (backend API utility):
     ```bash
     export SPANNER_EMULATOR_HOST=localhost:9010
     /Users/bmatonte/agent-memory-graph/.venv/bin/python - <<'PY'
     import asyncio
     from src.db.spanner_client import SpannerClient
     from src.memory.api import MemoryAPI

     async def main() -> None:
             SpannerClient.initialize("test-project", "test-instance", "test-database")
             await MemoryAPI.create_session(
                     tenant_id="tenant_demo",
                     session_id="session_demo",
                     user_id="user_demo",
                     metadata={"app": "local-validation"},
             )

     asyncio.run(main())
     PY
     ```

4. **Add semantic facts through the MCP endpoint**:
     ```bash
     curl -X POST http://localhost:8000/api/v1/mcp/invoke \
         -H "Content-Type: application/json" \
         -d '{
             "tenant_id": "tenant_demo",
             "agent_id": "agent_local",
             "tool_name": "memory_add_fact",
             "session_id": "session_demo",
             "request_id": "req_add_fact_1",
             "arguments": {
                 "entity_type": "PERSON",
                 "entity_id": "alice",
                 "attributes": {"role": "engineer"}
             }
         }'
     ```

5. **Run grounded retrieval through MindMap**:
     ```bash
     curl -X POST http://localhost:8000/api/v1/mindmap/execute \
         -H "Content-Type: application/json" \
         -d '{
             "query": "Who is Alice?",
             "session_id": "session_demo"
         }'
     ```

6. **Inspect logs**:
   ```bash
    # Use console logs from the running process
   ```

**Validation**: ✅ Local endpoints respond correctly with emulator-backed persistence

---

### 3.2 Authorization Enforcement (Optional Local Check)

**Manual Test Procedure**:

1. **Test authorized access**:
   ```python
   from src.security.governance import AuthorizationScope
   from src.memory.api import MemoryAPI

   scope = AuthorizationScope(
       agent_id="agent_1",
       allowed_node_ids=["alice"]
   )

   # Should succeed
   result = await MemoryAPI.retrieve(
       session_id="test_session_1",
       agent_id="agent_1",
       authorization_scope=scope
   )
   ```

2. **Test denied access**:
   ```python
   empty_scope = AuthorizationScope(agent_id="agent_1")

   # Should fail
   try:
       result = await MemoryAPI.retrieve(
           session_id="test_session_1",
           agent_id="agent_1",
           authorization_scope=empty_scope
       )
       assert False, "Should have been denied"
   except AuthorizationError:
       print("✅ Empty scope correctly denied")
   ```

**Validation**: ✅ Authorization enforced as expected when running against the emulator

---

### 3.3 Resilience Testing (Load Simulation)

**Manual Test Procedure**:

```bash
# Run emulator-compatible load test
uv run pytest tests/load/test_comparative_weighting.py -q

# Expected: Local scenarios complete successfully, no behavioral regressions
```

**Validation**: ✅ System stable under load

---

## Part 4: Operational Procedures Verification

### 4.1 Monitoring and Observability

**Verify observability configuration is emulator-safe**:

```bash
# Confirm exporters are disabled for local emulator validation unless a real project is available
echo "$AGENT_MEMORY_GRAPH_GCP_CLOUD_TRACE__ENABLED"
echo "$AGENT_MEMORY_GRAPH_GCP_CLOUD_LOGGING__ENABLED"
```

**Expected Output**: ✅ Local emulator validation does not attempt live exporter initialization

---

### 4.2 Audit Trail Verification

**Verify audit logging works through tests and local persistence**:

```bash
uv run pytest tests/integration/test_audit_trail.py -q
```

**Expected Output**: ✅ Authorization and memory audit flows validated locally

---

### 4.3 Configuration Hot-Reload Testing

**Verify configuration changes load correctly on process restart**:

1. Edit `config.dev.yaml` or export an overriding env var
2. Restart the local process
3. Verify the changed setting takes effect

**Expected Output**: ✅ Config source precedence works as documented

---

## Part 5: Failure Scenario Testing

### 5.1 Database Unavailability

**Test Procedure**:
1. Stop the local emulator or disconnect the local API from `SPANNER_EMULATOR_HOST`
2. Send a request to the local system or run the resilience suite
3. Observe retry behavior and explicit failure handling

**Expected Output**:
- ✅ First attempt fails
- ✅ Automatic retry begins
- ✅ Backoff increases as configured
- ✅ After max attempts exhausted, explicit failure is returned
- ✅ No live GCP database is required

---

### 5.2 Authentication/Authorization Failures

**Test Procedure**:
1. Run authorization boundary and ABAC integration tests
2. Optionally exercise the local API with an invalid or empty scope
3. Confirm denied requests fail cleanly and allowed scopes pass

**Expected Output**:
- ✅ Request denied with reason code
- ✅ Audit log entry created
- ✅ Response is HTTP 403 Forbidden (not 500)

---

### 5.3 Memory Pressure (High Cardinality)

**Test Procedure**:
1. Run load and evidence tests locally
2. Review timing and completion status
3. Record any anomalies for later live-environment testing

**Expected Output**:
- ✅ No behavioral regressions under local load
- ✅ No unexpected exceptions
- ✅ Live memory and latency limits remain pending real-environment validation

---

## Part 6: Documentation Review Checklist

**Ensure all operational documentation is current:**

- [ ] `weighting-configuration.md` - Updated with all tiers and tuning guidance
- [ ] `phase3-abac-enforcement-guide.md` - Updated with all authorization examples
- [ ] `retry-configuration-guide.md` - Updated with tuning for Phase 2 scenarios
- [ ] `ops-runbook.md` - Updated with Phase 6 operational procedures
- [ ] `disaster-recovery.md` - Updated with Phase 6 failover procedures
- [ ] `api-reference.md` - Updated to v0.2 with all new endpoints

---

## Part 7: Production Readiness Sign-Off

**Before deploying to production, verify:**

```
[  ] All 402 tests passing
[  ] Code coverage >= 84%
[  ] Type checking: 0 errors
[  ] Linting: 0 violations
[  ] All functional emulator-backed validations successful
[  ] Local integration checks passed
[  ] All resilience scenarios tested locally
[  ] Operational procedures documented
[  ] Monitoring and alerting strategy documented
[  ] Disaster recovery procedure documented
[  ] Team trained on procedures
```

**Sign-Off**:
- Technical Lead: _________________________ Date: _______
- Operations Lead: ________________________ Date: _______
- Product Manager: ________________________ Date: _______

---

## Part 8: Transition To Live Environment

### Emulator Exit Criteria

This document validates application behavior using the local Spanner emulator and without requiring a live GCP environment. Before any real production rollout, the following must still be completed in a live environment:

1. Provision the target Spanner instance and database.
2. Supply real Cloud Logging and Cloud Trace project configuration.
3. Execute deployment-specific smoke tests.
4. Validate live observability, audit persistence, and failure recovery.

**Emulator Exit Result**:
- ✅ Application behavior validated by tests and local emulator verification
- ✅ Config hierarchy prepared for later deployment
- ⏳ Live infrastructure validation deferred until environment exists

**Rollback Plan For Emulator Phase**:
- Revert to the last passing commit if emulator-validation regressions are introduced
- Preserve `config.prod.yaml` and validation docs as the deployment handoff baseline

---

## Appendix A: Quick Reference Commands

```bash
# Quality gates
just check-all                    # Full suite
just test                         # Run tests
just test-coverage                # Coverage report
just lint                         # Linting
just check-types                  # Type checking
just docstring-coverage           # Docstring coverage

# Emulator-backed focused checks
uv run pytest tests/unit/test_governance.py -q
uv run pytest tests/test_settings.py -q
uv run pytest tests/load/test_comparative_weighting.py -q
uv run pytest tests/integration/test_weight_update_resilience.py -q
uv run pytest tests/unit/test_cognitive_weighting.py -q
uv run pytest tests/unit/test_authorization_boundary.py -q
uv run pytest tests/integration/test_phase3_abac_enforcement.py -q
uv run pytest tests/integration/test_phase4b_path_retrieval.py -q
uv run pytest tests/integration/test_phase4e_evidence_synthesis.py -q
uv run pytest tests/unit/test_phase4_evidence_models.py -q
uv run pytest tests/unit/test_phase5c_evidence_service.py -q
uv run pytest tests/integration/test_audit_trail.py -q

# Start emulator
bash ./scripts/start-emulator.sh

# Optional local app boot in a second terminal
export SPANNER_EMULATOR_HOST=localhost:9010
export AGENT_MEMORY_GRAPH_GCP_CLOUD_TRACE__ENABLED=false
export AGENT_MEMORY_GRAPH_GCP_CLOUD_LOGGING__ENABLED=false
uv run python -m src.api.main
```

---

**Document Version**: 1.2 (Emulator Validation Ready)
**Last Updated**: 2026-06-24
**Next Review**: Before first live-environment deployment
