-- DOWN Migration 005: Remove Audit Immutability Control Indexes
-- Reverses: 005_audit_immutability_controls.sql
-- Purpose: Drop the optimized immutable-timeline access indexes added in migration 005

DROP INDEX IF EXISTS idx_AUDIT_EVENTS_TenantId_EventType_CreatedAt;
DROP INDEX IF EXISTS idx_AUDIT_EVENTS_TenantId_SourceNodeId_CreatedAt;
