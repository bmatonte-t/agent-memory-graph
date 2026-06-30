-- Migration 002: Create MemoryEdge Table with Interleaving
-- Purpose: Define the edge table for relationships, interleaved in MemoryNode for GQL traversal optimization
-- Status: Phase 1B - Schema Foundation
-- Critical: Interleaving co-locates edges with source nodes to minimize RPC calls during GQL traversals

CREATE TABLE IF NOT EXISTS MemoryEdge (
  SourceNodeId STRING(256) NOT NULL,
  EdgeId STRING(256) NOT NULL,
  DestNodeId STRING(256) NOT NULL,
  RelType STRING(256) NOT NULL,      -- Relationship type
  LogOddsWeight FLOAT64 DEFAULT (0.5),
  LastAccessed TIMESTAMP DEFAULT (CURRENT_TIMESTAMP()),
  Context JSON,                      -- Edge metadata
  CreatedAt TIMESTAMP DEFAULT (CURRENT_TIMESTAMP()),
  UpdatedAt TIMESTAMP DEFAULT (CURRENT_TIMESTAMP())
) PRIMARY KEY (SourceNodeId, EdgeId);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_MemoryEdge_SourceType ON MemoryEdge (SourceNodeId, RelType);
CREATE INDEX IF NOT EXISTS idx_MemoryEdge_DestType ON MemoryEdge (DestNodeId, RelType);
CREATE INDEX IF NOT EXISTS idx_MemoryEdge_RelType_Weight ON MemoryEdge (RelType, LogOddsWeight DESC);
