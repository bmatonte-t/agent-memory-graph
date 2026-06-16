-- Migration 001: Create MemoryNode Table
-- Purpose: Define the core node table for tripartite memory (Context, Semantic, Audit)
-- Status: Phase 1B - Schema Foundation

CREATE TABLE MemoryNode (
  NodeId STRING(256) NOT NULL,
  MemoryTier STRING(50) NOT NULL,  -- 'CONTEXT', 'SEMANTIC', 'AUDIT'
  Label STRING(256) NOT NULL,       -- Node type or entity type
  LogOddsWeight FLOAT64 DEFAULT 0.5,
  LastAccessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  VectorData BYTES(MAX),            -- Embeddings (nullable)
  Attributes JSON,                  -- Schemaless entity properties
  CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  UpdatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
) PRIMARY KEY (NodeId);

-- Indexes for common query patterns
CREATE INDEX idx_MemoryNode_Tier_Weight ON MemoryNode (MemoryTier, LogOddsWeight DESC);
CREATE INDEX idx_MemoryNode_Tier_Label ON MemoryNode (MemoryTier, Label);
CREATE INDEX idx_MemoryNode_LastAccessed ON MemoryNode (LastAccessed DESC);
