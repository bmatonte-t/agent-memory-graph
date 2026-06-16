# Architecture Options

## Evaluation Criteria

Use these criteria consistently when comparing options:
- Deterministic grounding and anti-hallucination guarantees
- Simplicity of operations and observability on GCP
- Security, tenancy, and audit compliance posture
- Performance and cost predictability at scale
- Marketplace readiness (buyer trust, deployability, supportability)

## Option A: Graph-first Memory Core

Spanner Graph is the primary memory system.
Vertex AI performs extraction, scoring, and retrieval planning.

Pros:
- Native graph traversal for relationship-heavy recall
- Strong durability and consistency model

Cons:
- Requires careful schema discipline for evolving cognition models
- Potentially higher complexity for vector-heavy retrieval use cases

Marketplace Fit:
- Strong trust posture from deterministic retrieval and simpler architecture
- Clearer operations model for enterprise buyers

## Option B: Hybrid Graph + Vector Sidecar

Spanner Graph stores symbolic memory and relations.
A vector index stores semantic embeddings with synchronized IDs.
Vertex AI orchestrates retrieval fusion.

Pros:
- Better semantic recall and symbolic reasoning blend
- Tunable retrieval strategy by task class

Cons:
- Dual-write and consistency complexity
- More moving parts for operations

Marketplace Fit:
- Potentially higher recall quality for semantic-heavy domains
- Higher support burden and reliability risk due to multi-system coupling

## Option C: Event-sourced Cognitive Pipeline

Raw events are immutable source of truth.
Derived graph memory projections are materialized asynchronously.

Pros:
- Strong replay and reproducibility
- Easier experimentation with scoring strategies

Cons:
- Eventual consistency for derived memory views
- Higher initial platform investment

Marketplace Fit:
- Strong compliance and replay story for regulated buyers
- Longer path to launch readiness for first commercial version
