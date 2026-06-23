-- Migration 008: ENGRAM Evidence Metadata Table
-- Purpose: Track evidence provenance, access patterns, and metadata for Phase 4 MindMap integration
-- Design: Append-only evidence entries linked to graph retrieval and synthesis operations

-- Create ENGRAM_EVIDENCE node type for explicit evidence tracking
-- Immutable: Only INSERT allowed, no UPDATE/DELETE (enforced via constraints + audit)
CREATE TABLE ENGRAM_EVIDENCE (
  -- Primary identifier and tenant isolation
  EvidenceId STRING(36) NOT NULL,
  TenantId STRING(128) NOT NULL,

  -- Evidence source classification (path_based | neighbor_based | other)
  SourceType STRING(32) NOT NULL,

  -- Evidence ordering in retrieval sequence
  EvidenceNumber INT64 NOT NULL,

  -- Serialized evidence representation (compact format: "entity->rel->entity")
  GraphPath STRING(1024) NOT NULL,

  -- Serialized evidence in natural language (LLM output)
  SerializedForm STRING(4096),

  -- Timestamp when evidence was accessed/retrieved
  AccessTimestamp TIMESTAMP NOT NULL,

  -- Usage tracking for cognitive weighting (Phase 1 + Phase 5 integration)
  UsageCount INT64 NOT NULL DEFAULT 0,
  LastUsedTimestamp TIMESTAMP,

  -- Cognitive weight for evidence quality and freshness (Phase 5: Engram confidence)
  CognitiveWeight FLOAT64 NOT NULL DEFAULT 1.0,

  -- Sufficiency flag: explicit signal for whether this evidence was sufficient for grounding
  IsSufficient BOOL NOT NULL DEFAULT TRUE,

  -- Audit trail linkage: reference to AUDIT_EVENTS entry that recorded this evidence retrieval
  AuditLogRef STRING(36),

  -- Synthesis linkage: track which syntheses used this evidence (JSON array of synthesis_ids)
  SynthesisRefs ARRAY<STRING(36)>,

  -- Metadata extension point for future phases (confidence scores, contradiction flags, etc.)
  ExtendedMetadata STRING(2048),

  -- Immutable creation time for audit compliance
  CreatedAt TIMESTAMP NOT NULL,

) PRIMARY KEY (TenantId, EvidenceId),
  INTERLEAVE IN PARENT MEMORY_GRAPH ON DELETE CASCADE;

-- Index for efficient lookup of evidence by tenant + source type + timestamp
CREATE INDEX idx_ENGRAM_EVIDENCE_TenantId_SourceType_AccessTimestamp
ON ENGRAM_EVIDENCE (TenantId, SourceType, AccessTimestamp DESC);

-- Index for temporal analysis: find recent evidence for a tenant
CREATE INDEX idx_ENGRAM_EVIDENCE_TenantId_CreatedAt
ON ENGRAM_EVIDENCE (TenantId, CreatedAt DESC);

-- Index for synthesis linkage: find all evidence used in a synthesis
-- (Supports Phase 5: analyzing which evidence was actually used)
CREATE INDEX idx_ENGRAM_EVIDENCE_SynthesisRefs
ON ENGRAM_EVIDENCE (TenantId, SynthesisRefs);

-- Index for cognitive weight analysis: find high-weight evidence (Phase 1 + Phase 5)
CREATE INDEX idx_ENGRAM_EVIDENCE_CognitiveWeight
ON ENGRAM_EVIDENCE (TenantId, CognitiveWeight DESC, CreatedAt DESC);
