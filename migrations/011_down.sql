-- Down Migration 011: Remove session lifecycle columns from MemoryNode

DROP INDEX idx_MemoryNode_SessionStatus;
ALTER TABLE MemoryNode DROP COLUMN SessionEndReason;
ALTER TABLE MemoryNode DROP COLUMN SessionEndedAt;
ALTER TABLE MemoryNode DROP COLUMN SessionStatus;
