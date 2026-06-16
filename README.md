# Agent Memory Graph

Cognitive Agent Memory Graph - A production-ready tripartite memory model for AI agents built on Google Cloud Spanner.

## Overview

The Agent Memory Graph implements a sophisticated memory architecture for AI agents with three distinct tiers:

- **CONTEXT**: Session-scoped short-term memory (conversation history)
- **SEMANTIC**: Global long-term knowledge (facts, entities, relationships) 
- **AUDIT**: Immutable operational logs for compliance and debugging

Each tier has independent mutation policies, retention schedules, and cognitive weighting based on Bayesian updates and temporal decay.

## Quick Start

### Local Development

```bash
# Setup Python environment
python3 -m venv venv
source venv/bin/activate
uv pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Start development server
uvicorn src.api.main:app --reload
```

## Phase 1 - Foundation (Complete ✅)

- ✅ Spanner schema with INTERLEAVE optimization
- ✅ 4 core memory APIs (create_session, add_semantic_fact, record_audit_event, retrieve_context_window)
- ✅ Cognitive weighting (Bayesian updates, temporal decay, pruning)
- ✅ Cloud Scheduler integration for maintenance jobs
- ✅ 60/60 tests passing (71% code coverage)
- ✅ Performance benchmarks (all <500ms)

## Documentation

- [API Reference](docs/api-reference.md)
- [Data Model Specification](docs/data-model-spec.md)
- [Phase 1 Validation Report](docs/phase1-validation-report.md)
- [Architecture Decision Records](docs/architecture/adr/)

## Contributing

Found a bug or have a feature request? Check out our [Contributing Guide](CONTRIBUTING.md) and feel free to open an issue.
