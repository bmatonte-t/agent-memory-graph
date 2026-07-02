-- Migration 011: Add session lifecycle columns to MemoryNode
-- Purpose: Persist explicit session closure state for deterministic idempotency
-- and timeout lifecycle handling.

ALTER TABLE MemoryNode ADD COLUMN SessionStatus STRING(32);
ALTER TABLE MemoryNode ADD COLUMN SessionEndedAt TIMESTAMP;
ALTER TABLE MemoryNode ADD COLUMN SessionEndReason STRING(64);

-- Index optimized for session lifecycle lookups in context tier.
CREATE INDEX IF NOT EXISTS idx_MemoryNode_SessionStatus
ON MemoryNode (MemoryTier, SessionStatus, UpdatedAt DESC);
