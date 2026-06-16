-- Migration 002: Create MemoryEdge Table with Interleaving
-- Purpose: Define the edge table for relationships, interleaved in MemoryNode for GQL traversal optimization
-- Status: Phase 1B - Schema Foundation
-- Critical: Interleaving co-locates edges with source nodes to minimize RPC calls during GQL traversals

CREATE TABLE MemoryEdge (
  SourceNodeId STRING(256) NOT NULL,
  EdgeId STRING(256) NOT NULL,
  DestNodeId STRING(256) NOT NULL,
  RelType STRING(256) NOT NULL,      -- Relationship type
  LogOddsWeight FLOAT64 DEFAULT 0.5,
  LastAccessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  Context JSON,                      -- Edge metadata
  CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  UpdatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  CONSTRAINT fk_MemoryEdge_Source FOREIGN KEY (SourceNodeId) REFERENCES MemoryNode (NodeId),
  CONSTRAINT fk_MemoryEdge_Dest FOREIGN KEY (DestNodeId) REFERENCES MemoryNode (NodeId),
  PRIMARY KEY (SourceNodeId, EdgeId),
) INTERLEAVE IN PARENT MemoryNode ON DELETE CASCADE;

-- Indexes for common query patterns
CREATE INDEX idx_MemoryEdge_SourceType ON MemoryEdge (SourceNodeId, RelType);
CREATE INDEX idx_MemoryEdge_DestType ON MemoryEdge (DestNodeId, RelType);
CREATE INDEX idx_MemoryEdge_RelType_Weight ON MemoryEdge (RelType, LogOddsWeight DESC);
