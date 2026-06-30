-- Migration 005: Audit Immutability Controls
-- Purpose: Harden append-only audit usage with optimized immutable access paths.

-- Optimize immutable timeline lookups by tenant and source node.
CREATE INDEX IF NOT EXISTS idx_AUDIT_EVENTS_TenantId_SourceNodeId_CreatedAt
ON AUDIT_EVENTS (TenantId, SourceNodeId, CreatedAt DESC);

-- Optimize immutable timeline lookups by tenant and event type.
CREATE INDEX IF NOT EXISTS idx_AUDIT_EVENTS_TenantId_EventType_CreatedAt
ON AUDIT_EVENTS (TenantId, EventType, CreatedAt DESC);
