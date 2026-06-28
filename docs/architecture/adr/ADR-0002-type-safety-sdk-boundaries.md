# ADR-0002: Type Safety Through SDK Wrapper Boundaries

- Status: Accepted
- Date: 2026-06-27
- Decision Owners: Backend Engineering Team

## Context

The project integrates with multiple untyped Google Cloud SDKs (BigQuery, Cloud Spanner, Cloud Scheduler). These SDKs return `Unknown` types from basedpyright's perspective, which:

1. Propagates `Unknown` types throughout downstream modules
2. Forces widespread use of `# type: ignore` comments (> 30 instances across files)
3. Reduces type safety and breaks the value of strict type checking
4. Makes type errors harder to distinguish from legitimate suppressions

The team faced a choice:
- Continue using `# type: ignore` comments (temporary, error-prone)
- Isolate SDK calls behind typed boundary layers (architectural pattern)
- Partially type-hint SDK classes (incomplete, fragile)

## Decision

Implement **Protocol-based SDK Wrapper Boundaries** to isolate untyped Google Cloud SDK calls and provide typed interfaces downstream.

### Pattern Details

1. **Dedicated Wrapper Module**: `src/integrations/google_sdk_wrappers.py`
   - All SDK instantiation happens here
   - All untyped SDK calls are contained at this boundary
   - Module pragma: `# pyright: reportUnknownVariableType=false` (justified suppression)

2. **Protocol Definitions**: Define typed contracts for each SDK
   - `BigQueryClientProtocol` — get_table(), list_rows()
   - `SchedulerClientProtocol` — create_job(), delete_job(), pause_job(), resume_job(), get_job(), list_jobs()
   - `SpannerDatabaseProtocol` — execute_update(), execute_sql()

3. **Cast Functions**: Establish typed boundaries
   - `as_bigquery_client(client: object) -> BigQueryClientProtocol`
   - `as_scheduler_client(client: object) -> SchedulerClientProtocol`
   - `as_spanner_database(database: object) -> SpannerDatabaseProtocol`

4. **Wrapper Functions**: Encapsulate complex operations
   - `get_bigquery_table_metadata(client, table_id) -> TableMetadata`
   - `execute_spanner_update_in_batch(database, statement, params) -> int`
   - These functions accept untyped objects but return fully typed results

5. **Downstream Usage**: Modules import and use typed protocols
   - No direct SDK calls outside `google_sdk_wrappers.py`
   - All downstream code works with typed Protocols, not Unknown types
   - Type checking passes cleanly without suppressions

## Rationale

This pattern provides:

1. **Type Safety**: Downstream modules are fully typed and strict type checking applies
2. **Clear Boundaries**: Untyped SDK integration is isolated and easy to find/modify
3. **Maintainability**: Changes to SDK integration don't ripple through codebase
4. **Documentation**: Protocol definitions serve as executable contracts
5. **Pragmatism**: Acknowledges that Google Cloud SDKs are untyped while maintaining type safety above the boundary

## Consequences

### Positive

- Basedpyright type checking passes with 0 errors in all application code
- Type safety benefits extend throughout the codebase
- Clear, single location for SDK integration logic
- Protocol definitions document expected SDK behavior
- Future SDK upgrades or replacements are easier to track

### Trade-offs

- Additional abstraction layer (minimal runtime cost, purely type-safe)
- Protocol definitions must track SDK API changes
- Wrapper functions may need updates if SDK APIs change

### Negative

- None identified; this is a strict improvement over `# type: ignore` patterns

## Implementation Status

**Fully Implemented** (2026-06-27):

- [x] `google_sdk_wrappers.py` — Protocols and cast functions
- [x] `cloud_scheduler_setup.py` — Uses `SchedulerClientProtocol`
- [x] `spanner_writer.py` — Uses `SpannerDatabaseProtocol`
- [x] `ingest_orchestrator.py` — Uses wrapper functions for schema analysis
- [x] Type checking: 0 errors, 0 warnings across all files
- [x] All 843 tests passing

## Testing & Verification

- **Unit tests**: All 17 wrapper tests passing
- **Integration tests**: All 843 project tests passing
- **Type checking**: basedpyright strict mode passes with 0 errors
- **Linting**: ruff all checks passed
- **Code review**: Passed comprehensive architecture review

## Alternatives Considered

### Alternative 1: Continue with `# type: ignore`

**Rejected** because:
- Does not scale (> 30 comments already)
- Hides real type errors
- Makes code harder to review
- No enforcement that suppressions are justified

### Alternative 2: Partial Type Hints on SDK Classes

**Rejected** because:
- Breaks if SDK APIs change
- Type hints remain incomplete
- Still requires type: ignore for uncovered SDKs
- Couples project to SDK internal structure

### Alternative 3: Do No Type Checking for SDK Integration

**Rejected** because:
- Loses type safety benefits
- Type errors bubble up to callers
- Harder to debug issues
- Does not align with project's strict type policy

## Revisit Triggers

This decision may be revisited if:

1. **Google Cloud SDKs Add Type Hints**: If gcp-python-client or specific SDKs get type stubs, can reduce wrapper verbosity
2. **New SDK Dependencies**: Ensure new SDKs follow same pattern
3. **Performance Issues**: If wrapper layer causes measurable overhead, optimize or inline
4. **API Changes**: If SDK APIs change significantly, protocols may need updates

## Impact on Objectives

| Objective | Impact | Notes |
|-----------|--------|-------|
| **Enterprise Trust** | ✅ Positive | Type safety signals production readiness |
| **Auditability** | ✅ Positive | SDK calls are centralized and trackable |
| **Determinism** | ✅ Neutral | No behavioral change; purely structural |
| **Marketplace Readiness** | ✅ Positive | Code quality signals reliability |
| **Cost & Latency** | ✅ Neutral | No measurable runtime overhead |

## References

- [copilot-instructions.md](../../copilot-instructions.md) — Lines 354-364: SDK wrapper pattern mandate
- [python.instructions.md](../../instructions/python.instructions.md) — Type annotation requirements
- [google_sdk_wrappers.py](../../../src/integrations/google_sdk_wrappers.py) — Implementation
- Code Review: [SDK_WRAPPER_VERIFICATION_REPORT.md](../verification/SDK_WRAPPER_VERIFICATION_REPORT.md)
