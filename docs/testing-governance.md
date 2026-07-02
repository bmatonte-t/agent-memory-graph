# Testing Governance (Centralized)

## Purpose

Define a single operating model for tests in agent-memory-graph.

This document is normative for test architecture and execution strategy.

## Core principles

- One critical behavior, one canonical test.
- Integration tests validate real integration boundaries.
- Non-functional tests do not block the default functional PR gate.
- Duplicate tests are active technical debt and must be removed.

## Canonical layers

### Component layer

- Validates deterministic business behavior and domain invariants.
- Must avoid external IO.
- Target: highest signal and maintainability.

### Contract layer

- Validates contracts across internal modules and adapters.
- Ensures request/response, error semantics, and boundary invariants.
- Replaces duplicated behavior spread across component and integration tests.

### Integration layer

- Validates real wiring and critical end-to-end behavior.
- Should avoid high mocking density.
- Must focus on confidence from real integration boundaries.

### Non-functional layer

- Includes performance, load, and chaos validations.
- Executed in dedicated gates/pipelines.

## Marker taxonomy

Mandatory pytest markers:

- unit
- contract
- integration
- smoke
- performance
- load
- chaos
- security
- migration
- slow
- asyncio

### Marker assignment policy

To avoid marker drift and keep gate behavior stable, the suite applies
default markers automatically from test file paths during collection:

- `tests/unit/**` -> `unit`
- `tests/integration/**` -> `integration`
- `tests/load/**` -> `load`
- `tests/chaos/**` -> `chaos`
- `tests/test_*.py` -> `unit` (legacy top-level tests)
- Any file name containing `performance` -> `performance`

Explicit test decorators remain valid and coexist with derived markers.

## Capability ownership and review model

The capability owner in the canonical matrix is accountable for:

- Reviewing canonical test changes for their capability.
- Approving any layer reclassification for canonical tests.
- Confirming duplicate retirement when a canonical replacement is introduced.

Review operating model:

- Weekly governance audit review: platform runtime + one rotating capability owner.
- Quarterly architecture review: all capability owners and test platform maintainers.
- Matrix freshness SLA: ownership and critical risks must be revalidated every quarter.

Source of truth:

- docs/testing-capability-matrix.md
- docs/testing-health-dashboard.md

## Test admission policy

A new test may be merged only if:

- The PR states the unique behavior validated by the test.
- The behavior is not already covered by an existing canonical test.
- Marker and layer assignment are explicit.

Admission checklist (mandatory in the PR template):

- Capability row reference from docs/testing-capability-matrix.md.
- Unique behavior statement (why this behavior is not already covered).
- Gate impact statement (PR functional, full functional, or non-functional).

## Test retirement policy

A test must be retired when:

- A canonical replacement exists for the same behavior.
- The behavior is now covered at a better layer.
- The test is semantically duplicated by another canonical test.

Retirement enforcement:

- If a canonical replacement is merged, duplicate retirement must happen in the same PR.
- If retirement cannot be completed in the same PR, the PR must include an explicit follow-up issue and due sprint.

## PR checklist additions

- Canonical behavior identified.
- Layer selected with rationale.
- Marker set correctly.
- Duplicate impact assessed.
- Replacement and retirement handled in the same PR when applicable.

## Capability traceability

Each critical capability must keep a traceability map:

- capability
- critical risks
- canonical tests by layer
- owner

Canonical source of truth:

- docs/testing-capability-matrix.md

Merge policy:

- New tests are blocked unless mapped to an existing capability row.
- If a new capability is introduced, the matrix update is mandatory in the same PR.

## Execution model

### Default PR gate

- Component
- Contract
- Smoke integration
- Command: `just test-gate-pr-functional`
- Selection protection: gate fails if selected tests are below minimum threshold.

### Full functional gate

- Component
- Contract
- Full integration
- Command: `just test-gate-full-functional`
- Selection protection: gate fails if selected tests are below minimum threshold.

### Non-functional gates

- Performance
- Load
- Chaos
- Command: `just test-gate-non-functional`
- Selection protection: gate fails if selected tests are below minimum threshold.

## Drift control

Run periodic audits for:

- semantic duplication
- integration over-mocking
- layer misuse
- flaky behavior

If drift is detected, prioritize retirement and re-canonicalization work in the next sprint.

Cadence:

- Weekly: governance inventory audit and dashboard refresh.
- Monthly: escaped defect review and mapping to canonical coverage quality.
- Quarterly: testing architecture review, ownership refresh, and capability risk revalidation.

## Freeze status

Non-canonical test creation is frozen while this policy is active.

A new test is considered canonical only if:

- It maps to a capability in docs/testing-capability-matrix.md.
- It declares target layer and unique behavior in the PR rationale.
- It does not duplicate behavior already covered in the matrix row.
- Replacement and retirement happen in the same PR when superseding legacy coverage.

## Operational baseline and commands

Baseline file:

- docs/testing-governance-baseline.json

Baseline sections:

- approved_over_mocked_integration_files
- approved_duplicate_test_identifiers
- approved_large_test_files

Governance commands:

- Generate artifacts: `just test-governance-audit`
- Enforce no new unapproved violations: `just test-governance-enforce`

## Structural complexity limits

To prevent monolithic test files from growing without control, governance enforces
a file-size policy:

- `max_test_file_lines`: maximum allowed lines per test file.
- Any file above threshold must be listed in
  `approved_large_test_files` in the baseline.
- New files exceeding threshold fail governance enforcement unless explicitly
  approved in baseline as a temporary exception.

Current operating threshold is managed in
[docs/testing-governance-baseline.json](testing-governance-baseline.json).

Artifacts generated by the governance script:

- reports/testing-governance-inventory.json
- reports/testing-governance-inventory.md
- reports/testing-health-dashboard.md
- reports/escaped-defects-log.md
