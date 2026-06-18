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
