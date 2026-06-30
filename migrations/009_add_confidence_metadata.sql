-- Migration 009: Add Confidence Metadata for Phase 5 Engram Integration
-- Purpose: Extend MemoryNode and ENGRAM_EVIDENCE with source-aware confidence,
--          freshness signals, contradiction detection, and synthesis-level confidence
-- Design: Add confidence scores, source metadata, and contradiction tracking

-- Extend MemoryNode with source metadata and contradiction flags
ALTER TABLE MemoryNode ADD COLUMN IF NOT EXISTS source_agent_id STRING(128);
ALTER TABLE MemoryNode ADD COLUMN IF NOT EXISTS source_query_id STRING(128);
ALTER TABLE MemoryNode ADD COLUMN IF NOT EXISTS contradiction_flags JSON;

-- Add indexes for source tracking and confidence filtering
CREATE INDEX IF NOT EXISTS idx_MemoryNode_SourceAgent_CreatedAt
ON MemoryNode (TenantId, source_agent_id, CreatedAt DESC);

CREATE INDEX IF NOT EXISTS idx_MemoryNode_Tier_Weight_CreatedAt
ON MemoryNode (TenantId, MemoryTier, LogOddsWeight DESC, CreatedAt DESC);

-- Extend ENGRAM_EVIDENCE with confidence and contradiction metadata
ALTER TABLE ENGRAM_EVIDENCE ADD COLUMN IF NOT EXISTS source_confidence_score FLOAT64;
ALTER TABLE ENGRAM_EVIDENCE ADD COLUMN IF NOT EXISTS detected_contradictions JSON;

-- Add index for confidence-based filtering (Phase 5 gating)
CREATE INDEX IF NOT EXISTS idx_ENGRAM_EVIDENCE_SourceConfidenceScore
ON ENGRAM_EVIDENCE (TenantId, SourceType, source_confidence_score DESC, AccessTimestamp DESC);

-- Index for recency gating: find fresh evidence for synthesis
CREATE INDEX IF NOT EXISTS idx_ENGRAM_EVIDENCE_FreshnessGate
ON ENGRAM_EVIDENCE (TenantId, AccessTimestamp DESC, source_confidence_score DESC);
