# Agent Memory Graph - Global Instructions

## Description

**Cognitive Agent Memory Graph** — a GCP-native tripartite memory system (Context / Semantic / Audit graphs) backed by Google Cloud Spanner. It exposes a FastAPI service and an MCP (Model Context Protocol) layer. Phases 1-2 are implemented; later phases will add retrieval pipelines, decay scheduling, and Cloud Marketplace packaging.

## General guidance

- If any conventions or workflows are unclear, please ask for clarification or examples.
- Prefer the smallest correct change. Do not refactor unrelated code.
- The three memory tiers (Context, Semantic, Audit) must stay strictly isolated — never mix writes or reads across tiers in the same transaction.

## Development process

Before saying you're done, you must always solve all linting, formatting, and typing errors.
If a typing error is genuinely unsolvable, ask the user; they may grant an exception and allow `# type: ignore[<error-code>]`.

Run the full quality gate before declaring success:

```bash
just check-all   # lint + check-types + check-format + test-coverage + docstring-coverage
```

## Tooling

- Run commands and tests with `uv run` (e.g. `uv run pytest`).
- Run predefined tasks with `just <task>` — list all with `just --list`.
- Install production dependencies: `uv add <package>`.
- Install dev/CI dependencies: `uv add --group dev <package>` (groups: `dev`, `cicd`, `documentation`).
- **Linter / formatter**: `ruff` — run `just lint` and `just format`.
- **Type checker**: `basedpyright` — run `just check-types`.
- **Tests**: `pytest` with `asyncio_mode = "auto"` — run `just test` or `just test-coverage`.
- **Docstring coverage**: `docstr-coverage` — run `just docstring-coverage`.

## CI/CD workflow conventions

### Hard failures vs. warnings in GitHub Actions

**Critical rule**: Only use `exit 1` in a workflow step when the issue is something an automated agent *can* fix before the check runs. For metadata that agents cannot control (e.g. GitHub labels, PR assignees), emit a `::warning::` instead and let the job continue.

```yaml
# ✅ Correct — metadata the agent cannot set: warn, do not block
if [ "$label_count" -eq 0 ]; then
  echo "::warning::There are no labels on this PR. Add one when available for cleaner release notes."
fi

# ❌ Wrong — this blocks the PR and the agent can never satisfy it automatically
if [ "$label_count" -eq 0 ]; then
  echo "There are no labels on this PR."
  exit 1
fi
```

Concretely, the `check-pr-style` workflow checks **title casing** and **trailing period** with `exit 1` (fixable by the agent) but checks **labels** and **assignees** with `::warning::` (not fixable by the agent).

### Continue-on-error pattern

Multi-step quality jobs collect individual step outcomes and fail at a final "collect results" step. Always use `continue-on-error: true` on individual check steps and use the collector pattern so all checks run before the job fails.

## Python code conventions

(See also `.github/instructions/python.instructions.md` for full details.)

- Target **Python 3.14**; use modern type syntax (`str | None`, `list[str]`, etc.).
- Always add type hints to every function parameter and return value.
- Use `collections.abc` generic types for parameters; concrete types for return values.
- Use Google-style docstrings on all functions and classes (including private ones).
- Use `logging` — not `print`. Log extensively at appropriate levels.
- Keep `try/except` blocks short and catch specific exceptions.
- Prefer `pathlib` over `os.path`.
- No abbreviations except `env`, `id`, `idx`.
- Use `f-strings` for string formatting.
- Define `StrEnum` for fixed sets of string constants.

## Testing conventions

(See also `.github/instructions/tests.instructions.md` for full details.)

- All tests use `pytest`; group related tests in classes.
- Because `asyncio_mode = "auto"`, **do not** add `@pytest.mark.asyncio` to async test functions.
- Use `pytest.raises(..., match=r"...")` for exception assertions — always pass `match`.
- Use fixtures for shared state; parametrize where appropriate.
- Test input → output behaviour, not internal call graphs.
- Add Google-style docstrings to every test function and class.

## Data model / architecture reminders

- **MemoryNode** and **MemoryEdge** tables use Spanner interleaving; never change interleaving without a migration.
- `cognitive_weight` must be set on every new Semantic node/edge (default `0.5`). Weight updates must be transactional and auditable via the Audit graph.
- All GQL traversal queries should filter by `cognitive_weight > 0.30` (configurable threshold) to enforce the cognitive horizon.
- When adding a new memory operation, always record a corresponding audit event inside the same Spanner write batch.