# Tripartite Memory Topology Notes

## Overview

The system avoids flat-vector memory as the primary architecture and uses a tripartite memory topology implemented in Google Cloud Spanner Graph.

Memory is separated by volatility, scope, and purpose:
- Context Graph: short-term working state
- Semantic Graph: long-term factual memory
- Audit Graph: immutable execution evidence

This structure supports deterministic behavior, explainability, and enterprise trust.

## 1) Context Graph (Short-Term Memory)

Purpose:
- Maintain continuity during an active session or task.

Characteristics:
- Scope: session-local
- Volatility: high (ephemeral, summarized over time)

Typical nodes/edges:
- Nodes: Session, DialogueTurn, Intent, LocalVariable
- Edges: HAS_TURN, FOLLOWED_BY, EXTRACTED

Operational flow:
- At session close, high-value signals can be promoted to Semantic Graph.
- Raw interaction history can be archived per retention policy.

## 2) Semantic Graph (Long-Term Memory)

Purpose:
- Durable, shared memory across sessions and authorized agents.

Characteristics:
- Scope: global or tenant-scoped
- Volatility: low (controlled updates)

Typical nodes/edges:
- Nodes: Person, Organization, Project, Document, Concept
- Edges: MANAGES, DEPENDS_ON, BELONGS_TO, AFFECTS

Required properties on semantic nodes and edges:
- cognitive_weight
- last_accessed

Operational flow:
- Retrieval updates relevance signals.
- Scheduled decay attenuates stale memory paths.

## 3) Audit Graph (Immutable Memory)

Purpose:
- Full traceability of agent behavior for compliance and debugging.

Characteristics:
- Scope: system-wide
- Volatility: append-only

Typical nodes/edges:
- Nodes: AgentEvent, ToolExecution, ReasoningStep, SystemState
- Edges: TRIGGERED_BY, RESULTED_IN, REFERENCED_NODE

Operational flow:
- Before or alongside tool execution and final responses, write audit events.
- Connect used Context/Semantic evidence via REFERENCED_NODE for provenance.

## Spanner Graph Implementation Guidance

Use a unified schema with property graph mapping.

Example:

```sql
CREATE PROPERTY GRAPH AgentMemoryGraph
  NODE TABLES (
    Sessions, Turns, Entities, Events
  )
  EDGE TABLES (
    SessionTurns SOURCE KEY (session_id) REFERENCES Sessions
                 DESTINATION KEY (turn_id) REFERENCES Turns
  );
```

Prefer GQL MATCH traversal for relationship-heavy retrieval and SQL for bulk update jobs where appropriate.

## Marketplace Alignment Notes

This topology improves product marketability by:
- Enabling auditable enterprise behavior by design
- Supporting policy and tenant boundaries explicitly
- Providing deterministic, explainable retrieval patterns buyers can trust

## Open Questions

- How strict should cross-memory write boundaries be?
- Which cross-links should be weighted versus informational?
- Which agent stages may write to Semantic Graph directly?
