"""Phase 2: Lock Resilience Design Specification

Goal: Make write paths robust under contention.

This design document outlines the approach for retry logic, idempotency,
failure visibility, and test strategy.
"""

# Phase 2: Lock Resilience - Design Specification

## 1. Problem Statement

Current memory write paths lack resilience under contention:
- Transient failures (e.g., Spanner lock contention) cause immediate failures
- No automatic retry with exponential backoff
- No idempotency keys, so retries risk duplicating effects
- Weight update failures are silent (best-effort)
- No visibility into contention or duplicate-request scenarios

## 2. Scope

### In Scope (Phase 2)
- Retry/backoff for transient write failures on MemoryAPI operations
- Idempotency keys for mutations (add_semantic_fact, _update_weight_on_successful_use)
- Explicit error handling and observability for weight-update failures
- Integration tests validating concurrent write recovery and no duplication

### Out of Scope (Future)
- Client-side retry logic (handled by orchestrator layer)
- Distributed tracing for cross-service resilience
- Persistent retry queue for durability
- Circuit breaker patterns (Phase 3+)

## 3. Design Decisions

### 3.1 Transient Error Classification

**Retryable Errors** (apply retry/backoff):
1. `ABORTED` (Spanner code 10) - Transaction conflict, safe to retry
2. `RESOURCE_EXHAUSTED` (Spanner code 8) - Database busy, safe to retry
3. `DEADLINE_EXCEEDED` (Spanner code 4) - Timeout, may be transient
4. `INTERNAL` (Spanner code 13) - Only if message contains "deadline" or "timeout"

**Non-Retryable Errors** (fail fast):
1. `NOT_FOUND` (Spanner code 5)
2. `PERMISSION_DENIED` (Spanner code 7)
3. `INVALID_ARGUMENT` (Spanner code 3)
4. `FAILED_PRECONDITION` (Spanner code 9)

**Configuration**:
```python
# Pulled from governance.RetryPolicy
max_attempts: int = 3
initial_backoff_seconds: float = 0.25
max_backoff_seconds: float = 5.0

# Backoff strategy: exponential with jitter
backoff(attempt: int) = min(
    initial_backoff_seconds * (2 ** attempt) + random(0, 1),
    max_backoff_seconds
)
```

### 3.2 Idempotency Strategy

**Approach**: Idempotency keys at the operation level, not the request level.

**Implementation**:
1. Generate UUID-based idempotency key for each write operation
2. Store in a temporary cache/context (NOT persisted to Spanner yet)
3. On retry: use the same idempotency key
4. If database returns same result for same idempotency key: assume success

**Scope**:
- `add_semantic_fact()`: One key per operation
- `_update_weight_on_successful_use()`: One key per batch
- `record_audit_event()`: One key per event (append-only, lower risk)

**Rationale**:
- Spanner lacks native idempotency support
- We cannot persistently track keys without adding overhead
- For Phase 2, we focus on within-transaction idempotency
- Future phases may add persistent tracking

### 3.3 Weight-Update Failure Handling

**Current Behavior** (Phase 1): Silent best-effort
- If update fails: log and continue
- No explicit error surfacing to caller

**Proposed Behavior** (Phase 2): Explicit with recovery
1. Attempt weight update with retry logic
2. If succeeds after retry: log success
3. If fails after max retries:
   - Log error with context (tenant_id, node_ids, attempt count)
   - Raise WeightUpdateFailed exception
   - Caller can decide: fail forward or suppress

**Error Handling**:
```python
class WeightUpdateFailed(Exception):
    """Weight update exhausted retries."""
    def __init__(
        self,
        tenant_id: str,
        node_ids: list[str],
        attempts: int,
        last_error: Exception,
    ):
        self.tenant_id = tenant_id
        self.node_ids = node_ids
        self.attempts = attempts
        self.last_error = last_error
```

### 3.4 Observability

**Metrics**:
1. `write_retry_attempt` (counter): tenant_id, operation, attempt_number
2. `write_retry_success` (counter): tenant_id, operation
3. `write_retry_exhausted` (counter): tenant_id, operation
4. `write_backoff_ms` (histogram): backoff duration per attempt

**Logging**:
1. Each retry attempt: INFO level with attempt number and delay
2. Retry exhausted: WARNING level with tenant/operation/attempts
3. Successful recovery: INFO level with total attempts

## 4. Implementation Plan

### Phase 2.1: Retry Infrastructure
1. Create `src/db/retry.py` with:
   - `is_transient_error(exception) -> bool`
   - `calculate_backoff(attempt: int) -> float`
   - `async_retry_with_backoff(func, max_attempts, backoff_calc) -> Any`
2. Integrate RetryPolicy from governance settings

### Phase 2.2: Idempotency Keys
1. Create `src/db/idempotency.py` with:
   - `generate_idempotency_key() -> str`
   - `IdempotencyContext` (thread-local or contextvars)
2. Thread through MemoryAPI operations

### Phase 2.3: Weight-Update Error Handling
1. Define `WeightUpdateFailed` exception
2. Wrap `_update_weight_on_successful_use()` with retry + explicit error handling
3. Audit events for failed weight updates

### Phase 2.4: Integration Tests
1. `tests/integration/test_concurrent_writes.py`:
   - Simulate concurrent adds to same node
   - Verify no duplicate edges created
   - Verify both complete successfully

2. `tests/integration/test_weight_update_resilience.py`:
   - Mock transient errors (ABORTED, RESOURCE_EXHAUSTED)
   - Verify retry with backoff succeeds
   - Verify max_attempts boundary

3. `tests/integration/test_idempotency.py`:
   - Same operation with same idempotency key
   - Verify deduplication

## 5. Backward Compatibility

- Retry logic is transparent to callers (automatic)
- Idempotency context is optional (default: no caching)
- Weight-update error handling adds new exception type (breaking change, requires version bump)
- Configuration extends existing RetryPolicy (no breaking changes)

## 6. Success Criteria

✅ **Unit Criteria**:
- Transient errors are retried up to max_attempts
- Non-transient errors fail immediately
- Backoff respects initial/max bounds
- Idempotency keys are unique per operation
- Weight update failures are explicitly logged

✅ **Integration Criteria**:
- Concurrent writes to same node complete successfully
- No duplicate edges created under contention
- Weight updates recover from transient failures
- Idempotency prevents duplicate side effects
- Audit events track retry attempts and outcomes

✅ **Quality Criteria**:
- All tests pass
- No performance regression (retries < 5% of requests)
- Error rate for non-retryable errors unchanged
- New metrics exportable via observability stack

## 7. Testing Strategy

### Test Scenarios

**Concurrent Write Tests**:
```python
# 10 concurrent tasks add edges to same node
# Expected: all succeed, exactly 10 edges in DB (no duplicates)
# Validates: no duplicate effect from concurrent writes
```

**Transient Error Recovery**:
```python
# Mock Spanner to fail 2x with ABORTED, then succeed
# Expected: operation succeeds after 2 retries
# Validates: retry with backoff works
```

**Idempotency Deduplication**:
```python
# First attempt fails, retry succeeds
# Expected: no duplicate node/edge created
# Validates: idempotency key prevents duplication
```

**Weight-Update Explicit Error**:
```python
# Mock 4 failures (exceeds max_attempts=3)
# Expected: WeightUpdateFailed exception raised
# Validates: explicit error visibility
```

### Test Structure
- `tests/integration/test_concurrent_writes.py` - concurrent scenarios
- `tests/integration/test_weight_update_resilience.py` - weight update specific
- `tests/integration/test_idempotency.py` - idempotency key behavior

## 8. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Retry storms (thundering herd) | Low | Exponential backoff + jitter |
| Idempotency cache memory leak | Medium | Short-lived contextvars, test cleanup |
| False positive transient classification | Medium | Conservative: only known transient codes |
| Weight-update failure causes user-visible issue | Low | Optional suppress flag, audit trail |
| Performance regression | Medium | Load tests, monitor retry %ile latency |

## 9. Rollout Plan

1. **Shadow Mode** (Week 1): Deploy with retry/backoff enabled, observe retry rates
2. **Canary** (Week 2): Roll out to 10% traffic, monitor error rates
3. **Progressive** (Week 3): 25% → 50% → 100%
4. **Monitor** (Week 4+): Watch for any anomalies

## Next Steps

1. Implement retry infrastructure (`src/db/retry.py`)
2. Implement idempotency context (`src/db/idempotency.py`)
3. Integrate into memory write paths
4. Add explicit weight-update error handling
5. Write integration tests for all scenarios
