# Agent Memory Graph - Copilot Instructions

Apply these rules for all coding tasks in this repository unless the user explicitly asks otherwise.

## Project Identity

You are assisting with the Cognitive Agent Memory Graph, a GCP-native, deterministic, anti-hallucination memory platform.

The system is designed as a production solution for managing memory across multiple agents operating in the same GCP project or organization, with strict guarantees for safety, token efficiency, and grounded responses.

## Product Objective

Build and evolve this product to be commercially viable and publishable in Google Cloud Marketplace.

Prioritize outcomes that improve customer trust and enterprise adoption:
- Clear value proposition and buyer-facing positioning.
- Fast onboarding and time-to-value.
- Production-grade reliability, observability, and supportability.
- Strong security and IAM-aligned access controls.
- Auditable operations and transparent deployment/upgrade paths.
- Cost-aware operation, including low token-spending patterns.

## Core Workflow

- Choose the right skill before starting work.
- For non-trivial work: spec -> plan -> implement in small slices -> test -> review -> ship.
- Keep scope tight: avoid unrelated refactors and cleanup.
- Surface assumptions and ambiguities before implementing.
- Prefer simple solutions over clever abstractions.

## Verification

- Do not mark work complete without evidence.
- Run relevant tests, linting, formatting, and typing checks for changed code.
- For bugs: reproduce first, add or extend a test, then fix.

Before declaring success, run the full quality gate:

```bash
just check-all
```

## Architecture Mandates

- Preserve strict tripartite memory separation:
  - Context (short-term)
  - Semantic (long-term)
  - Audit (immutable logs)
- Never mix writes or reads across memory tiers inside the same transaction.
- Do not propose flat vector-memory replacements for core memory architecture.
- Use Google Cloud Spanner Graph as the graph persistence foundation.

### MindMap Motor

- Never allow direct LLM answering from raw user prompt alone.
- Enforce the reasoning pipeline:
  - Mine -> Aggregate -> Serialize -> Synthesize
- Synthesis must be grounded in serialized graph evidence.
- If graph retrieval returns no evidence, fail gracefully and state lack of graph knowledge. Do not guess.

### Engram Prioritization

- All new Semantic nodes and edges must include:
  - cognitive_weight
  - last_accessed
- Apply confirmation-bias updates safely: increment cognitive_weight on validated reuse.
- Weight updates must be transactional and auditable through the Audit graph.
- Traversal defaults must enforce the cognitive horizon threshold:
  - cognitive_weight > 0.30 (unless explicitly configured otherwise)

## Technology Baseline

- Database: Google Cloud Spanner (Graph Query Language, GQL)
- AI engine: Vertex AI
  - Gemini 1.5 Flash for extraction stages
  - Gemini 1.5 Pro for synthesis stages
- Backend and middleware: Python with FastAPI
- Infrastructure: GCP-native services (Cloud Run, IAM, Cloud Scheduler)

## Implementation Standards

- Prefer the smallest correct change; avoid unrelated refactors.
- GQL-first graph access: prefer GQL MATCH for relationship traversal over SQL JOIN patterns.
- Define strict typed schemas (for example, Pydantic models) for all LLM JSON outputs.
- Add an Audit event write whenever adding a function that executes external tools or API calls.
- Use logging, not print.

## Development Tooling

- Run Python commands and tests through uv run (for example, uv run pytest).
- Run project tasks through just (list tasks with just --list).
- Manage dependencies with uv add:
  - Production: uv add <package>
  - Dev and CI: uv add --group dev <package>
- Lint and format with ruff:
  - just lint
  - just format
- Type-check with basedpyright:
  - just check-types
- Test with pytest:
  - just test
  - just test-coverage
- Check docstring coverage:
  - just docstring-coverage

## Python and Testing Conventions

See detailed rules in:
- .github/instructions/python.instructions.md
- .github/instructions/tests.instructions.md

Mandatory highlights:
- Target Python 3.14 and use modern type syntax.
- Type-hint every parameter and return value.
- Use Google-style docstrings on public and private functions/classes.
- Keep try/except blocks short and catch specific exceptions.
- In tests, assert exceptions with pytest.raises(..., match=...).
- Do not use @pytest.mark.asyncio (asyncio_mode = auto).

## Code Formatting and Linting Standards

All code must pass `uv run ruff check` and `just check-all` without warnings.

### Import Organization

**Order**: future → stdlib → third-party → local (within each group, alphabetical)

```python
from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from fastapi import FastAPI
import pytest

from src.memory.api import MemoryAPI

if TYPE_CHECKING:
    from collections.abc import Callable
```

**Rules**:
- Type-only imports (used only in annotations) go behind `TYPE_CHECKING` block.
- Group imports by type using blank lines to separate.
- Never use `from typing import *` or wildcard imports; use explicit imports.
- Move third-party test imports (`pytest`) into `TYPE_CHECKING` if used only for type hints (e.g., `pytest.MonkeyPatch`, `pytest.LogCaptureFixture`).
- For type hints at runtime (e.g., `response: pytest.LogCaptureFixture`), use the fully qualified form after the `TYPE_CHECKING` import.

### Line Length

**Limit: 100 characters** (enforced by ruff rule E501)

For long lines:
- Function signatures: break after opening paren, indent parameters
- Long conditionals: wrap with parentheses and break at logical operators
- Long imports: use parentheses for multi-line imports
- Long strings: use implicit string concatenation or textwrap

```python
# Good: function signature
def long_function_name(
    param1: str,
    param2: int,
    param3: bool = False,
) -> None:

# Good: long conditional
if (
    condition_a is not None
    and condition_b == expected_value
):

# Good: long with statement
with (
    patch.object(API, "method_a", return_value=None),
    patch.object(API, "method_b", new_callable=AsyncMock),
):
```

### Variables and Assignments

**Rules**:
- Every variable must be used. Remove unused assignments and responses.
- Use specific variable names, not `_` for throwaway results in comprehensions.
- If a result is not used, do not assign it; just call the function:
  ```python
  # Bad
  response = client.post(...)

  # Good (if response isn't used)
  client.post(...)
  ```
- Use single `with` statements where possible; combine nested contexts with parentheses:
  ```python
  # Bad
  with patch.object(...) as mock_a:
      with patch.object(...) as mock_b:
          ...

  # Good
  with (
      patch.object(...) as mock_a,
      patch.object(...) as mock_b,
  ):
      ...
  ```

### Magic Numbers and Constants

**Rule**: Replace hardcoded numbers with named constants at module scope.

```python
# Bad
if request_index == 42:
    ...

# Good (at module scope)
DEGRADED_REQUEST_INDEX = 42

if request_index == DEGRADED_REQUEST_INDEX:
    ...
```

Use sets for multiple comparisons:
```python
# Bad
assert response.status_code == 200 or response.status_code == 404

# Good
assert response.status_code in {200, 404}
```

### Type Annotations

**Rules**:
- Every function parameter and return value must be annotated.
- Use `| None` instead of `Optional[...]` (Python 3.10+ union syntax).
- For complex callables, use `collections.abc.Callable` (not `typing.Callable`).
- Use `TYPE_CHECKING` for forward references and circular imports.

```python
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models import CustomType

def process(callback: Callable[[str], int]) -> None:
    ...
```

### Docstrings

**Style**: Google-style docstrings

```python
def retrieve_data(
    tenant_id: str,
    query: str,
    limit: int = 100,
) -> dict[str, object]:
    """Retrieve data from the backend.

    Args:
        tenant_id: Tenant identifier for isolation.
        query: Search query string.
        limit: Maximum number of results (1-100).

    Returns:
        dict[str, object]: Query results indexed by key.

    Raises:
        ValueError: If tenant_id is empty or limit is out of range.
        RuntimeError: If the backend is unavailable.
    """
```

### Comments and TODOs

**Rules**:
- TODO comments must include a colon: `# TODO: Fix this in Phase X`
- Comments should explain why, not what (code shows what).
- Keep comments near the code they describe.

```python
# Good
# TODO: Phase 4C: Fix src/memory/mindmap_pipeline.py::TraceRecorder.record() line 258
# Tenant isolation is enforced downstream
assert response.status_code in {200, 500}

# Bad
# TODO Phase 4C: Fix...
# response codes
assert response.status_code in {200, 500}
```

### Exception Handling

**Rules**:
- Catch specific exceptions, not `Exception`.
- Keep try/except blocks short (one operation if possible).
- Use context managers and `pytest.raises()` in tests.

```python
try:
    result = database.fetch(query)
except ValueError as e:
    logger.error("Validation failed: %s", e)
    raise
except Exception as e:
    msg = f"Unexpected error: {e}"
    raise RuntimeError(msg) from e
```

### Test Patterns

**Rules**:
- Use `pytest.raises(Exception, match="pattern")` for exception assertions.
- Mock external dependencies at the module boundary.
- Use `AsyncMock` for async functions; use `new_callable=AsyncMock` in patches.
- Combine assertion messages with pytest fixtures in the test name and docstring.
- Assert sets/lists with `assert ... in {...}` or `assert ... == {...}` for deterministic order.

```python
async def test_retrieval_fails_on_validation_error(self) -> None:
    """Validation errors should be caught and logged."""
    with pytest.raises(ValueError, match="invalid tenant"):
        await MemoryAPI.retrieve(tenant_id="")

def test_set_membership(self) -> None:
    """Status codes should be in expected set."""
    assert response.status_code in {200, 404}
```

### No Auto-fixable Violations at Commit Time

**Before committing:**
1. Run `uv run ruff check` → must show "All checks passed!"
2. Run `just check-all` → must succeed (lint + tests + types + docstrings).
3. Run `uv run pytest` on touched tests → all must pass.

If ruff can auto-fix (with `uv run ruff check --fix`), do so, but review the output to ensure no behavior changes.

## Type Safety and Gate Discipline

Apply these concrete patterns from recent hardening work whenever touching typed code, external SDK integrations, or quality gates.

### 1) Treat "Unknown" as a boundary-design signal

- `Unknown` in basedpyright means the compiler cannot prove types at that call site; this is not a runtime failure but a design debt marker.
- For external SDKs (Google Cloud Spanner, Scheduler, Vertex AI, Cloud Logging), isolate untyped APIs behind typed wrappers/protocols in `src/integrations/google_sdk_wrappers.py`.
- Keep untyped objects from crossing module boundaries. Downstream modules should consume typed protocols and helper functions only.

### 2) Keep SDK wrappers behavior-compatible

- Wrappers must preserve existing error semantics relied on by tests (especially exact exception messages).
- When refactoring to wrappers, consider behavior parity part of the contract, not an optional cleanup.

### 3) Retry closure contract: accept keyword passthrough safely

- `async_retry_with_backoff` may forward keyword arguments such as `tenant_id`.
- Internal retry closures should accept passthrough kwargs (`**_`) unless strict keyword signatures are required.
- Do not shadow outer variables used in query params/logging (for example, avoid redefining `tenant_id` inside nested closures).

### 4) Preserve test patchability during import refactors

- If tests patch symbols using module paths (for example `patch("src.memory.retrieval.EvidentPathFinder")`), instantiate via module namespace in production code (`retrieval.EvidentPathFinder(...)`) instead of directly imported symbols.
- Refactors that bypass patch targets can silently turn unit/integration tests into real dependency calls.

### 5) Pydantic v2 forward refs: rebuild explicitly when needed

- For models with forward references gated by `TYPE_CHECKING`, run explicit `model_rebuild(...)` with a runtime namespace mapping when needed.
- Keep runtime and static typing aligned to avoid late model construction failures.

### 6) Fast, reliable gate workflow

- Use tight loops first: run `uv run ruff check <touched_file>` and targeted `uv run pytest <failing_test> -q` before full gate.
- Finish every task with `just check-all` as the repository-wide completion gate.
- Do not claim completion until `ruff`, `basedpyright`, format check, pytest, and docstring coverage all pass via `just check-all`.

## CI Workflow Rules

### Blocking vs. non-blocking checks

- Use hard failures (exit 1) only for issues the agent can fix before rerun.
- For metadata the agent cannot reliably enforce (for example labels, assignees), emit ::warning:: and continue.

### Continue-on-error collection pattern

- In multi-check workflows, set continue-on-error: true on individual checks.
- Aggregate outcomes and fail in a final collector step so all checks run first.

## Multi-Agent Product Positioning Guardrails

When proposing features, architecture, docs, demos, or UX copy, maintain this positioning:
- This product is the safe shared memory fabric for many AI agents inside one GCP project or organization.
- It reduces hallucination by grounding outputs in auditable graph memory.
- It reduces token spend by prioritizing high-signal memory retrieval and compact serialization.
- It preserves functional correctness through deterministic pipeline stages and explicit no-evidence behavior.
- It supports enterprise governance through immutable audit trails and IAM-aligned operations.
