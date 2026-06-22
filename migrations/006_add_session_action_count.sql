-- Migration 006: Add per-session action counter
-- Purpose: Persist a cumulative action counter on session nodes so weighting can use
--          a real session-scoped value rather than a per-call proxy.

ALTER TABLE MemoryNode ADD COLUMN SessionActionCount INT64 DEFAULT 0;
