# Phase 2 Lock Resilience: Staging & Production Rollout Strategy

## Executive Summary

Phase 2 introduces automatic retry/backoff logic and idempotency guarantees to handle transient Spanner failures. This document outlines the staged rollout approach to validate these changes in production-like environments before full deployment.

**Rollout Timeline**: 2 weeks (staging validation + production stages)

**Risk Level**: Low (retry logic is additive; no breaking API changes)

**Rollback Plan**: 1-click disable via retry policy config

---

## Pre-Rollout Validation (Week 1)

### Stage 0: Development Verification

**Duration**: Ongoing (completed before staging)
**Scope**: Local machines, CI/CD tests

**Deliverables**:
- ✅ All unit tests passing (11/11 memory API tests)
- ✅ All integration tests passing (8/8 weight tests)
- ✅ New tests for concurrent writes (test_concurrent_writes.py)
- ✅ New tests for retry resilience (test_weight_update_resilience.py)
- ✅ New tests for idempotency (test_idempotency.py)
- ✅ Code review completed (lint, type checks, docstrings)

**Gate**: Code merged to `develop` branch ✅

### Stage 1: Staging Environment Validation

**Duration**: 5 business days
**Scope**: Staging GCP project with production-like data volume

**Configuration**:
```yaml
# staging-config.yaml
governance:
  retry:
    enabled: true
    max_attempts: 3
    initial_backoff_seconds: 0.25
    max_backoff_seconds: 5.0
```

**Test Plan**:

1. **Load Test** (2 hours)
   - Run 100 concurrent semantic fact additions
   - Run 50 concurrent weight updates
   - Target: 0% error rate, observe retry rates
   - Success Criteria: `write_retry_attempt` log rate < 5%

2. **Contention Stress Test** (1 hour)
   - 10 concurrent operations on same parent node (relationship creation)
   - Target: No duplicate edges created
   - Success Criteria: Edge count == expected (no duplicates)

3. **Transient Failure Injection** (1 hour)
   - Mock Spanner to return ABORTED on 20% of operations
   - Verify automatic retry and eventual success
   - Success Criteria: All operations succeed after retry

4. **Long-Running Stability** (24+ hours)
   - Continuous semantic fact ingestion (1 QPS)
   - Continuous weight updates (0.5 QPS)
   - Monitor for error escalation or retry loops
   - Success Criteria: No operational errors, stable retry rate

5. **Idempotency Verification**
   - Simulate operation retry by manually re-running same fact creation
   - Verify idempotency key prevents duplicate node creation
   - Success Criteria: Same idempotency key → no duplicate writes

**Observability Setup**:
```yaml
# Cloud Logging
log_filter: |
  resource.type="cloud_run"
  resource.labels.service_name="agent-memory-graph"
  (
    severity="ERROR" OR
    message LIKE "write_retry_attempt%" OR
    message LIKE "operation_failed%"
  )

# BigQuery Log Export (30-day retention)
destination: projects/staging-project/datasets/logs/table

# Create alerts
- Alert: retry_rate > 10% within 5-minute window
- Alert: operation_failed count > 5 within 1-hour window
```

**Pass/Fail Criteria**:
- ✅ All tests pass with observed metrics
- ✅ No error rate increase vs. baseline
- ✅ Retry rate < 5% on normal workload
- ✅ No duplicate data detected
- ✅ All idempotency tests pass

**Go/No-Go Decision**: Team review of staging results

---

## Production Rollout (Week 2)

### Stage 2: Canary Release (Day 8-10)

**Scope**: 5% of production traffic (e.g., one GCP region or tenant shard)

**Configuration**:
```yaml
# production-canary-config.yaml (same as final, with canary flags)
governance:
  retry:
    enabled: true
    max_attempts: 3
    initial_backoff_seconds: 0.25
    max_backoff_seconds: 5.0

  # Feature flag for gradual rollout
  phase2_lock_resilience:
    enabled: true
    canary_percentage: 5  # 5% of operations
```

**Monitoring**:
- Dashboard: Memory API retry metrics by tenant
- Alerts: Error rate, latency, retry rate
- SLO tracking: p99 latency should not increase > 100ms

**Expected Baseline** (no retries):
- Add semantic fact: p99 ~50ms
- Weight update: p99 ~30ms
- With retries (worst case): p99 ~5s (cap via max_backoff_seconds)

**Metrics to Watch**:
```
memory_write_retry_attempt_total
memory_write_retry_success_total
memory_operation_duration_seconds (p99)
weight_update_failure_total
```

**Rollback Trigger**:
- Error rate increase > 20%
- p99 latency increase > 200ms
- `WeightUpdateFailedError` rate > 1%
- Any production incident related to retries

**Rollback Action**:
```yaml
# Set canary_percentage to 0 (disable for all)
governance:
  phase2_lock_resilience:
    canary_percentage: 0
    enabled: false
```

### Stage 3: Expanded Release (Day 11-12)

**Scope**: 50% of production traffic

**Configuration**:
```yaml
governance:
  phase2_lock_resilience:
    canary_percentage: 50
```

**Validation** (Same as canary, but observe at 50% scale):
- Error rate stable
- Retry rate < 5%
- Latency p99 acceptable
- No unintended duplicates in semantic graph

**Go/No-Go Decision**: On-call engineer review

### Stage 4: Full Production Release (Day 13)

**Scope**: 100% of production traffic

**Configuration**:
```yaml
governance:
  phase2_lock_resilience:
    canary_percentage: 100
    enabled: true
```

**Post-Release Validation** (First 24 hours):
- Continuous monitoring of metrics
- On-call team watching for anomalies
- Ready to rollback if issues detected

---

## Rollback Procedure

**Decision to Rollback**: Any Go/No-Go gate fails OR production incident detected

**Immediate Actions** (< 5 minutes):
1. Set `phase2_lock_resilience.enabled = false` in config
2. Restart Cloud Run service (or auto-update triggers)
3. Verify error rates return to baseline
4. Notify team channel

**Root Cause Analysis** (within 24 hours):
1. Collect logs from staging/canary
2. Review retry patterns and error codes
3. Identify code or configuration issue
4. Fix and re-test in staging

**Retry After Fix**:
1. Code fix → merge to `develop`
2. Re-run staging tests (Stage 1)
3. Re-attempt canary release (Stage 2)

---

## Operational Runbooks

### Runbook 1: High Retry Rate Detected

**Trigger**: Alert fires when `write_retry_attempt` > 50 in 5-minute window

**Detection**:
```sql
SELECT
  TIMESTAMP_TRUNC(timestamp, MINUTE) as minute,
  COUNT(*) as retry_attempts
FROM `project.dataset.logs`
WHERE message LIKE 'write_retry_attempt%'
GROUP BY 1
ORDER BY 1 DESC
LIMIT 5;
```

**Response**:
1. ⏱️ Determine scope: Single tenant? All? Single region?
2. 🔍 Check Spanner metrics: CPU%, connections, active sessions
3. 🔍 Check application metrics: QPS, error rate, latency
4. 📊 Compare with baseline (use historical alerts as reference)

**Actions**:
- **If CPU > 80%**: Scale up Spanner compute units
- **If connections > 90% limit**: Check for connection leaks (scale up app)
- **If operation_failed errors**: Check error codes, may need rollback
- **If expected (maintenance window)**: Monitor duration, expect recovery

### Runbook 2: Weight Update Failures

**Trigger**: `WeightUpdateFailedError` in logs or alert fires

**Detection**:
```sql
SELECT
  timestamp,
  REGEXP_EXTRACT(message, r'failed to update weights for (\d+) nodes') as node_count,
  REGEXP_EXTRACT(message, r'after (\d+) attempts') as attempts,
  message
FROM `project.dataset.logs`
WHERE message LIKE 'WeightUpdateFailedError%'
ORDER BY timestamp DESC
LIMIT 20;
```

**Response**:
1. Confirm nodes exist: Check if MemoryNodes were actually created
   ```sql
   SELECT COUNT(*) FROM MemoryNode WHERE NodeId IN (...)
   ```
2. Check tenant isolation: Verify tenant_id filter is correct
3. Check permissions: Verify service account has UPDATE access

**Actions**:
- **If nodes missing**: Bug in `add_semantic_fact()` — investigate
- **If tenant isolation issue**: Configuration error — fix and redeploy
- **If permissions issue**: Update IAM role for service account
- **If persistent**: Rollback Phase 2 (disable retries)

### Runbook 3: Duplicate Semantic Facts Detected

**Trigger**: Manual review or data quality check finds duplicate nodes/edges

**Detection**:
```sql
SELECT
  NodeId,
  MemoryTier,
  COUNT(*) as count
FROM `project.dataset.MemoryNode`
WHERE MemoryTier = 'SEMANTIC'
GROUP BY 1, 2
HAVING count > 1;
```

**Response**:
1. 📅 Determine when duplicates were created (check CreatedAt)
2. 🔑 Check if same idempotency key was used (in logs)
3. 🔍 Investigate if idempotency context was active during creation

**Actions**:
- **If same idempotency key**: Idempotency is working (expected) — no action
- **If different keys**: Indicates missed deduplication — investigate code
- **If pattern**: May indicate retry was too aggressive — adjust backoff config

---

## Success Metrics (Phase 2 Complete)

**Primary Metrics**:
- ✅ Retry rate on transient errors < 5%
- ✅ Zero increase in error rate vs. baseline
- ✅ Weight update success rate > 99.9%
- ✅ No duplicate nodes/edges created by retries

**Operational Metrics**:
- ✅ Add semantic fact p99 latency: < 200ms (with retries)
- ✅ Weight update p99 latency: < 100ms (with retries)
- ✅ Observability metrics correctly tracked and alerting

**Team Confidence Metrics**:
- ✅ All tests passing (unit + integration + load)
- ✅ Zero issues in staging environment
- ✅ Canary release completes without incident
- ✅ Production release completes without incident

---

## Communication Plan

### Pre-Rollout (1 week before)
- **Announcement**: "Phase 2 retry infrastructure deploying next week"
- **Target**: Engineering + DevOps teams
- **Content**: Overview, what changes, monitoring expectations

### Day of Staging Release
- **Announcement**: "Phase 2 staging validation starting today"
- **Details**: Expected duration, monitoring requirements, escalation

### Day of Canary Release
- **Announcement**: "Phase 2 canary release: 5% of traffic"
- **Status Channel**: Live updates on canary metrics
- **Escalation**: Clear point of contact for on-call

### Day of Full Release
- **Announcement**: "Phase 2 100% production release complete"
- **Retrospective**: Lessons learned, metrics review (24 hours post)

---

## Decision Gates

| Gate | Owner | Pass Criteria |
|------|-------|---------------|
| **Stage 0: Dev Complete** | Engineering Lead | All tests passing, code reviewed |
| **Stage 1: Staging Validation** | QA + Engineering Lead | All validation tests pass, metrics acceptable |
| **Stage 2: Canary Go** | On-Call Engineer | Error rate < baseline + 5%, no manual rollback needed |
| **Stage 3: 50% Go** | On-Call Engineer | Same as canary, plus 24-hour stability |
| **Stage 4: 100% Release** | Engineering Lead | Same as 50%, plus retrospective complete |

---

## Configuration Files Reference

### Staging (`config.staging.yaml`)
```yaml
governance:
  retry:
    enabled: true
    max_attempts: 3
    initial_backoff_seconds: 0.25
    max_backoff_seconds: 5.0

  phase2_lock_resilience:
    enabled: true
    canary_percentage: 100  # 100% for staging
```

### Production — Canary (`config.prod-canary.yaml`)
```yaml
governance:
  retry:
    enabled: true
    max_attempts: 3
    initial_backoff_seconds: 0.25
    max_backoff_seconds: 5.0

  phase2_lock_resilience:
    enabled: true
    canary_percentage: 5  # 5% of traffic
```

### Production — Full (`config.prod.yaml`)
```yaml
governance:
  retry:
    enabled: true
    max_attempts: 3
    initial_backoff_seconds: 0.25
    max_backoff_seconds: 5.0

  phase2_lock_resilience:
    enabled: true
    canary_percentage: 100  # All traffic
```

---

## Appendix: Monitoring Queries

### Daily Retry Summary
```sql
SELECT
  CURRENT_DATE() as date,
  COUNT(*) as total_retries,
  COUNT(DISTINCT REGEXP_EXTRACT(message, r'tenant_id=(\w+)')) as affected_tenants,
  COUNTIF(message LIKE '%attempt=2%') as retries_on_2nd_attempt,
  COUNTIF(message LIKE '%attempt=3%') as retries_on_3rd_attempt
FROM `project.dataset.logs`
WHERE DATE(timestamp) = CURRENT_DATE()
  AND message LIKE 'write_retry_attempt%'
GROUP BY 1;
```

### Error Codes Requiring Retry
```sql
SELECT
  REGEXP_EXTRACT(message, r'error=(\w+)') as error_code,
  COUNT(*) as count,
  ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
FROM `project.dataset.logs`
WHERE message LIKE 'write_retry_attempt%'
GROUP BY 1
ORDER BY count DESC;
```

### Weight Update Failures
```sql
SELECT
  timestamp,
  REGEXP_EXTRACT(message, r'tenant_id=(\w+)') as tenant_id,
  REGEXP_EXTRACT(message, r'after (\d+) attempts') as attempts,
  message
FROM `project.dataset.logs`
WHERE message LIKE 'WeightUpdateFailedError%'
ORDER BY timestamp DESC;
```

---

**Approved By**: [Engineering Lead Name] | [Date]
**Last Updated**: 2026-06-22
**Next Review**: Post-production (1 month after release)
