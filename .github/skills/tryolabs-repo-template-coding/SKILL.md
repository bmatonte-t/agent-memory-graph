---
name: tryolabs-repo-template-coding
description: Enforces Tryolabs repo-template engineering standards for Python projects, including uv/just tooling, strict typing, ruff formatting, pytest conventions, gate discipline, and CI workflow behavior. Use when coding in repos created from Tryolabs templates or when normalizing a project to that standard.
---

# Tryolabs Repo Template Coding

## Overview

This skill standardizes how code is written, validated, and shipped in repositories based on the Tryolabs repo template.

It applies the same workflow used in the template and this workspace instructions, with emphasis on:
- Development Tooling
- Python and Testing Conventions
- Code Formatting and Linting Standards
- Type Safety and Gate Discipline
- CI Workflow Rules

The implementation target is not merely local correctness. Code must be adjusted until it satisfies the repository's `code-quality` GitHub Actions job contract, using the same commands and pass criteria that CI applies.

## When To Use

Use this skill when:
- Implementing or reviewing Python code in a Tryolabs-style repo.
- Setting up or fixing quality gates (lint, types, format, tests, docstrings).
- Updating CI behavior to match template expectations.
- Converting ad-hoc coding practices into template-compliant workflows.

Do not use this skill for:
- Non-Python projects with unrelated tooling.
- One-off experiments where formal quality gates are explicitly out of scope.

## Process

### 1. Preflight and Scope

1. Confirm repo is template-aligned:
  - `justfile` includes `lint`, `check-types`, `check-format`, `test-coverage`, `docstring-coverage`, `check-all`.
  - `pyproject.toml` targets Python 3.14+, Ruff, basedpyright, pytest config.
  - The repository workflow defines a `code-quality` job whose blocking checks are the standard to satisfy, not an approximation.
2. Keep scope surgical:
  - Touch only files needed for the task.
  - Avoid opportunistic refactors.
3. Surface assumptions before non-trivial changes.

### 2. Development Tooling Rules

1. Run Python commands through `uv run`.
2. Manage dependencies with `uv add`:
  - Runtime dependency: `uv add <package>`
  - Dev/CI dependency: `uv add --group dev <package>`
3. Use `just --list` to discover canonical project commands.
4. Prefer task wrappers over handcrafted command variants when a `just` target exists.

### 3. Python Coding Rules

1. Target modern Python syntax (3.14 baseline).
2. Type-hint every function parameter and return value.
3. Prefer `X | None` over `Optional[X]`.
4. Keep `try/except` blocks short and catch specific exceptions.
5. Use `logging`, not `print`.
6. Keep comments short and focused on why, not what.
7. Use Google-style docstrings for functions/classes (public and private when applicable).

### 4. Testing Rules

1. Use `pytest`.
2. Group related tests with classes when useful.
3. Use type hints in tests.
4. Assert exceptions with:
  - `pytest.raises(ExpectedError, match="...")`
5. Because `asyncio_mode = auto`, do not add `@pytest.mark.asyncio` unless explicitly required by project policy.
6. Prefer behavior-focused assertions over implementation-coupled tests.

### 5. Formatting and Linting Rules

1. Ruff is the source of truth for lint + format.
2. Keep line length at 100 chars unless project overrides.
3. Import order:
  - `__future__`
  - standard library
  - third-party
  - local
4. Use `TYPE_CHECKING` imports for type-only dependencies when appropriate.
5. Replace magic numbers with named constants where they carry domain meaning.

### 6. Type Safety and Boundary Discipline

1. Treat `Unknown` type findings from basedpyright as design boundary signals, not noise.
2. Isolate untyped external SDK usage behind typed wrappers/protocols.
3. Preserve behavior compatibility when refactoring integration boundaries.
4. Keep test patchability stable when changing import style.
5. Use explicit forward-ref rebuilds for Pydantic v2 models when needed.

### 7. CI Workflow Rules

1. In multi-check workflows, prefer collecting all results first, then failing in a final collector step.
2. Use hard failures only for issues the agent can fix automatically.
3. Emit warnings (not failures) for metadata checks that cannot be reliably auto-remediated.
4. Keep branch protection checks deterministic and reproducible locally.
5. When the repository defines a `code-quality` job, treat its check list as mandatory completion criteria for code changes.
6. Match the workflow's exact blocking steps and commands unless the task explicitly changes that workflow:
  - `lint` -> `just lint`
  - `check-format` -> `just check-format`
  - `docstring-coverage` -> `just docstring-coverage`
  - `check-types` -> `just check-types`
  - `test-coverage` -> `just test-coverage`
7. Do not consider code complete if it only passes targeted local checks but would still fail any blocking `code-quality` step.
8. If a change introduces friction with these gates, fix the code to conform to the gates before proposing CI changes. Only change the workflow when the user explicitly asks to change the standard itself.

## Verification

Run fast local loops first on touched files:
1. `uv run ruff check <touched_files>`
2. `uv run ruff format --check <touched_files>`
3. `uv run basedpyright <touched_paths>`
4. `uv run pytest <targeted_tests> -q`

Before declaring completion, verify alignment with the `code-quality` job by running its effective gates locally:
1. `just lint`
2. `just check-format`
3. `just docstring-coverage`
4. `just check-types`
5. `just test-coverage`

Then run the repository-wide completion gate:
1. `just check-all`

Completion criteria:
- Lint clean
- Format check clean
- Type check clean
- Tests passing (or documented known blockers)
- Docstring coverage gate passing
- Coverage gate passing
- No failing step from the repository `code-quality` job contract

## Common Rationalizations To Reject

- "It works locally, skip type checks."
- "This broad except is fine for now."
- "I only changed one file, no need to run full gate."
- "We can patch CI later."
- "The local targeted test passed, so the `code-quality` job can fail for now."
- "Changing CI is easier than making the code satisfy the existing gate."

## Red Flags

- New code without type hints.
- New try/except with `except Exception` and long protected blocks.
- Added dependencies with `pip install` instead of `uv add`.
- Completion claimed without `just check-all` evidence.
- CI checks failing early and hiding downstream failures.
- A change passes ad hoc local commands but still fails one of `lint`, `check-format`, `docstring-coverage`, `check-types`, or `test-coverage`.

## Output Contract For Agents Using This Skill

When reporting completion:
1. List files changed.
2. Summarize behavior impact.
3. Report verification commands executed and key outcomes, explicitly covering the repository `code-quality` steps.
4. State any residual risks or follow-up actions.
