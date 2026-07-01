-- DOWN Migration 006: Remove SessionActionCount Column
-- Reverses: 006_add_session_action_count.sql
-- Purpose: Remove the per-session action counter column from MemoryNode
-- Note: Run 007_down.sql first to drop the property graph that exposes this column

ALTER TABLE MemoryNode DROP COLUMN IF EXISTS SessionActionCount;
