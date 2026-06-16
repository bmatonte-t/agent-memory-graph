# Agent Memory Graph - Data Model Specification

**Version**: 0.1.0  
**Database**: Google Cloud Spanner  
**Schema Format**: ISO GQL (Graph Query Language)

---

## Table of Contents

1. [Tripartite Memory Architecture](#tripartite-memory-architecture)
2. [Core Tables](#core-tables)
3. [Indexes and Optimization](#indexes-and-optimization)
4. [Graph Patterns](#graph-patterns)
5. [Cognitive Weight System](#cognitive-weight-system)
6. [Examples](#examples)

---

## Tripartite Memory Architecture

The Agent Memory Graph divides all knowledge into three immutable tiers:

```
┌─────────────────────────────────────────────────────┐
│ CONTEXT TIER (Short-term, Session-scoped)           │
│ Nodes: Session, Turn, UserInput, AgentResponse     │
│ Purpose: Conversation history, current context      │
│ Lifecycle: 24-48 hours (decays rapidly)             │
│ Mutability: Mutable (weights updated on access)    │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ SEMANTIC TIER (Long-term, Global knowledge)         │
│ Nodes: Entity (POLE+O), Relationship, Fact         │
│ Purpose: Persistent facts, learned entities         │
│ Lifecycle: Months to years (decays slowly)          │
│ Mutability: Mutable (weights tuned via use)        │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ AUDIT TIER (Immutable log, Compliance)              │
│ Nodes: Event, Transaction, Operation                │
│ Purpose: Complete operation history                 │
│ Lifecycle: Permanent retention                      │
│ Mutability: INSERT ONLY (no updates/deletes)       │
└─────────────────────────────────────────────────────┘
```

### Design Rationale

- **Separation of Concerns**: Each tier has different retention and mutation policies
- **Performance**: Short-lived data (CONTEXT) separate from persistent data (SEMANTIC)
- **Compliance**: Audit trail isolated and immutable (AUDIT)
- **Cognitive Modeling**: Mimics human memory (working, long-term, autobiographical)

---

## Core Tables

### MemoryNode

Central table for all nodes in the tripartite memory model.

**DDL**:
```sql
CREATE TABLE MemoryNode (
    NodeId STRING(256) NOT NULL,
    MemoryTier STRING(50) NOT NULL,  -- CONTEXT, SEMANTIC, AUDIT
    Label STRING(100),                 -- Entity type or node kind
    LogOddsWeight FLOAT64 NOT NULL,    -- Cognitive weight in log-odds
    LastAccessed TIMESTAMP,            -- Most recent access
    VectorData BYTES(MAX),             -- Optional embedding vector
    Attributes JSON,                   -- Flexible attributes
    CreatedAt TIMESTAMP NOT NULL,
    UpdatedAt TIMESTAMP NOT NULL,
    PRIMARY KEY (NodeId)
) INTERLEAVE IN PARENT MemoryNode;

CREATE INDEX idx_MemoryNode_Tier_Weight 
    ON MemoryNode(MemoryTier, LogOddsWeight DESC);
CREATE INDEX idx_MemoryNode_Tier_Label 
    ON MemoryNode(MemoryTier, Label);
CREATE INDEX idx_MemoryNode_LastAccessed 
    ON MemoryNode(LastAccessed DESC);
```

**Column Definitions**:

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `NodeId` | STRING(256) | No | PK: Unique node identifier (UUID recommended) |
| `MemoryTier` | STRING(50) | No | CONTEXT \| SEMANTIC \| AUDIT |
| `Label` | STRING(100) | Yes | Entity type (PERSON, OBJECT, LOCATION, EVENT, ORGANIZATION, etc.) |
| `LogOddsWeight` | FLOAT64 | No | Cognitive weight in log-odds units (initially 0.5) |
| `LastAccessed` | TIMESTAMP | Yes | Timestamp of most recent access (null = never) |
| `VectorData` | BYTES(MAX) | Yes | Embedding vector (for semantic similarity, Phase 2) |
| `Attributes` | JSON | Yes | Flexible attributes: `{"name": "...", "role": "...", ...}` |
| `CreatedAt` | TIMESTAMP | No | Node creation timestamp (immutable) |
| `UpdatedAt` | TIMESTAMP | No | Last update timestamp |

**Constraints**:
- PRIMARY KEY (NodeId)
- FOREIGN KEY for edge relationships (see MemoryEdge)

---

### MemoryEdge

Represents directed edges between nodes in the graph.

**DDL**:
```sql
CREATE TABLE MemoryEdge (
    SourceNodeId STRING(256) NOT NULL,
    EdgeId STRING(256) NOT NULL,
    DestNodeId STRING(256) NOT NULL,
    RelType STRING(100) NOT NULL,      -- REFERENCES, LOCATED_AT, WORKED_AT, etc.
    LogOddsWeight FLOAT64 NOT NULL,
    LastAccessed TIMESTAMP,
    Context JSON,                       -- Edge-specific metadata
    CreatedAt TIMESTAMP NOT NULL,
    UpdatedAt TIMESTAMP NOT NULL,
    PRIMARY KEY (SourceNodeId, EdgeId),
    FOREIGN KEY (SourceNodeId) REFERENCES MemoryNode(NodeId) ON DELETE CASCADE,
    FOREIGN KEY (DestNodeId) REFERENCES MemoryNode(NodeId) ON DELETE CASCADE
) INTERLEAVE IN PARENT MemoryNode ON DELETE CASCADE;

CREATE INDEX idx_MemoryEdge_Source_Type 
    ON MemoryEdge(SourceNodeId, RelType);
CREATE INDEX idx_MemoryEdge_Dest_Type 
    ON MemoryEdge(DestNodeId, RelType);
CREATE INDEX idx_MemoryEdge_Type_Weight 
    ON MemoryEdge(RelType, LogOddsWeight DESC);
```

**Column Definitions**:

| Column | Type | Description |
|--------|------|-------------|
| `SourceNodeId` | STRING(256) | FK: Source node (parent in INTERLEAVE) |
| `EdgeId` | STRING(256) | PK2: Unique edge identifier |
| `DestNodeId` | STRING(256) | FK: Destination node |
| `RelType` | STRING(100) | Relationship type (REFERENCES, LOCATED_AT, WORKED_AT, etc.) |
| `LogOddsWeight` | FLOAT64 | Edge weight (initially 0.5) |
| `LastAccessed` | TIMESTAMP | Most recent traversal |
| `Context` | JSON | Edge metadata: `{"strength": 0.8, "type": "strong", ...}` |
| `CreatedAt` | TIMESTAMP | Edge creation |
| `UpdatedAt` | TIMESTAMP | Last update |

**Design Note**: INTERLEAVE IN PARENT MemoryNode co-locates edges with their source nodes for optimal GQL traversal performance.

---

## Indexes and Optimization

### Strategic Indexes

```sql
-- Retrieve all nodes in tier ordered by weight (for decay operations)
CREATE INDEX idx_MemoryNode_Tier_Weight 
    ON MemoryNode(MemoryTier, LogOddsWeight DESC);

-- Find nodes by type within tier (for POLE+O filtering)
CREATE INDEX idx_MemoryNode_Tier_Label 
    ON MemoryNode(MemoryTier, Label);

-- Retrieve nodes accessed before timestamp (for decay cutoff)
CREATE INDEX idx_MemoryNode_LastAccessed 
    ON MemoryNode(LastAccessed DESC);

-- Outgoing edges from source with type filter (for graph traversal)
CREATE INDEX idx_MemoryEdge_Source_Type 
    ON MemoryEdge(SourceNodeId, RelType);

-- Incoming edges to destination (for reverse traversal)
CREATE INDEX idx_MemoryEdge_Dest_Type 
    ON MemoryEdge(DestNodeId, RelType);

-- Edges ordered by relationship type and strength
CREATE INDEX idx_MemoryEdge_Type_Weight 
    ON MemoryEdge(RelType, LogOddsWeight DESC);
```

### INTERLEAVE Benefits

- **Co-location**: Edges stored on same partition as source node
- **Performance**: GQL traversal (source → edges → destination) avoids cross-partition seeks
- **Cascading**: DELETE from MemoryNode automatically deletes all edges (referential integrity)

---

## Graph Patterns

### Graph Definition

```sql
CREATE PROPERTY GRAPH MemoryGraph
  NODE TABLES (MemoryNode AS Node)
  EDGE TABLES (
    MemoryEdge AS Edge 
    SOURCE KEY (SourceNodeId) REFERENCES Node(NodeId)
    DESTINATION KEY (DestNodeId) REFERENCES Node(NodeId)
    LABEL (RelType)
  );
```

### Common GQL Queries

**Pattern 1: Session Context Window**
```gql
MATCH p = (s:Node)-[e]->(t:Node)
WHERE s.NodeId = @session_id 
  AND s.MemoryTier = 'CONTEXT'
  AND t.MemoryTier = 'CONTEXT'
RETURN t.NodeId, t.Label, t.Attributes, t.LogOddsWeight, t.CreatedAt, e.RelType
ORDER BY t.CreatedAt DESC
LIMIT @window_size
```

**Pattern 2: Entity Lookup**
```gql
MATCH p = (n:Node)
WHERE n.MemoryTier = 'SEMANTIC'
  AND n.Label = @entity_type
  AND n.LogOddsWeight > @threshold
RETURN n.NodeId, n.Attributes, n.LogOddsWeight
ORDER BY n.LogOddsWeight DESC
```

**Pattern 3: Relationship Traversal (2-hop)**
```gql
MATCH p = (a:Node)-[e1]->(b:Node)-[e2]->(c:Node)
WHERE a.NodeId = @start_id
  AND e1.RelType = @rel_type_1
  AND e2.RelType = @rel_type_2
  AND b.MemoryTier = @tier
RETURN a, e1, b, e2, c
```

---

## Cognitive Weight System

### Log-Odds Weight

Weights are represented as **log-odds** (natural logarithm of odds ratio):

```
weight = ln(P(True) / P(False))

Where:
  P(True)  = probability fact is true/relevant
  P(False) = probability fact is false/irrelevant

Examples:
  weight = 0.0   → odds = 1:1     (50% confidence)
  weight = 0.5   → odds ≈ 1.65:1  (62% confidence)
  weight = 1.0   → odds ≈ 2.7:1   (73% confidence)
  weight = -0.5  → odds ≈ 0.6:1   (38% confidence)
```

### Weight Dynamics

**Initial Weight**:
```
LogOddsWeight = 0.5  (62% confidence baseline)
```

**Bayesian Update on Success**:
```
LogOddsWeight_new = LogOddsWeight_old + ln(BAYES_FACTOR)
BAYES_FACTOR = 1.25  (25% increase in odds ratio)
ln(1.25) ≈ 0.223 bits
```

**Temporal Decay**:
```
LogOddsWeight(t) = LogOddsWeight(0) * e^(-decay_rate * hours_since_access)
decay_rate = 0.05 per hour
```

Example:
- Initial weight: 0.5
- After 10 uses: 0.5 + (10 × 0.223) = 2.73
- After 1 week decay (no use): 2.73 × e^(-0.05 × 168) ≈ 0.02 (effectively forgotten)

**Pruning Threshold**:
```
weight < 0.30 → Soft-delete (is_deleted = true)
```

---

## Attributes JSON Schema

### MemoryNode Attributes

**CONTEXT Node Example**:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "turn_index": 5,
  "role": "user",
  "message": "What is the capital of France?",
  "timestamp": "2026-06-16T17:30:00Z"
}
```

**SEMANTIC Node Example**:
```json
{
  "entity_type": "PERSON",
  "name": "Alice Johnson",
  "role": "research_scientist",
  "organization": "ACME Labs",
  "expertise": ["machine_learning", "natural_language_processing"],
  "contact": "alice@example.com",
  "created_by": "user_123",
  "source": "direct_ingestion"
}
```

**AUDIT Node Example**:
```json
{
  "event_type": "ADD_SEMANTIC_FACT",
  "source_node_id": "entity_456",
  "user_id": "user_123",
  "action": "created",
  "duration_ms": 42,
  "status": "success",
  "context": {
    "entity_type": "PERSON",
    "relationship_type": "REFERENCES"
  }
}
```

### MemoryEdge Context

```json
{
  "confidence": 0.95,
  "source": "training_data",
  "bidirectional": false,
  "metadata": {
    "discovered_at": "2026-06-16T17:30:00Z",
    "relationship_strength": "strong"
  }
}
```

---

## Examples

### Insert Examples

**Create Session**:
```sql
INSERT INTO MemoryNode (
    NodeId, MemoryTier, Label, LogOddsWeight, 
    LastAccessed, Attributes, CreatedAt, UpdatedAt
) VALUES (
    '550e8400-e29b-41d4-a716-446655440000',
    'CONTEXT',
    'Session',
    0.5,
    CURRENT_TIMESTAMP(),
    JSON('{"user_id": "user_456", "provider": "openai"}'),
    CURRENT_TIMESTAMP(),
    CURRENT_TIMESTAMP()
);
```

**Add Semantic Fact**:
```sql
INSERT INTO MemoryNode (
    NodeId, MemoryTier, Label, LogOddsWeight,
    LastAccessed, Attributes, CreatedAt, UpdatedAt
) VALUES (
    'alice_123',
    'SEMANTIC',
    'PERSON',
    0.5,
    CURRENT_TIMESTAMP(),
    JSON('{"name": "Alice", "role": "engineer", "expertise": ["systems", "databases"]}'),
    CURRENT_TIMESTAMP(),
    CURRENT_TIMESTAMP()
);
```

**Create Relationship**:
```sql
INSERT INTO MemoryEdge (
    SourceNodeId, EdgeId, DestNodeId, RelType,
    LogOddsWeight, LastAccessed, CreatedAt, UpdatedAt
) VALUES (
    'alice_123',
    '12345678-abcd-efgh-ijkl-mnopqrstuvwx',
    'company_456',
    'WORKED_AT',
    0.5,
    CURRENT_TIMESTAMP(),
    CURRENT_TIMESTAMP(),
    CURRENT_TIMESTAMP()
);
```

### Query Examples

**Retrieve Context for Session**:
```gql
MATCH p = (s:Node)-[]->(t:Node)
WHERE s.NodeId = '550e8400-e29b-41d4-a716-446655440000'
  AND s.MemoryTier = 'CONTEXT'
RETURN t.NodeId, t.Label, t.Attributes, t.LogOddsWeight
ORDER BY t.CreatedAt DESC
LIMIT 10
```

**Find High-Confidence Facts**:
```gql
MATCH (n:Node)
WHERE n.MemoryTier = 'SEMANTIC'
  AND n.LogOddsWeight > 1.0
RETURN n.NodeId, n.Label, n.LogOddsWeight
ORDER BY n.LogOddsWeight DESC
```

---

## Performance Characteristics

| Operation | Query Pattern | Estimated Latency |
|-----------|---------------|-------------------|
| Create node | INSERT MemoryNode | <10ms |
| Create edge | INSERT MemoryEdge | <15ms |
| Retrieve context (10 turns) | GQL MATCH | <50ms |
| Retrieve context (100 turns) | GQL MATCH | <200ms |
| Decay weights (1000 nodes) | UPDATE + timestamp | <500ms |
| Find entity by type | INDEX lookup | <25ms |
| Find relationships (fan-out) | INDEX + GQL | <100ms |

---

## Migration Strategy

Migrations are version-controlled and idempotent:

```
migrations/
  001_memory_node_table.sql
  002_memory_edge_table.sql
  003_property_graph.sql
  004_indexes.sql  (Phase 2+)
  005_vector_index.sql  (Phase 2+)
```

Run all migrations sequentially on fresh instance:
```bash
./scripts/run-migrations.sh
```

---

**Last Updated**: 2026-06-16  
**Maintained by**: Agent Memory Graph Development Team
