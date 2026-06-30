# Cognitive Weighting

Every node and edge in the graph carries a `LogOddsWeight` — a continuous confidence score. The cognitive weighting system keeps this score accurate over time by decaying stale knowledge and amplifying frequently-used facts.

## LogOdds Score

`LogOddsWeight` is a floating-point value, typically in the range [0.0, 1.0], representing the current confidence in a node or edge:

| Score | Interpretation |
|---|---|
| > 0.8 | High confidence — fact is frequently accessed, recently confirmed |
| 0.4 – 0.8 | Medium confidence — fact is present but aging |
| < 0.4 | Low confidence — fact is stale or weakly supported |
| < pruning threshold | Candidate for removal |

The score is initialized at 0.5 (neutral) when a node is created.

## Temporal Decay

Knowledge that is not accessed becomes less reliable over time. The decay job (`POST /internal/decay-weights`) applies exponential decay to all nodes and edges in the tenant's graph:

```
new_weight = current_weight * exp(-λ * Δt)
```

Where:
- `λ` (lambda) controls decay speed — higher values decay faster
- `Δt` is the time elapsed since `LastAccessed` in days

Decay is applied selectively per memory tier:
- **SEMANTIC** — decays slowly (knowledge remains valid longer)
- **CONTEXT** — decays faster (session context becomes irrelevant quickly)
- **AUDIT** — never decayed (audit events are immutable by design)

The decay job is intended to be scheduled via Cloud Scheduler and run on a configurable cadence (daily in prod by default).

## Action-Count Scaling

When an agent completes an action in a session, the session node's `SessionActionCount` is incremented. This counter is used as an inverse confidence modifier:

- **Low action count** (< threshold): the session is in early exploration; semantic facts retrieved are given reduced weight
- **High action count** (≥ threshold): the agent has taken several confirmatory actions; fact weights are used at full value

This prevents premature high-confidence retrieval in the first turns of a session before the agent has accumulated evidence.

The threshold is configurable via `governance.weighting.action_count_threshold` in `config.yaml` (default: 3).

## Weight Pruning

The prune job (`POST /internal/prune-weights`) removes nodes whose `LogOddsWeight` has fallen below a configured threshold. This keeps the graph from accumulating stale knowledge indefinitely.

Pruning is conservative by default:
- Only SEMANTIC nodes are pruned (CONTEXT and AUDIT are never pruned programmatically)
- SEMANTIC nodes that still have active edges are retained even if their weight is low
- The pruning threshold is configurable

## Effect on MindMap Queries

The MindMap pipeline's aggregation stage uses weights to prioritize traversal:
- High-weight edges are traversed first
- Paths with higher cumulative weight are ranked higher in the `AggregationResult`
- The serialization stage computes a `confidence` score for each fact from the path's edge weights
- The freshness gate in the synthesis stage uses the `LastAccessed` timestamp to compute `freshness_score`

The net effect: facts that are frequently accessed, recently confirmed, and supported by high-weight graph paths surface in answers; stale or weakly-supported facts are either hedged or excluded.

## Configuration

```yaml
# config.yaml
governance:
  weighting:
    enabled: true
    action_count_threshold: 3   # sessions below this get scaled weights
```

The pruning threshold and decay lambda are configurable at the application level. Contact the AMG team for tuning guidance on your graph's knowledge distribution.

## Operational Endpoints

| Endpoint | Schedule | Purpose |
|---|---|---|
| `POST /internal/decay-weights` | Daily (Cloud Scheduler) | Apply temporal decay to all nodes |
| `POST /internal/prune-weights` | Weekly (Cloud Scheduler) | Remove nodes below threshold |

These endpoints are internal-only (not exposed to agents via MCP) and should be called by the Cloud Scheduler service account, not by external callers.
