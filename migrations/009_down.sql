-- DOWN Migration 009: Remove Confidence Metadata Columns and Indexes
-- Reverses: 009_add_confidence_metadata.sql
-- Purpose: Remove confidence, contradiction, and source metadata columns added in migration 009

-- Drop ENGRAM_EVIDENCE confidence indexes
DROP INDEX IF EXISTS idx_ENGRAM_EVIDENCE_FreshnessGate;
DROP INDEX IF EXISTS idx_ENGRAM_EVIDENCE_SourceConfidenceScore;

-- Remove ENGRAM_EVIDENCE confidence columns
ALTER TABLE ENGRAM_EVIDENCE DROP COLUMN IF EXISTS detected_contradictions;
ALTER TABLE ENGRAM_EVIDENCE DROP COLUMN IF EXISTS source_confidence_score;

-- Drop MemoryNode source/confidence indexes
DROP INDEX IF EXISTS idx_MemoryNode_Tier_Weight_CreatedAt;
DROP INDEX IF EXISTS idx_MemoryNode_SourceAgent_CreatedAt;

-- Remove MemoryNode source and contradiction columns
ALTER TABLE MemoryNode DROP COLUMN IF EXISTS contradiction_flags;
ALTER TABLE MemoryNode DROP COLUMN IF EXISTS source_query_id;
ALTER TABLE MemoryNode DROP COLUMN IF EXISTS source_agent_id;
