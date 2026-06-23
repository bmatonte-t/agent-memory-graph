# Phase 3: ABAC Authorization Enforcement

**Status**: Complete and enabled by default
**Version**: v0.2 production
**Last Updated**: 2026-06-22

## Overview

Phase 3 implements Attribute-Based Access Control (ABAC) for agent access to graph resources. All agent operations are now subject to authorization enforcement, which denies access by default and requires explicit authorization scopes for allowed operations.

## What is ABAC?

ABAC is a policy model where access decisions are made based on attributes of:
- **Agents**: Who is requesting (agent_id)
- **Resources**: What they're accessing (node_id, label, memory_tier, relationship_type)
- **Environment**: Where/when the request happens (tenant_id, operation type)

## Key Features

### ✅ Deny-by-Default Policy

- All operations require an explicit `AuthorizationScope` when authorization is enabled.
- Missing scope = permission denied.
- Default configuration: `authorization.enabled = true` with `default_deny = true`.

### ✅ Multi-Dimensional Resource Control

Each `AuthorizationScope` can restrict access on:

```python
AuthorizationScope(
    agent_id="agent_1",
    allowed_node_ids=["entity_1", "session_1"],     # Specific nodes
    allowed_labels=["PERSON", "Session"],            # Entity types
    allowed_memory_tiers=["SEMANTIC", "CONTEXT"],    # Memory layers
    allowed_relationship_types=["REFERENCES", "INFLUENCED_BY"],  # Edges
)
```

**Access is granted only if**:
- At least one dimension is configured (has values)
- All configured dimensions match the requested resource
- If a dimension has values, the resource must match one of them
- If all dimensions are empty (no configured values), access is **DENIED** (deny-by-default)

### ✅ Comprehensive Audit Trail

Every authorization decision (allow/deny) is recorded:

```json
{
  "event_type": "AUTHZ_ALLOW | AUTHZ_DENY",
  "tenant_id": "tenant_a",
  "agent_id": "agent_1",
  "operation": "add_semantic_fact",
  "node_id": "entity_123",
  "allowed": true,
  "context": {
    "allowed_node_ids": ["entity_1"],
    "requested_node_id": "entity_123"
  }
}
```

### ✅ Tenant Isolation

- Authorization scopes are always evaluated within the requesting tenant context.
- Cross-tenant access attempts are automatically denied.
- No data leakage between tenants.

## Enforcement Points

ABAC is enforced at all mutation and read boundaries:

| Operation | Enforced | Resource Check |
|-----------|----------|-----------------|
| `create_session` | ✅ | node_id, label="Session", tier="CONTEXT" |
| `add_semantic_fact` | ✅ | node_id, label=entity_type, tier="SEMANTIC" |
| `add_semantic_fact` (relationship) | ✅ | source_node_id, relationship_type, source_tier |
| `record_audit_event` | ✅ | node_id, label="AUDIT_EVENT", tier="AUDIT" |
| `retrieve_context_window` | ✅ | node_id, label="Session", tier="CONTEXT" |
| `_update_weight_on_successful_use` | ✅ | All node_ids in batch |

## Configuration

### Enable/Disable Authorization

```yaml
# config.yaml
governance:
  authorization:
    enabled: true          # Default: true (always enforced)
    default_deny: true     # Default: true (deny missing scopes)
```

### Default Behavior

- **enabled=true, default_deny=true**: Deny everything except explicitly allowed scopes (most secure)
- **enabled=false**: Skip all authorization checks (dev/testing only)

## Agent Integration

### Passing Authorization Scope

Every agent call must include an authorization scope:

```python
from src.security.governance import AuthorizationScope
from src.memory.api import MemoryAPI

scope = AuthorizationScope(
    agent_id="my_agent_1",
    allowed_node_ids=["allowed_entity_id"],
    allowed_labels=["PERSON"],
    allowed_memory_tiers=["SEMANTIC"],
)

# This call will succeed
response = await MemoryAPI.add_semantic_fact(
    tenant_id="tenant_a",
    entity_type="PERSON",
    entity_id="allowed_entity_id",
    authorization_scope=scope,
)

# This call will fail - entity_id not in allowed_node_ids
try:
    response = await MemoryAPI.add_semantic_fact(
        tenant_id="tenant_a",
        entity_type="PERSON",
        entity_id="other_entity_id",
        authorization_scope=scope,
    )
except PermissionError as e:
    print(f"Access denied: {e}")  # authorization denied for add_semantic_fact
```

### Empty Scope Behavior (All Dimensions Empty)

When an `AuthorizationScope` has all dimension lists empty, access is **DENIED**:

```python
scope = AuthorizationScope(
    agent_id="restricted_agent",
    # All lists empty - this denies access to ALL resources
)
# This will FAIL for any resource (deny-by-default)
```

To grant an agent access to all resources of a specific type, configure at least one dimension with all possible values:

```python
scope = AuthorizationScope(
    agent_id="unrestricted_agent",
    allowed_node_ids=[],  # Still must configure at least one dimension below
    allowed_labels=[],    # Even if empty lists won't work...
    allowed_memory_tiers=["CONTEXT", "SEMANTIC", "AUDIT"],  # Need actual values
)
# This allows access to all memory tiers (restricted to tiers only)
```

**To allow truly unrestricted access**, disable authorization in configuration:

```yaml
governance:
  authorization:
    enabled: false  # Disable ABAC (development/testing only)
```

## Denial Scenarios

### 1. Resource Outside Allowed List

```python
scope = AuthorizationScope(
    agent_id="agent_1",
    allowed_node_ids=["allowed_id"],  # Only this node is allowed
)

# ❌ DENIED - entity_id not in allowed_node_ids
await MemoryAPI.add_semantic_fact(
    tenant_id="tenant_a",
    entity_type="PERSON",
    entity_id="other_id",  # Not in allowed list
    authorization_scope=scope,
)
```

### 2. Unauthorized Label

```python
scope = AuthorizationScope(
    agent_id="agent_1",
    allowed_node_ids=["entity_1"],
    allowed_labels=["PERSON"],  # Only PERSON allowed
)

# ❌ DENIED - OBJECT not in allowed_labels
await MemoryAPI.add_semantic_fact(
    tenant_id="tenant_a",
    entity_type="OBJECT",  # Not in allowed labels
    entity_id="entity_1",
    authorization_scope=scope,
)
```

### 3. Unauthorized Memory Tier

```python
scope = AuthorizationScope(
    agent_id="agent_1",
    allowed_node_ids=["session_1"],
    allowed_labels=["Session"],
    allowed_memory_tiers=["CONTEXT"],  # Only CONTEXT tier
)

# ❌ DENIED - SEMANTIC tier not in allowed_memory_tiers
await MemoryAPI.add_semantic_fact(
    tenant_id="tenant_a",
    entity_type="Session",
    entity_id="session_1",
    authorization_scope=scope,
)
```

### 4. Relationship to Unauthorized Source

```python
scope = AuthorizationScope(
    agent_id="agent_1",
    allowed_node_ids=["dest_entity"],  # Can write dest_entity
    allowed_labels=["PERSON", "OBJECT"],
    allowed_memory_tiers=["SEMANTIC"],
)

# ❌ DENIED - cannot reference unauthorized_source
await MemoryAPI.add_semantic_fact(
    tenant_id="tenant_a",
    entity_type="PERSON",
    entity_id="dest_entity",
    relationship={"source_id": "unauthorized_source", "type": "REFERENCES"},
    authorization_scope=scope,
)
```

## Audit Trail Queries

### Check Authorization Decisions

```sql
SELECT
  EventId,
  EventType,
  CreatedAt,
  Context
FROM AUDIT_EVENTS
WHERE TenantId = @tenant_id
  AND EventType IN ('AUTHZ_ALLOW', 'AUTHZ_DENY')
ORDER BY CreatedAt DESC
LIMIT 100;
```

### Denied Decisions Only

```sql
SELECT
  EventId,
  EventType,
  CreatedAt,
  Context
FROM AUDIT_EVENTS
WHERE TenantId = @tenant_id
  AND EventType = 'AUTHZ_DENY'
ORDER BY CreatedAt DESC
LIMIT 50;
```

### Agent Activity

```sql
SELECT
  CAST(JSON_VALUE(Context, '$.agent_id') AS STRING) AS agent_id,
  EventType,
  COUNT(*) AS count
FROM AUDIT_EVENTS
WHERE TenantId = @tenant_id
  AND EventType LIKE 'AUTHZ%'
GROUP BY agent_id, EventType
ORDER BY count DESC;
```

## Error Handling

### Permission Denied Response

When an operation violates ABAC policy:

```python
PermissionError: authorization denied for add_semantic_fact
```

The error is:
- ✅ Logged in the audit trail
- ✅ Returned to the agent
- ✅ Non-retryable (permanent denial)
- ✅ Safe for client display (no sensitive details)

### MCP Tool Response

For MCP tool invocations:

```json
{
  "success": false,
  "error": {
    "code": "permission_denied",
    "message": "authorization denied for memory_add_fact",
    "retryable": false
  }
}
```

## Testing ABAC

### Unit Tests

Test policy evaluation in isolation:

```bash
uv run pytest tests/unit/test_governance.py -v
uv run pytest tests/unit/test_authorization_boundary.py -v
```

### Integration Tests

Test enforcement across API boundaries:

```bash
uv run pytest tests/integration/test_phase3_abac_enforcement.py -v
```

## Migration Guide

### From Phase 2 (Authorization Disabled)

If you have code running without authorization scope:

**Before** (Phase 2):
```python
response = await MemoryAPI.add_semantic_fact(
    tenant_id="tenant_a",
    entity_type="PERSON",
    entity_id="entity_1",
    # No authorization_scope - was allowed
)
```

**After** (Phase 3):
```python
scope = AuthorizationScope(
    agent_id="my_agent",
    allowed_node_ids=["entity_1"],
    allowed_labels=["PERSON"],
    allowed_memory_tiers=["SEMANTIC"],
)
response = await MemoryAPI.add_semantic_fact(
    tenant_id="tenant_a",
    entity_type="PERSON",
    entity_id="entity_1",
    authorization_scope=scope,  # Now required
)
```

### Temporary Disable (Dev/Testing)

If you need to temporarily disable authorization:

```python
from src.project_base.settings import settings

# Only for dev/test - DO NOT use in production
settings.governance.authorization.enabled = False
```

## Operational Runbook

### Check Authorization Status

```bash
# View current governance settings
python3 -c "from src.project_base.settings import settings; print(settings.governance.authorization)"
```

### Debug Authorization Denial

1. Check the agent's authorization scope
2. Check the audit trail for denied decisions
3. Verify resource attributes (node_id, label, tier, relationship_type)
4. Update scope if policy needs to change

### Add New Resource Access

To grant an agent access to new resources:

1. Update the `allowed_node_ids` list
2. Add required labels to `allowed_labels`
3. Ensure `allowed_memory_tiers` includes the resource's tier
4. Verify in audit trail that new operations are allowed

## Security Considerations

### ✅ Defense in Depth

- Authorization is checked at multiple points (MCP dispatch, MemoryAPI boundary, batch write)
- Even if one check is missed, others will catch it

### ✅ Audit Trail is Immutable

- Authorization decisions cannot be modified or deleted
- Can only be queried for compliance/forensics

### ✅ No Silent Failures

- Authorization denials are explicit and logged
- Cannot be confused with other error types

### ✅ Tenant Isolation

- Scopes are always evaluated within tenant context
- No cross-tenant leakage possible

## Performance

### Authorization Overhead

- Single-layer authorization check: **< 1ms**
- Audit event write: **5-20ms** (async, included in batch)
- Total per-operation: **~5-20ms** added latency

### Caching Strategies

Authorization decisions are **not** cached because:
- Policies can change between requests
- Audit trail must reflect all decisions
- Scope is per-agent per-operation

Consider caching at the **application layer** if needed.

## Compliance

### ABAC Audit Trail

Every authorization decision creates a permanent audit record:
- ✅ Who (agent_id)
- ✅ What (resource attributes)
- ✅ When (timestamp)
- ✅ Result (allowed/denied)
- ✅ Why (policy context)

### Compliance Queries

```sql
-- Find all denied access attempts
SELECT * FROM AUDIT_EVENTS
WHERE TenantId = @tenant_id
  AND EventType = 'AUTHZ_DENY'
  AND CreatedAt >= @start_date;

-- Verify agent stayed within scope
SELECT * FROM AUDIT_EVENTS
WHERE TenantId = @tenant_id
  AND CAST(JSON_VALUE(Context, '$.agent_id') AS STRING) = @agent_id;
```

## FAQ

**Q: What happens if I don't pass an authorization_scope?**
A: If authorization is enabled (default), the operation fails with `PermissionError: authorization denied`.

**Q: Can I have empty allowed lists?**
A: Yes, empty lists mean no restriction on that dimension. If all lists are empty, no restrictions are configured, and the check defaults to the policy's `default_deny` setting.

**Q: How do I grant access to ALL resources?**
A: Create a scope with all empty lists. However, it's safer to explicitly list allowed resources.

**Q: Can I query who has access to what?**
A: Yes, check the audit trail for `AUTHZ_ALLOW` events. The context contains the agent, resource, and scope.

**Q: Is authorization checked on reads?**
A: Yes, `retrieve_context_window` is an ABAC read operation.

## Next Steps

1. **Canary Rollout**: Deploy Phase 3 ABAC to 5% of tenants
2. **Monitor Audit Trail**: Check for unexpected denials
3. **Gradual Expansion**: Increase to 50%, then 100%
4. **Feedback Loop**: Adjust policies based on operational metrics

## Related Documents

- [Phase 0: Decision Freeze](../phase-gate-checklist.md)
- [Governance Policy Model](../../src/security/governance.py)
- [Authorization Boundary Tests](../../../tests/unit/test_authorization_boundary.py)
- [ABAC Enforcement Tests](../../../tests/integration/test_phase3_abac_enforcement.py)
