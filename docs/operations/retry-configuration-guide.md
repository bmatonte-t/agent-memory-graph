# Phase 2 Lock Resilience: Retry Configuration Guide

## Overview

This guide covers configuring the Phase 2 retry infrastructure for resilient Spanner operations in the Cognitive Agent Memory Graph. The retry system automatically handles transient failures (database locks, resource exhaustion, timeouts) while preserving data integrity through idempotency management.

## Quick Start

The default retry policy is already configured and enabled:

```yaml
# config.yaml
governance:
  retry:
    max_attempts: 3                    # Total retry attempts
    initial_backoff_seconds: 0.25      # First retry waits 250ms
    max_backoff_seconds: 5.0           # Cap on backoff duration
```

No configuration is required for basic functionality.

## Retry Policy Configuration

### Configuration Schema

```yaml
governance:
  retry:
    max_attempts: int              # Default: 3 (inclusive; includes first attempt)
    initial_backoff_seconds: float # Default: 0.25 (seconds)
    max_backoff_seconds: float     # Default: 5.0 (seconds)
```

### Parameter Tuning

| Parameter | Default | Range | Notes |
|-----------|---------|-------|-------|
| `max_attempts` | 3 | 1-10 | More attempts = longer potential latency, but better recovery. 3 is optimal for most workloads. |
| `initial_backoff_seconds` | 0.25 | 0.01-1.0 | Increase for high-contention workloads. Decrease for interactive latency-sensitive paths. |
| `max_backoff_seconds` | 5.0 | 1.0-30.0 | Prevent retry storms during sustained outages. 5s balances recovery and responsiveness. |

### Tuning Strategy

**For High-Throughput Batch Operations** (Dataform, ETL):
```yaml
governance:
  retry:
    max_attempts: 5                # More retries (batch can absorb latency)
    initial_backoff_seconds: 1.0   # Start with longer backoff
    max_backoff_seconds: 30.0      # Allow extended backoff for data center recovery
```

**For Interactive Workloads** (API endpoints):
```yaml
governance:
  retry:
    max_attempts: 2                # Fast fail if retry needed
    initial_backoff_seconds: 0.1   # Keep latency low
    max_backoff_seconds: 1.0       # Short max to preserve UX
```

**For Development/Testing**:
```yaml
governance:
  retry:
    max_attempts: 1                # Disable retries, fail fast
    initial_backoff_seconds: 0.01
    max_backoff_seconds: 0.01
```

## Transient Error Classification

The retry system automatically retries these Spanner error codes:

| Error Code | Cause | User Action |
|-----------|-------|-----|
| `ABORTED` (10) | Transaction conflict or row lock | Automatic retry (transient) |
| `RESOURCE_EXHAUSTED` (8) | Database busy, connection limits | Automatic retry (transient) |
| `DEADLINE_EXCEEDED` (4) | Request timeout | Automatic retry (may be transient) |
| `INTERNAL` with "deadline"/"timeout" | gRPC timeout | Automatic retry (selective) |

### Non-Transient Errors (Fail Immediately)

These errors are NOT retried:
- `PERMISSION_DENIED` - Authorization issue (fix credentials)
- `INVALID_ARGUMENT` - Bad request (fix SQL or params)
- `NOT_FOUND` - Table/database missing (check schema)
- `ALREADY_EXISTS` - Duplicate key (check business logic)
- `INTERNAL` without timeout mention - Real backend error

## Backoff Algorithm

The retry system uses **exponential backoff with jitter**:

```
backoff_seconds = min(
    initial * (2 ^ attempt) + random(0, 1),
    max_backoff_seconds
)
```

### Example Timeline (Default Config)

| Attempt | Base Backoff | Jitter | Final Wait | Cumulative |
|---------|--------------|--------|-----------|-----------|
| 1 | 0.25 * 2^0 = 0.25 | +0-1ms | 0.25-1.25s | 0.25-1.25s |
| 2 | 0.25 * 2^1 = 0.50 | +0-1ms | 0.50-1.50s | 0.75-2.75s |
| 3 | 0.25 * 2^2 = 1.00 | +0-1ms | 1.00-2.00s | 1.75-4.75s |
| *Final* | *Capped* | — | *5.00s max* | *Max 9.75s total* |

Jitter prevents thundering herd when multiple operations retry simultaneously.

## Idempotency Management

The retry system maintains idempotency through **contextvars-based key tracking**:

1. Operation begins → generates unique UUID key
2. Key stored in thread-local context (no database)
3. Batch operations execute within context
4. On retry → same context is reused (deduplication)
5. Operation completes → context cleaned up

### Benefits

- **No duplicate writes**: Retried operations don't create duplicate nodes/edges
- **No database persistence**: Keys are scoped to operation execution
- **Thread-safe**: Uses contextvars for async isolation
- **Zero overhead**: No additional database round trips

## Monitoring and Observability

### Log Entries

The retry system emits these log entries:

```
# Successful first attempt
[DEBUG] Add semantic fact tenant_id=tenant_123 entity_id=person_456

# Retry attempt logged
[INFO] write_retry_attempt tenant_id=tenant_123 attempt=1 max_attempts=3 \
       backoff_seconds=0.631 error=StatusCode.ABORTED

# After max retries exhausted
[ERROR] operation_failed tenant_id=tenant_123 attempt=3 max_attempts=3 \
        is_retryable=False error=StatusCode.ABORTED

# Weight update failure (non-retryable)
[ERROR] WeightUpdateFailedError: failed to update weights for 3 nodes after 3 attempts
```

### Metrics to Track

Add these metrics to your observability platform:

```python
# In src/observability/metrics.py (future)
write_retry_attempt = Counter(
    "memory_write_retry_attempt",
    "Total retry attempts",
    ["tenant_id", "operation", "error_code"],
)

write_retry_success = Counter(
    "memory_write_retry_success",
    "Successful retries",
    ["tenant_id", "operation", "attempt_number"],
)

write_retry_exhausted = Counter(
    "memory_write_retry_exhausted",
    "Retries exhausted",
    ["tenant_id", "operation", "error_code"],
)

weight_update_failure = Counter(
    "memory_weight_update_failure",
    "Weight update failures",
    ["tenant_id", "reason"],
)
```

### Key Queries

**Find retry patterns in your logs** (BigQuery):
```sql
SELECT
  REGEXP_EXTRACT(message, r'tenant_id=(\w+)') as tenant_id,
  REGEXP_EXTRACT(message, r'error=(\w+)') as error_code,
  COUNT(*) as retry_count,
  TIMESTAMP_TRUNC(timestamp, HOUR) as hour
FROM `project.dataset.logs`
WHERE message LIKE 'write_retry_attempt%'
GROUP BY 1, 2, 4
ORDER BY retry_count DESC;
```

**Identify high-contention operations**:
```sql
SELECT
  REGEXP_EXTRACT(message, r'tenant_id=(\w+)') as tenant_id,
  MAX(CAST(
    REGEXP_EXTRACT(message, r'attempt=(\d+)') AS INT64
  )) as max_attempt_reached,
  COUNT(*) as total_attempts
FROM `project.dataset.logs`
WHERE message LIKE '%write_retry%'
GROUP BY 1
HAVING max_attempt_reached >= 2
ORDER BY total_attempts DESC;
```

## Troubleshooting

### High Retry Rates

**Symptom**: Logs show frequent `write_retry_attempt` entries

**Diagnosis**:
1. Check database CPU and connection count: `SELECT * FROM INFORMATION_SCHEMA.SESSIONS`
2. Review for hot rows: Large updates to popular nodes may cause locks
3. Check network latency between application and Spanner

**Solutions**:
- Increase `initial_backoff_seconds` to 0.5-1.0
- Increase `max_backoff_seconds` to 10.0-30.0
- Scale up Spanner compute units
- Review transaction duration; break into smaller batches

### Retries Exhausted (Recurring)

**Symptom**: `operation_failed tenant_id=X attempt=3` appears regularly

**Diagnosis**:
1. Check if error is transient: Look for error code in log
2. If `PERMISSION_DENIED` → credentials issue
3. If `INVALID_ARGUMENT` → SQL or parameter error
4. If `ABORTED` recurring → contention or timeout

**Solutions**:
- If transient: Increase `max_attempts` to 4-5
- If non-transient: Fix underlying issue (schema, permissions, timeout)
- Consider operation batching to reduce lock time

### Weight Update Failures

**Symptom**: `WeightUpdateFailedError: failed to update weights` in logs

**Diagnosis**:
1. Weight updates are always retried with full retry policy
2. If still failing after retries, it's a persistent issue
3. Check if node_ids exist: `SELECT COUNT(*) FROM MemoryNode WHERE NodeId IN (...)`

**Solutions**:
- Verify node exists before calling `_update_weight_on_successful_use()`
- Check tenant isolation: Ensure tenant_id filter is applied
- Verify Spanner table permissions

## Deployment Checklist

- [ ] Retry policy configured in `config.yaml` for your environment
- [ ] Backoff thresholds appropriate for your workload (see tuning section)
- [ ] Observability platform configured to receive log events
- [ ] BigQuery log retention set to 30+ days (for trend analysis)
- [ ] Alert configured for `operation_failed` error rate > threshold
- [ ] Team trained on retry behavior and idempotency guarantees
- [ ] Performance baseline established (e.g., p99 latency without retries)
- [ ] Runbook created for "High Retry Rates" scenario

## Phase 2 Integration Checklist

- [x] Retry infrastructure implemented in `src/db/retry.py`
- [x] Idempotency context added to `add_semantic_fact()` and `create_session()`
- [x] Weight update resilience integrated into `_update_weight_on_successful_use()`
- [x] Integration tests created for concurrent writes and retry scenarios
- [ ] Observability metrics integrated (Phase 3)
- [ ] Production monitoring dashboards configured (Phase 3)
- [ ] Runbooks created for operational support (Phase 3)

## Further Reading

- [Google Cloud Spanner: Error Handling](https://cloud.google.com/spanner/docs/errors)
- [Exponential Backoff Best Practices](https://cloud.google.com/documentation/solutions/retries)
- [Idempotency in Distributed Systems](https://en.wikipedia.org/wiki/Idempotence)

---

**Last Updated**: 2026-06-22  
**Maintainer**: Agent Memory Graph Team  
**Phase**: 2 (Lock Resilience)
