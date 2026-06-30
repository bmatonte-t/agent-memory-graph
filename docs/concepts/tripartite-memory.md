# Tripartite Memory Model

Agent Memory Graph organizes all knowledge into three distinct memory tiers, stored as nodes in a single graph. Each tier has a different retention semantics, query pattern, and role in agent cognition.

## The Three Tiers

### CONTEXT — Short-term working memory

CONTEXT nodes represent the active session: what the agent said, what the user asked, what tools were called, and what decisions were made in the current conversation thread.

**Characteristics:**
- Scoped to a session (`session_id`)
- Ordered by recency (`LastAccessed DESC`)
- Retrieved via `MEMORY_RECALL_CONTEXT` to reconstruct the conversation window
- Not shared across sessions (each session has its own CONTEXT nodes)

**Typical node labels:** `SESSION`, `TURN`, `TOOL_CALL`, `DECISION`

### SEMANTIC — Long-term organizational knowledge

SEMANTIC nodes are facts about the organization that persist across sessions and are shared by all agents within the tenant. This is where domain knowledge lives.

**Characteristics:**
- Scoped to the tenant (`TenantId`), shared by all agents
- Weighted by confidence (`LogOddsWeight`) and recency (`LastAccessed`)
- Aged out through temporal decay when not accessed
- Retrieved via the MindMap pipeline when answering queries

**Typical node labels:** `PERSON`, `CONCEPT`, `DOCUMENT`, `PROCESS`, `SYSTEM`, `ORGANIZATION`

### AUDIT — Immutable compliance log

AUDIT nodes (stored in the `AUDIT_EVENTS` table) are append-only records of every access, authorization decision, mutation attempt, and reasoning step.

**Characteristics:**
- Append-only — no updates or deletes
- Every MCP tool invocation writes an audit entry (GRANTED or DENIED)
- Contains reason codes, request IDs, and decision context
- Retrieved via `MEMORY_LOG_TRACE` for compliance queries

**Typical event types:** `CREATE_SESSION`, `ADD_SEMANTIC_FACT`, `MCP_AUTHORIZATION_GRANTED`, `MCP_AUTHORIZATION_DENIED`, `MUTATION_ATTEMPT`

## Graph Structure

Nodes of any tier can be connected by edges (`MemoryEdge`). An edge has:
- `RelType` — the relationship type (e.g., `REFERENCES`, `MENTIONS`, `AUTHORED_BY`, `PART_OF`)
- `LogOddsWeight` — confidence in this relationship
- `Context` — free-form JSON metadata about the relationship

The full schema is defined as a Cloud Spanner property graph (`AgentMemoryGraph`), enabling GQL traversal queries that cross tier boundaries:

```sql
-- Example: find all facts a session has referenced
MATCH p = (s:Node {MemoryTier: 'CONTEXT', NodeId: @session_id})-[:REFERENCES]->(f:Node {MemoryTier: 'SEMANTIC'})
RETURN f.NodeId, f.Label, f.Attributes, f.LogOddsWeight
ORDER BY f.LogOddsWeight DESC
LIMIT 20
```

## Tenant Isolation

Every node and edge carries a `TenantId` column. All reads and writes include a `WHERE TenantId = @tenant_id` predicate, enforced at the application layer. Cross-tenant access is architecturally impossible unless the same tenant ID is explicitly shared.

In the current LATAM deployment, the tenant is the adopting team's organization identifier (set via the `COMPANY_ID` CI variable).

## Persistence

The graph persists in Cloud Spanner, which provides:
- Horizontal scale without resharding
- External consistency (serializable transactions)
- Native GQL property graph queries
- Automatic multi-region replication in prod

Schema is managed via SQL migration files in `migrations/` and applied by Terraform's `null_resource.run_migrations` on each `terraform apply`.
