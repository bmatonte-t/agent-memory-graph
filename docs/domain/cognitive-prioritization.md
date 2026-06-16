# Cognitive Modeling and Prioritization Notes

## Overview

Cognitive prioritization keeps long-term memory useful and cost-efficient.

Each Semantic node and edge includes:
- cognitive_weight (FLOAT64)
- last_accessed (TIMESTAMP)

The system increases weights for useful evidence paths and decays stale memory over time.

## Core Lifecycle

### 1) Genesis (Baseline Initialization)

When a new semantic fact is ingested:
- assign baseline weight (for example, 0.50)
- treat it as candidate memory pending future confirmation

### 2) Confirmation Bias (Positive Reinforcement)

Trigger:
- a path contributes to a successful grounded answer or tool execution

Action:
- increment weights of nodes/edges used in that path

Example formula:

$$
W_{new} = \min(W_{old} + 0.15, 1.0)
$$

### 3) Temporal Decay

Trigger:
- scheduled background process (for example Cloud Scheduler + Cloud Run)

Action:
- reduce stale weights based on elapsed time since last_accessed

Example formula:

$$
W_{new} = \max(W_{old} \times e^{-\lambda t}, 0.01)
$$

### 4) Cognitive Horizon

Mechanism:
- retrieval filters include only memories above a threshold (for example $W > 0.30$)

Outcome:
- lower noise in retrieval
- reduced token usage during synthesis
- preserved cold knowledge for admin/offline access

## Operational Requirements

- Update last_accessed on retrieval
- Perform reinforcement updates asynchronously when possible
- Keep decay jobs observable and idempotent
- Record relevant update events in Audit Graph

## Candidate Prioritization Signals

- Utility: downstream task impact
- Novelty: information gain
- Confidence: source and extraction reliability
- Risk: potential harm if incorrect
- Freshness: temporal recency by memory class

## Marketplace Alignment Notes

Prioritization improves marketability by:
- keeping response quality stable as memory grows
- controlling inference and storage costs
- supporting predictable latency and buyer-friendly performance expectations

## Open Questions

- Should prioritization be globally fixed or task-contextual?
- Should decay policy differ by memory class?
- How should low-confidence memory be constrained in retrieval?
