# Agent Memory Graph API Reference

**Version**: 0.1.0  
**Base URL**: `http://localhost:8000` (development)  
**Authentication**: (To be implemented in Phase 2)

---

## Table of Contents

1. [Session Management](#session-management)
2. [Semantic Fact Ingestion](#semantic-fact-ingestion)
3. [Context Retrieval](#context-retrieval)
4. [Audit Trail](#audit-trail)
5. [Error Codes](#error-codes)
6. [Examples](#examples)

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

## Error Codes

| Code | Status | Description | Recommended Action |
|------|--------|-------------|--------------------|
| 400 | Bad Request | Invalid input parameters | Verify request format against API spec |
| 404 | Not Found | Resource does not exist | Check session_id, entity_id, or user_id |
| 409 | Conflict | Resource already exists | Use unique IDs, or retrieve existing resource |
| 500 | Internal Server Error | Database or system failure | Retry with exponential backoff |
| 503 | Service Unavailable | Spanner quota or connection issue | Check GCP Cloud Spanner status |

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

Auto-generated at: `http://localhost:8000/docs` (Phase 2)

---

**Last Updated**: 2026-06-16  
**Status**: Phase 1 Complete (Endpoints ready for Phase 2 FastAPI integration)
