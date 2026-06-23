# Agent Memory Graph API Reference

**Version**: 0.2.0 (Production Ready)
**Base URL**: `http://localhost:8000` (development) | Production via Cloud Run
**Authentication**: Tenant-scoped with ABAC authorization
**Status**: ✅ All phases 0-5 implemented

---

## Table of Contents

1. [Authentication & Authorization](#authentication--authorization)
2. [Session Management](#session-management)
3. [Semantic Fact Ingestion](#semantic-fact-ingestion)
4. [Context Retrieval](#context-retrieval)
5. [Evidence Operations](#evidence-operations)
6. [Weighting Configuration](#weighting-configuration)
7. [Authorization Policies](#authorization-policies)
8. [Audit Trail](#audit-trail)
9. [Error Codes](#error-codes)
10. [Configuration Guide](#configuration-guide)
11. [Examples](#examples)

---

## Authentication & Authorization

### Phase 3: ABAC (Attribute-Based Access Control)

All requests to MemoryAPI and MCP endpoints are subject to authorization checks. Authorization uses an `AuthorizationScope` that enforces deny-by-default policy.

**Authorization Model**:

```python
from src.security.governance import AuthorizationScope, AuthorizationPolicy

# Define allowed resources for an agent
scope = AuthorizationScope(
    agent_id="agent_123",
    allowed_node_ids=["session_1", "entity_a"],      # Specific nodes
    allowed_labels=["PERSON", "SESSION"],             # Entity types
    allowed_memory_tiers=["SEMANTIC", "CONTEXT"],     # Memory layers
    allowed_relationship_types=["REFERENCES"]         # Edge types
)

# Access is granted only if resource matches configured dimensions
# Empty scope = access denied
```

**Authorization Requirements**:

- **For Session Creation**: `allowed_memory_tiers` must include `CONTEXT`
- **For Fact Addition**: `allowed_memory_tiers` must include `SEMANTIC`, `allowed_labels` must include entity type
- **For Context Retrieval**: `allowed_node_ids` must include session_id
- **For Audit Access**: Special `AUDIT_READ` scope required

**Authorization Error Handling**:

```python
from src.api.main import AuthorizationError

try:
    context = await MemoryAPI.retrieve(
        session_id="session_1",
        agent_id="agent_999",
        authorization_scope=empty_scope  # Empty scope
    )
except AuthorizationError as e:
    print(f"Access denied: {e.reason_code}")
    # reason_code: DENIED_SESSION_NOT_ALLOWED, DENIED_NODE_ID_NOT_ALLOWED, etc.
```

---

## Session Management

### Create Session

Create a new session and initialize its Context Graph.

**Endpoint**: `POST /api/memory/sessions` (Phase 2)

**Method**: `create_session(session_id: str, user_id: str, metadata: dict) → SessionResponse`

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `session_id` | string | Yes | Unique session identifier (UUID recommended) |
| `user_id` | string | Yes | User ID associated with session |
| `metadata` | object | No | Session metadata (arbitrary JSON) |

**Response** (200 OK):
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-06-16T17:30:00.000Z",
  "status": "active"
}
```

**Error Codes**:
- `400 Bad Request`: Empty session_id or user_id
- `500 Internal Server Error`: Database write failed

**Example** (Python):
```python
from src.memory.api import MemoryAPI

session = await MemoryAPI.create_session(
    session_id="550e8400-e29b-41d4-a716-446655440000",
    user_id="user_123",
    metadata={"provider": "openai", "model": "gpt-4"}
)
print(session.status)  # "active"
```

---

## Semantic Fact Ingestion

### Add Semantic Fact

Ingest an entity into the Semantic Graph with baseline cognitive weight.

**Endpoint**: `POST /api/memory/facts` (Phase 2)

**Method**: `add_semantic_fact(entity_type: str, entity_id: str, attributes: dict, relationship: dict) → FactResponse`

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `entity_type` | enum | Yes | POLE+O type: PERSON, OBJECT, LOCATION, EVENT, ORGANIZATION |
| `entity_id` | string | Yes | Unique entity identifier |
| `attributes` | object | No | Entity attributes (arbitrary JSON) |
| `relationship` | object | No | Optional relationship: `{type, source_id}` |

**Response** (201 Created):
```json
{
  "entity_id": "entity_456",
  "entity_type": "PERSON",
  "node_path": "/PERSON/entity_456",
  "weight": 0.5,
  "created_at": "2026-06-16T17:30:05.000Z"
}
```

**Error Codes**:
- `400 Bad Request`: Invalid entity_type or empty entity_id
- `404 Not Found`: Source node not found (if relationship provided)
- `500 Internal Server Error`: Database write failed

**Example**:
```python
fact = await MemoryAPI.add_semantic_fact(
    entity_type="PERSON",
    entity_id="john_doe_123",
    attributes={"name": "John Doe", "role": "engineer"},
    relationship={"type": "WORKED_AT", "source_id": "company_456"}
)
print(fact.weight)  # 0.5 (initial weight)
```

**Entity Types** (POLE+O Framework):
- `PERSON`: Individuals, actors
- `OBJECT`: Physical or abstract objects
- `LOCATION`: Geographic or spatial locations
- `EVENT`: Occurrences, incidents, interactions
- `ORGANIZATION`: Groups, institutions, teams

---

## Context Retrieval

### Retrieve Context Window

Retrieve recent session history via graph traversal with metadata.

**Endpoint**: `GET /api/memory/sessions/{session_id}/context` (Phase 2)

**Method**: `retrieve_context_window(session_id: str, window_size: int = 10) → ContextResponse`

**Parameters**:
| Name | Type | Required | Range | Description |
|------|------|----------|-------|-------------|
| `session_id` | string | Yes | - | Session identifier |
| `window_size` | integer | No | 1-100 | Number of turns to retrieve (default: 10) |

**Response** (200 OK):
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "turns": [
    {
      "turn_id": "turn_1",
      "node_id": "turn_1_node_id",
      "role": "user",
      "content": "{\"message\": \"Hello\"}",
      "weight": 0.52,
      "created_at": "2026-06-16T17:30:10.000Z"
    },
    {
      "turn_id": "turn_2",
      "node_id": "turn_2_node_id",
      "role": "agent",
      "content": "{\"message\": \"Hi there\"}",
      "weight": 0.50,
      "created_at": "2026-06-16T17:30:11.000Z"
    }
  ],
  "total_weight_sum": 1.02,
  "retrieved_at": "2026-06-16T17:30:15.000Z"
}
```

**Error Codes**:
- `400 Bad Request`: Invalid session_id or window_size
- `404 Not Found`: Session not found
- `500 Internal Server Error`: Database query failed

**Example**:
```python
context = await MemoryAPI.retrieve_context_window(
    session_id="550e8400-e29b-41d4-a716-446655440000",
    window_size=20
)
for turn in context.turns:
    print(f"{turn.role}: {turn.content}")
```

---

## Audit Trail

### Record Audit Event (Internal)

Record immutable event in Audit Graph.

**Method**: `record_audit_event(event_type: str, source_node_id: str, context: dict) → AuditResponse`

**Note**: Automatically called by all public APIs. Can be called directly for custom events.

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `event_type` | string | Yes | Event type (CREATE_SESSION, ADD_SEMANTIC_FACT, etc.) |
| `source_node_id` | string | Yes | Source node that triggered event |
| `context` | object | No | Event context metadata |

**Response**:
```json
{
  "event_id": "event_abc123",
  "event_type": "CREATE_SESSION",
  "timestamp": "2026-06-16T17:30:00.000Z"
}
```

**Event Types**:
- `CREATE_SESSION`: Session created
- `ADD_SEMANTIC_FACT`: Entity added to semantic memory
- `RETRIEVE_CONTEXT_WINDOW`: Context retrieved
- `DECAY_WEIGHTS`: Temporal decay applied
- `PRUNE_WEIGHTS`: Weight-based pruning executed

**Example**:
```python
event = await MemoryAPI.record_audit_event(
    event_type="CUSTOM_EVENT",
    source_node_id="session_123",
    context={"reason": "user_feedback", "score": 0.95}
)
print(event.event_id)  # Unique audit log entry
```

---

## Cognitive Weighting

### Temporal Decay (Scheduled)

Applied daily at 2 AM UTC via Cloud Scheduler.

**Method**: `decay_weights_temporal(decay_rate: float = 0.05) → int`

**Formula**: `weight_t = weight_0 * e^(-decay_rate * hours_since_access)`

**Default Parameters**:
- `decay_rate`: 0.05 per hour (5% per hour)
- Schedule: Daily 2:00 AM UTC

**Example**:
```python
# Manual invocation (normally Cloud Scheduler)
from src.memory.cognitive_weighting import CognitiveWeighting
updated = await CognitiveWeighting.decay_weights_temporal(decay_rate=0.05)
```

### Weight Pruning (Scheduled)

Applied daily at 3 AM UTC via Cloud Scheduler.

**Method**: `prune_weights_below_threshold(threshold: float = 0.30) → int`

**Default Parameters**:
- `threshold`: 0.30 (30% of initial weight)
- Schedule: Daily 3:00 AM UTC

---

## Evidence Operations

### Phase 4: Operational Evidence Retrieval

Retrieve recent evidence for operational diagnostics and debugging.

**Method**: `get_evidence_context_for_tenant(tenant_id: str, limit_hours: int = 24) → list[EvidenceItem]`

**Purpose**: Query recent ENGRAM_EVIDENCE entries for a tenant to diagnose retrieval issues and verify evidence quality.

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `tenant_id` | string | Yes | - | Tenant identifier for isolation |
| `limit_hours` | integer | No | 24 | Hours lookback from now |

**Response**:
```python
@dataclass
class EvidenceItem:
    evidence_id: str              # Unique evidence identifier
    source_type: EvidenceSourceType  # PATH_BASED, ENRICHED_NEIGHBOR, etc.
    evidence_number: int          # Sequence in result set
    graph_path: str               # GraphPath representation
    serialized_form: str          # Full evidence serialization
    access_timestamp: datetime    # When evidence was accessed
    cognitive_weight: float       # Current weight (0.0-1.0)
    audit_log_ref: str           # Reference to audit event
    freshness_score: float       # Freshness decay (0.0-1.0, recent=high)
```

**Example**:
```python
from src.memory.evidence_service import EvidenceService

service = EvidenceService()
evidence = await service.get_evidence_context_for_tenant(
    tenant_id="tenant_a",
    limit_hours=24
)

for item in evidence:
    print(f"Evidence: {item.evidence_id}")
    print(f"  Freshness: {item.freshness_score:.2f}")
    print(f"  Weight: {item.cognitive_weight:.2f}")
    print(f"  Source: {item.source_type}")
```

**Error Handling**:
- `ValueError`: Invalid tenant_id (empty or malformed)
- `RuntimeError`: Database query failed (transient)

---

## Weighting Configuration

### Phase 1: Action-Scaled Weighting

Configure cognitive weighting to scale with tenant agent activity volume.

**Configuration**:

```yaml
# config.yaml
governance:
  weighting:
    enabled: true                  # Master switch
    action_count_threshold: 3      # Minimum actions before weighting triggers
```

**Weighting Trigger Logic**:

```python
from src.memory.cognitive_weighting import WeightingTriggerPolicy

policy = WeightingTriggerPolicy(action_count_threshold=3)

# Weighting triggers when session action count >= threshold
should_weight = policy.should_trigger(action_count=5)  # True
should_weight = policy.should_trigger(action_count=2)  # False
```

**Weighting Behavior**:

- **Low-volume tenants** (< 3 actions): Weighting skipped for efficiency
- **High-volume tenants** (>= 3 actions): Weighting runs after each action
- **Fallback**: If weighting disabled, uses deterministic baseline

**Performance Impact**:

| Threshold | Avg Actions/Session | Weighting Runs | Latency Overhead |
|-----------|-------------------|-----------------|------------------|
| 3 | 10 | 7 | +50ms per session |
| 5 | 10 | 5 | +30ms per session |
| 10 | 10 | 1 | +5ms per session |

**Tuning Guide**:

- **Interactive workloads** (low latency required): threshold=10
- **Batch workloads** (throughput focus): threshold=3
- **Mixed workloads**: threshold=5 (balanced)

---

## Authorization Policies

### Phase 3: ABAC Policy Definition

Define and enforce fine-grained authorization scopes for agents accessing graph resources.

**Policy Model**:

```python
from src.security.governance import AuthorizationScope, AuthorizationPolicy

# 1. Define scope for an agent
scope = AuthorizationScope(
    agent_id="data_analyst_1",
    allowed_node_ids=["project_a", "team_x"],       # Nodes agent can access
    allowed_labels=["DATASET", "QUERY"],             # Entity types allowed
    allowed_memory_tiers=["SEMANTIC"],               # Memory layers (CONTEXT, SEMANTIC, AUDIT)
    allowed_relationship_types=["CREATED_BY", "OWNS"]  # Relationship types allowed
)

# 2. Check authorization
policy = AuthorizationPolicy(default_deny=True)
can_access = policy.authorize(
    scope=scope,
    resource_id="project_a",
    resource_label="DATASET"
)
# Result: True (matches both node_id and label)

# 3. All dimensions are AND-combined
scope_strict = AuthorizationScope(
    agent_id="agent_1",
    allowed_node_ids=["node_1"],
    allowed_labels=["PERSON"]
)
# Access granted only if BOTH conditions match:
# - resource_id in ["node_1"]
# - resource_label in ["PERSON"]
```

**Built-in Policies**:

| Policy Type | Description | Example Scope |
|------------|-------------|----------------|
| Full Access | Agent can access all resources | `allowed_node_ids=None, allowed_labels=None` (granted if empty, only if authorization disabled) |
| Tenant-Scoped | Agent limited to specific tenant | `allowed_node_ids=[node for node in tenant_a]` |
| Role-Based | Agent limited by entity type | `allowed_labels=["DATASET", "REPORT"]` |
| Time-Limited | (Not implemented in v0.2; planned for v0.3) | N/A |

**Audit Trail for Authorization**:

Every authorization decision is logged with reason code:

```json
{
  "event_type": "MCP_AUTHORIZATION_GRANTED",
  "agent_id": "agent_1",
  "resource_id": "node_1",
  "reason_code": "AUTHORIZED_AGENT_SCOPE",
  "timestamp": "2026-06-24T12:00:00Z"
}
```

**Reason Codes**:

| Code | Meaning |
|------|---------|
| `AUTHORIZED_AGENT_SCOPE` | Authorization granted |
| `DENIED_SESSION_NOT_ALLOWED` | Session not in allowed_node_ids |
| `DENIED_NODE_ID_NOT_ALLOWED` | Node not in allowed_node_ids |
| `DENIED_AUDIT_ACCESS_NOT_ALLOWED` | AUDIT_READ not in scope |
| `DENIED_UNSUPPORTED_TOOL` | Tool not supported by authorization |
| `MISSING_AUTHORIZATION_SCOPE` | No scope provided |
| `AUTHORIZATION_DISABLED` | Authorization checks disabled |

---

## Retry and Resilience Configuration

### Phase 2: Transient Failure Recovery

All critical mutations (create_session, add_semantic_fact, record_audit_event) automatically retry on transient failures.

**Configuration**:

```yaml
# config.yaml
governance:
  retry:
    max_attempts: 3              # Total attempts (including first)
    initial_backoff_seconds: 0.25  # First backoff: 250ms
    max_backoff_seconds: 5.0     # Maximum backoff: 5s
```

**Backoff Strategy**:

- **Exponential backoff**: delay = min(initial * 2^attempt, max)
- **Attempt 1**: Immediate (no backoff)
- **Attempt 2**: 0.25s delay
- **Attempt 3**: 0.5s delay
- **Max**: 5.0s cap

**Transient Errors (Automatically Retried)**:

- `ABORTED` (Spanner transaction conflict)
- `RESOURCE_EXHAUSTED` (Quota or connection limit)
- `DEADLINE_EXCEEDED` (Timeout)

**Permanent Errors (Not Retried)**:

- `INVALID_ARGUMENT` (Bad request)
- `PERMISSION_DENIED` (Authorization failed)
- `NOT_FOUND` (Resource missing)

**Idempotency Context**:

All mutations include IdempotencyContext to prevent duplicate effects on retry:

```python
from src.db.idempotency import IdempotencyContext

# Idempotency key auto-generated or provided
context = IdempotencyContext(
    idempotency_key="fact_add_123",  # Unique for this operation
    operation_type="ADD_SEMANTIC_FACT"
)

# If operation retries, same idempotency_key ensures single effect
```

---

## Confidence and Freshness Models

### Phase 5: Engram-Inspired Confidence Quality

Evidence includes confidence metadata and freshness scoring to influence synthesis decisions.

**Confidence Breakdown**:

```python
from src.models.confidence import ConfidenceBreakdown, EvidenceSourceType

breakdown = ConfidenceBreakdown(
    source_types={
        EvidenceSourceType.PATH_BASED: 0.85,
        EvidenceSourceType.ENRICHED_NEIGHBOR: 0.70,
        EvidenceSourceType.SYNTHESIZED: 0.60
    },
    aggregate_confidence=0.72,
    contradiction_count=0,
    last_updated=datetime.utcnow()
)
```

**Freshness Scoring**:

```python
from src.models.confidence import FreshnessScore
from datetime import datetime, timedelta

# Freshness = exp(-λ * hours_old), where λ=0.1
recent = datetime.utcnow() - timedelta(hours=1)
old = datetime.utcnow() - timedelta(hours=24)

freshness_recent = FreshnessScore.compute(recent, decay_lambda=0.1)
# current_score ≈ 0.90

freshness_old = FreshnessScore.compute(old, decay_lambda=0.1)
# current_score ≈ 0.09

# Synthesis gates on freshness_threshold (default 0.30)
is_fresh_enough = freshness_recent.current_score > 0.30  # True
is_stale = freshness_old.current_score > 0.30  # False
```

**Gating Logic in Synthesis**:

```python
# Evidence is used for synthesis only if:
# 1. aggregate_confidence > confidence_threshold (default 0.50)
# 2. freshness_score > freshness_threshold (default 0.30)
# 3. contradiction_count == 0 (no unresolved conflicts)

if (breakdown.aggregate_confidence >= 0.50
    and freshness_score >= 0.30
    and breakdown.contradiction_count == 0):
    use_for_synthesis()
else:
    mark_insufficient_evidence()
```

---

## Error Codes

| Code | Status | Description | Recommended Action |
|------|--------|-------------|--------------------|
| 400 | Bad Request | Invalid input parameters (empty tenant_id, invalid scope) | Verify request format against API spec |
| 403 | Forbidden | Authorization check failed (ABAC deny) | Check AuthorizationScope has required dimensions |
| 404 | Not Found | Resource does not exist (session, entity) | Check session_id, entity_id, or tenant_id |
| 409 | Conflict | Resource already exists or transient conflict | Use unique IDs, or retry with backoff |
| 500 | Internal Server Error | Database or system failure (transient) | Automatic retry via async_retry_with_backoff |
| 503 | Service Unavailable | Spanner quota/connection issue (transient) | Automatic retry via async_retry_with_backoff |

**v0.2 Additions**:

| Exception | HTTP Code | Cause | Handling |
|-----------|-----------|-------|----------|
| `AuthorizationError` | 403 | ABAC scope violation | Check scope dimensions |
| `IdempotencyError` | 409 | Duplicate idempotency key | Retry with same key is safe |
| `RetryExhaustedError` | 500 | Max retry attempts exceeded | Exponential backoff exhausted |
| `TenantIsolationError` | 403 | Cross-tenant access attempt | Check tenant_id matches session |

---

## Rate Limits

**Phase 1**: No rate limiting (local/development)

**Phase 2+**: Recommended limits per session:
- Session creation: 10/minute
- Fact ingestion: 100/minute
- Context retrieval: 50/minute
- Audit events: Unlimited (internal)

---

## Examples

### Complete Workflow

```python
from src.memory.api import MemoryAPI
from src.memory.cognitive_weighting import CognitiveWeighting

# 1. Create session
session = await MemoryAPI.create_session(
    session_id="conv_123",
    user_id="user_456",
    metadata={"model": "gpt-4", "temperature": 0.7}
)

# 2. Add entities
person = await MemoryAPI.add_semantic_fact(
    entity_type="PERSON",
    entity_id="alice",
    attributes={"name": "Alice", "role": "scientist"}
)

location = await MemoryAPI.add_semantic_fact(
    entity_type="LOCATION",
    entity_id="lab_1",
    attributes={"name": "Lab 1", "floor": 3},
    relationship={"type": "LOCATED_AT", "source_id": "alice"}
)

# 3. Retrieve context
context = await MemoryAPI.retrieve_context_window(
    session_id=session.session_id,
    window_size=10
)

# 4. Monitor weights
stats = await CognitiveWeighting.get_weight_statistics()
print(f"SEMANTIC tier: {stats['SEMANTIC']['mean_weight']:.2f}")
```

---

## Integration with FastAPI (Phase 2)

```python
from fastapi import APIRouter
from src.memory.api import MemoryAPI

router = APIRouter(prefix="/api/memory", tags=["memory"])

@router.post("/sessions", response_model=SessionResponse)
async def create_session_endpoint(request: CreateSessionRequest):
    return await MemoryAPI.create_session(
        session_id=request.session_id,
        user_id=request.user_id,
        metadata=request.metadata
    )

@router.post("/facts", response_model=FactResponse)
async def add_fact_endpoint(request: AddSemanticFactRequest):
    return await MemoryAPI.add_semantic_fact(
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        attributes=request.attributes,
        relationship=request.relationship
    )

@router.get("/sessions/{session_id}/context", response_model=ContextResponse)
async def retrieve_context_endpoint(session_id: str, window_size: int = 10):
    return await MemoryAPI.retrieve_context_window(
        session_id=session_id,
        window_size=window_size
    )
```

---

## OpenAPI/Swagger

Auto-generated at: `http://localhost:8000/docs`

---

## Configuration Guide

See detailed configuration in:
- `docs/operations/weighting-configuration.md` (Phase 1: Action-scaled weighting)
- `docs/operations/phase3-abac-enforcement-guide.md` (Phase 3: Authorization policies)
- `docs/operations/retry-configuration-guide.md` (Phase 2: Retry and resilience)

---

**Last Updated**: 2026-06-24
**Status**: ✅ Phase 0-5 Complete (v0.2 Production Ready)
**Next**: Phase 6 - Production deployment and marketplace launch
