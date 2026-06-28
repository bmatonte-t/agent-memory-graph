# Governance and Authorization Models

## Overview

Agent Memory Graph supports two authorization models for enterprise deployments:

1. **Internal ABAC** — Use built-in policy engine in Spanner
2. **External Delegation** — Delegate to customer's policy service

Choose the model that aligns with your enterprise's identity and governance infrastructure.

---

## Model 1: Internal ABAC

### When to Use

- You have existing role-based policies defined in Spanner or want to define them centrally
- You want minimal external dependencies
- Your authorization requirements are stable and well-defined
- You prefer a managed authorization layer within AMG

### Configuration

```yaml
single_company:
  enabled: true
  company_id: "your-org"
  auth_mode: "internal"
  external_auth_url: null  # not used
```

### How It Works

- Policies are stored in Spanner ABAC tables
- Agent requests include context: user_id, agent_id, resource_type, action
- Built-in policy engine evaluates against stored rules
- Decisions are deterministic and auditable
- Response time: ~1ms (Spanner query)

### Governance Considerations

- **Policy Updates** — Change policies in Spanner; no agent restart needed
- **Auditing** — All policy decisions logged in Audit memory tier
- **Scalability** — ABAC policy table grows linearly with rule count; no performance degradation up to 10k+ rules

---

## Model 2: External Delegation

### When to Use

- You have an existing policy service (Okta, Auth0, Entitlements Platform, custom service)
- You want authorization decisions made by your identity infrastructure
- Policies are frequently updated and managed externally
- You need real-time sync with your authorization systems

### Configuration

```yaml
single_company:
  enabled: true
  company_id: "your-org"
  auth_mode: "external"
  external_auth_url: "https://your-policy-service.example.com/authorize"
```

### How It Works

1. Agent makes a request with context: user_id, agent_id, resource, action
2. AMG sends `POST /authorize` to external policy service
3. Policy service responds: `{"allowed": bool, "reason_code": str}`
4. Decision is cached (default: 5 minutes) for performance
5. Decisions logged in Audit tier for compliance

### External Service Contract

**Request**:
```json
{
  "user_id": "user@example.com",
  "agent_id": "support-agent-v1",
  "resource": "customer_data",
  "action": "read",
  "context": {
    "organization": "your-org",
    "request_id": "req-123-abc"
  }
}
```

**Response**:
```json
{
  "allowed": true,
  "reason_code": "POLICY_MATCH",
  "ttl_seconds": 300
}
```

### Governance Considerations

- **Latency** — External service latency directly impacts AMG response time; design with <50ms P99
- **Fault Tolerance** — Cache TTL provides resilience if policy service is temporarily unavailable
- **Scalability** — Request rate to policy service scales with agent request volume; ensure policy service handles expected QPS
- **Auditability** — All delegation calls logged with policy service response and decision

---

## Comparison

| Aspect | Internal ABAC | External Delegation |
|--------|---------------|-------------------|
| **Setup Complexity** | Lower (tables in Spanner) | Higher (integrate policy service) |
| **Response Latency** | ~1ms | Service latency + cache misses |
| **Real-Time Policy** | Requires manual updates | Automatic via policy service |
| **External Dependencies** | None | Requires policy service availability |
| **Auditability** | Complete in AMG | Complete in AMG + policy service |
| **Best For** | Stable, internal policies | Dynamic, externally managed policies |

---

## Cost Implications

### Infrastructure

Both models share core infrastructure:
- **Spanner**: Base cost (Context, Semantic, Audit tiers)
- **Cloud Run**: API container + scaling costs
- **Observability**: Logs, traces, metrics

### Model-Specific

**Internal ABAC**:
- Small query cost for policy evaluation (negligible)
- Policy table storage (MB to GB scale)

**External Delegation**:
- Cost depends on your policy service (not managed by AMG)
- Potential egress charges for delegated requests (typically 0.1-1MB per request)

---

## Migration Between Models

You can switch authorization models by updating `config.yaml` and redeploying:

1. Stop agents
2. Update config.yaml (auth_mode, external_auth_url)
3. Restart agents
4. Audit trail shows config change

**No data migration required** — authorization is orthogonal to memory storage.

---

## Operational Checklist

- [ ] Choose authorization model based on infrastructure
- [ ] If Internal ABAC: define policies and load into Spanner
- [ ] If External Delegation: provide policy service endpoint and contract
- [ ] Configure `auth_mode` and optional `external_auth_url`
- [ ] Test with sample agent requests
- [ ] Validate audit trails capture all authorization decisions
- [ ] Document policy update procedures for your team
