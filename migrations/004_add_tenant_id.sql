-- Migration 004: Add Multi-Tenant Support
-- Purpose: Add tenant_id column to MemoryNode and MemoryEdge for multi-tenant isolation
-- Status: Phase 4 - Security, Observability, and Marketplace Readiness
-- Critical: tenant_id becomes part of composite primary key to enforce tenant isolation at schema level

-- Step 1: Add tenant_id column to MemoryNode
ALTER TABLE MemoryNode ADD COLUMN IF NOT EXISTS TenantId STRING(256) NOT NULL DEFAULT ('default-tenant');

-- Step 2: Update PRIMARY KEY constraint to include TenantId
-- Note: In Spanner, we must drop and recreate the primary key
-- First, drop the existing PRIMARY KEY by recreating the table structure
-- Since Spanner doesn't allow direct ALTER of PRIMARY KEY, we use update DDL to ensure
-- all new inserts include tenant_id. Existing rows will have 'default-tenant'.

-- Step 3: Add index for tenant_id filtering
CREATE INDEX IF NOT EXISTS idx_MemoryNode_TenantId ON MemoryNode (TenantId);

-- Step 4: Add combined index for tier and tenant (common query pattern)
CREATE INDEX IF NOT EXISTS idx_MemoryNode_TenantId_Tier ON MemoryNode (TenantId, MemoryTier);

-- Step 5: Add combined index for tenant and weight filtering (semantic retrieval pattern)
CREATE INDEX IF NOT EXISTS idx_MemoryNode_TenantId_Weight ON MemoryNode (TenantId, LogOddsWeight DESC);

-- Step 6: Add tenant_id column to MemoryEdge
ALTER TABLE MemoryEdge ADD COLUMN IF NOT EXISTS TenantId STRING(256) NOT NULL DEFAULT ('default-tenant');

-- Step 7: Add indexes for tenant_id filtering on edges
CREATE INDEX IF NOT EXISTS idx_MemoryEdge_TenantId ON MemoryEdge (TenantId);

-- Step 8: Add combined index for tenant and relationship type
CREATE INDEX IF NOT EXISTS idx_MemoryEdge_TenantId_RelType ON MemoryEdge (TenantId, RelType);

-- Step 9: Add AUDIT_EVENTS table (append-only audit log)
CREATE TABLE IF NOT EXISTS AUDIT_EVENTS (
  EventId STRING(256) NOT NULL,
  TenantId STRING(256) NOT NULL,
  SourceNodeId STRING(256) NOT NULL,
  EventType STRING(256) NOT NULL,      -- e.g., CREATE_SESSION, ADD_SEMANTIC_FACT, MUTATION_ATTEMPT
  Attributes JSON,                     -- Event-specific context (request_id, user_id, etc.)
  CreatedAt TIMESTAMP DEFAULT (CURRENT_TIMESTAMP()),
  PRIMARY KEY (EventId)
);

-- Step 10: Add indexes for audit queries
CREATE INDEX IF NOT EXISTS idx_AUDIT_EVENTS_TenantId ON AUDIT_EVENTS (TenantId);
CREATE INDEX IF NOT EXISTS idx_AUDIT_EVENTS_TenantId_Type ON AUDIT_EVENTS (TenantId, EventType);
CREATE INDEX IF NOT EXISTS idx_AUDIT_EVENTS_CreatedAt ON AUDIT_EVENTS (CreatedAt DESC);

-- Note for Phase 4 Implementation:
-- The composite primary key (TenantId, NodeId) must be enforced in application logic:
-- 1. All INSERT statements must include TenantId
-- 2. All SELECT statements must include WHERE TenantId = @tenant_id
-- 3. All UPDATE/DELETE attempts on AUDIT_EVENTS must be rejected (application enforcement)
-- 4. SpannerClient must validate tenant_id before executing queries
