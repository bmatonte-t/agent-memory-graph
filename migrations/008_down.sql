-- DOWN Migration 008: Drop ENGRAM_EVIDENCE Table
-- Reverses: 008_add_engram_evidence_table.sql
-- Purpose: Remove the ENGRAM evidence provenance table and its indexes
-- Note: Run 009_down.sql first to drop indexes added by migration 009 on this table

DROP INDEX IF EXISTS idx_ENGRAM_EVIDENCE_CognitiveWeight;
DROP INDEX IF EXISTS idx_ENGRAM_EVIDENCE_TenantId_CreatedAt;
DROP INDEX IF EXISTS idx_ENGRAM_EVIDENCE_TenantId_SourceType_AccessTimestamp;
DROP TABLE IF EXISTS ENGRAM_EVIDENCE;
