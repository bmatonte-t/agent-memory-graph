# Task 1 Fix 3 — Report

## Summary

Two targeted fixes applied to `develop` branch. Both verified by running tests and `just check-all`.

---

## Fix 1 — `destination_node_id` None Guard (`src/memory/mindmap_pipeline.py`)

### Problem
In `SpannerAggregationAdapter.aggregate()`, `destination_node_id` was used via `str(destination_node_id)` at lines 544–555 without a prior None check. A None row value would silently produce the string `"None"`, corrupting the evidence graph node dictionary and downstream edges/paths. The `source_node_id` guard (Bug B fix) was already in place but the symmetric guard for `destination_node_id` was missing.

### Fix Applied
Added a guard block immediately after the existing `source_node_id` guard and before the `memory_tier` guard, raising `ValueError` with the row index and repr — matching the existing pattern exactly:

```python
if destination_node_id is None:
    msg = f"destination_node_id cannot be None in row {idx}: {row!r}"
    raise ValueError(msg)
```

**File:** `src/memory/mindmap_pipeline.py` (~line 531)

### New Unit Test
Added `test_spanner_aggregation_adapter_rejects_none_destination_node_id` to `tests/unit/test_mindmap_pipeline.py`. The test:
- Monkeypatches `SpannerClient.execute_sql` to return a row with `destination_node_id=None` (position 5 in the tuple)
- Asserts `pytest.raises(ValueError, match="destination_node_id cannot be None")`
- Has a docstring explaining the rationale and symmetry with the `source_node_id` guard

---

## Fix 2 — `asyncio.get_event_loop()` Deprecated in Python 3.14+ (`tests/integration/test_concurrent_writes.py`)

### Problem
`test_concurrent_session_action_increments_not_lost` called `asyncio.get_event_loop().run_in_executor(...)` inside an `async def` function. In Python 3.14+, `get_event_loop()` is deprecated inside a running loop; the correct API for code already running inside an async context is `asyncio.get_running_loop()`.

### Fix Applied
Replaced the single call site (line 241):

```python
# Before
asyncio.get_event_loop().run_in_executor(...)

# After
asyncio.get_running_loop().run_in_executor(...)
```

**File:** `tests/integration/test_concurrent_writes.py` (line 241)

---

## Verification

| Check | Result |
|---|---|
| `uv run pytest tests/unit/test_mindmap_pipeline.py tests/integration/test_concurrent_writes.py -v` | 25/25 passed |
| `just check-all` (ruff, basedpyright strict, format, full pytest suite) | 849 passed, 2 skipped, 0 errors |
| New test `test_spanner_aggregation_adapter_rejects_none_destination_node_id` | PASSED |
| No new `type: ignore` suppressions added | Confirmed |

---

## Commit

```
fix(t1-review): guard destination_node_id against None; use get_running_loop in async test
```
