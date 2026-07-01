-- DOWN Migration 004: Remove Multi-Tenant Support
-- Reverses: 004_add_tenant_id.sql
-- Purpose: Remove TenantId columns, tenant indexes, and the AUDIT_EVENTS table
-- Note: Run 003_down.sql first to drop the property graph before dropping indexes

-- Drop AUDIT_EVENTS indexes and table
DROP INDEX IF EXISTS idx_AUDIT_EVENTS_CreatedAt;
DROP INDEX IF EXISTS idx_AUDIT_EVENTS_TenantId_Type;
DROP INDEX IF EXISTS idx_AUDIT_EVENTS_TenantId;
DROP TABLE IF EXISTS AUDIT_EVENTS;

-- Drop MemoryEdge tenant indexes
DROP INDEX IF EXISTS idx_MemoryEdge_TenantId_RelType;
DROP INDEX IF EXISTS idx_MemoryEdge_TenantId;

-- Drop MemoryNode tenant indexes
DROP INDEX IF EXISTS idx_MemoryNode_TenantId_Weight;
DROP INDEX IF EXISTS idx_MemoryNode_TenantId_Tier;
DROP INDEX IF EXISTS idx_MemoryNode_TenantId;

-- Remove TenantId columns
-- Note: Cloud Spanner does not support DROP COLUMN on columns that are part of
-- a PRIMARY KEY or are referenced by an existing index. Drop indexes above first.
ALTER TABLE MemoryEdge DROP COLUMN IF EXISTS TenantId;
ALTER TABLE MemoryNode DROP COLUMN IF EXISTS TenantId;
