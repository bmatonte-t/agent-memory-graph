-- DOWN Migration 002: Drop MemoryEdge Table
-- Reverses: 002_memory_edge_table.sql
-- Purpose: Remove the edge table and its indexes
-- Note: Must be run before 001_down.sql (MemoryEdge references MemoryNode)

DROP INDEX IF EXISTS idx_MemoryEdge_RelType_Weight;
DROP INDEX IF EXISTS idx_MemoryEdge_DestType;
DROP INDEX IF EXISTS idx_MemoryEdge_SourceType;
DROP TABLE IF EXISTS MemoryEdge;
