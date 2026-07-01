-- DOWN Migration 001: Drop MemoryNode Table
-- Reverses: 001_memory_node_table.sql
-- Purpose: Remove the core node table and its indexes

DROP INDEX IF EXISTS idx_MemoryNode_LastAccessed;
DROP INDEX IF EXISTS idx_MemoryNode_Tier_Label;
DROP INDEX IF EXISTS idx_MemoryNode_Tier_Weight;
DROP TABLE IF EXISTS MemoryNode;
