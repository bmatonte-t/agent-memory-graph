"""Weighting Tier Configuration and Monitoring Runbook

Phase 1 Operational Guide: Action-Scaled Cognitive Weighting

This runbook provides operational guidance for configuring and monitoring
action-scaled cognitive weighting across tenant cohorts.
"""

# Weighting Tier Configuration and Monitoring Runbook

## Overview

Action-scaled cognitive weighting allows the system to adjust weighting frequency
and strength based on tenant agent activity volume. Low-activity tenants skip
weighting operations efficiently, while high-activity tenants receive more
weighting opportunities.

**Baseline Configuration:**
- Weighting enabled by default: `False` (disabled for backward compatibility)
- Default action count threshold: `3` (minimum session actions before weighting triggers)
- Weighting frequency: Per-session, after each agent action

---

## 1. Configuration

### 1.1 Enable Weighting for a Tenant Cohort

Edit `config.yaml` in the deployment:

```yaml
governance:
  weighting:
    enabled: true
    action_count_threshold: 3
```

**Configuration Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `false` | Master switch for action-scaled weighting. Set to `true` to enable. |
| `action_count_threshold` | int | `3` | Minimum session action count before weighting is triggered (must be ≥ 1). |

### 1.2 Tuning the Threshold by Tenant Activity

**For LOW-ACTIVITY deployments** (< 100 actions/hour per tenant):
```yaml
governance:
  weighting:
    enabled: true
    action_count_threshold: 2  # Trigger weighting more frequently
```

**For MEDIUM-ACTIVITY deployments** (100-1000 actions/hour):
```yaml
governance:
  weighting:
    enabled: true
    action_count_threshold: 3  # Default; balanced approach
```

**For HIGH-ACTIVITY deployments** (> 1000 actions/hour):
```yaml
governance:
  weighting:
    enabled: true
    action_count_threshold: 5  # Reduce weighting frequency to save compute
```

### 1.3 Environment-Specific Configuration

Use separate config files for Dev, Staging, and Prod:

```bash
# Development: aggressive weighting
config.dev.yaml → action_count_threshold: 1

# Staging: tuned threshold
config.staging.yaml → action_count_threshold: 3

# Production: conservative threshold
config.prod.yaml → action_count_threshold: 5
```

---

## 2. Behavioral Guarantees

### 2.1 Weighting Trigger Behavior

| Session Action Count | Policy: `enabled=true, threshold=3` | Result |
|----------------------|--------------------------------------|--------|
| 1                    | `1 < 3` → False                      | ⏭️ Skip weighting |
| 2                    | `2 < 3` → False                      | ⏭️ Skip weighting |
| 3                    | `3 >= 3` → True                      | ✅ Apply weighting |
| 4                    | `4 >= 3` → True                      | ✅ Apply weighting |
| 100                  | `100 >= 3` → True                    | ✅ Apply weighting |

### 2.2 Session Action Counter

- **Initialization:** Counter starts at 0 for each new session.
- **Increment:** Counter increments by 1 on each successful agent action.
- **Scope:** Per-tenant, per-session (isolated across tenants and sessions).
- **Persistence:** Stored in `MemoryNode.SessionActionCount` in Spanner.
- **Atomicity:** Increments are transactional (guaranteed exactly-once per action).

### 2.3 Weight Update Behavior

When weighting is triggered:
1. Retrieve nodes accessed in the current session.
2. Compute log-odds update: `LogOddsWeight += ln(1.25) ≈ 0.223`
3. Update `MemoryNode.LogOddsWeight` and `LastAccessed` timestamp.
4. Log the update at INFO level for observability.

When weighting is skipped (below threshold):
1. Log at INFO level: `weight_update_skipped tenant_id=X action_count=Y threshold=Z`
2. Continue processing without applying weights.

---

## 3. Monitoring and Observability

### 3.1 Key Metrics

Monitor these metrics in your observability platform (Cloud Logging, Datadog, etc.):

**Metric: `weight_update_triggered`**
- Type: Counter
- Labels: `tenant_id`, `memory_tier`
- Description: Number of successful weighting operations per tenant per memory tier.
- Expected Behavior:
  - High-activity tenants: 100+ per day
  - Low-activity tenants: < 10 per day

**Metric: `weight_update_skipped`**
- Type: Counter
- Labels: `tenant_id`, `memory_tier`
- Description: Number of weighting operations skipped due to threshold not being met.
- Expected Behavior:
  - Proportional to action count below threshold
  - Should decrease as tenants perform more actions

**Metric: `session_action_count`**
- Type: Gauge
- Labels: `tenant_id`, `session_id`
- Description: Current session action count per tenant.
- Expected Behavior:
  - Low-activity tenants: peaks around 1-5 per session
  - High-activity tenants: peaks around 10-100+ per session

**Metric: `weighting_policy_enabled`**
- Type: Gauge (boolean)
- Labels: none
- Description: Whether action-scaled weighting is enabled in this deployment.
- Expected Behavior: 0 (disabled) or 1 (enabled)

### 3.2 Log Queries

**Search for all weighting skips in a time window:**
```
resource.type="cloud_run"
jsonPayload.message=~"weight_update_skipped.*"
timestamp>="2026-06-01T00:00:00Z" AND timestamp<="2026-06-02T00:00:00Z"
```

**Search for weighting triggers by tenant:**
```
resource.type="cloud_run"
jsonPayload.message=~"LogOddsWeight.*"
jsonPayload.tenant_id="my_tenant"
```

**Compare weighting frequency across tenant cohorts:**
```
SELECT
  jsonPayload.tenant_id,
  COUNT(*) as weight_updates,
  COUNT(DISTINCT jsonPayload.session_id) as unique_sessions
FROM `project.dataset.cloud_run_logs`
WHERE jsonPayload.message LIKE "%weight_update%"
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
GROUP BY tenant_id
ORDER BY weight_updates DESC
```

### 3.3 Dashboards

Create a Grafana or Google Cloud Console dashboard with:

1. **Weighting Trigger Rate by Tenant**
   - X-axis: Time
   - Y-axis: Updates per minute
   - Series: One line per tenant cohort (high-volume, medium-volume, low-volume)

2. **Session Action Count Distribution**
   - X-axis: Action count buckets (0-1, 1-5, 5-10, 10-50, 50+)
   - Y-axis: Number of sessions
   - Grouped by tenant cohort

3. **Weighting Skip Rate**
   - X-axis: Time
   - Y-axis: Percentage of operations skipped
   - Trend: Should decrease over time as tenants perform more actions

4. **Weighting Configuration Status**
   - Display current settings (enabled, threshold)
   - Alert if configuration drifts

---

## 4. Troubleshooting

### 4.1 Issue: Weighting Updates Not Being Applied

**Symptom:** Logs show "weight_update_skipped" for all tenants, or no weighting logs at all.

**Diagnosis:**

1. **Check if weighting is enabled:**
   ```bash
   grep -A 2 "weighting:" config.yaml | grep enabled
   ```
   Expected: `enabled: true`

2. **Check if tenants are meeting the threshold:**
   ```
   SELECT
     tenant_id,
     MAX(session_action_count) as max_action_count
   FROM memory_nodes
   GROUP BY tenant_id
   LIMIT 10
   ```
   Expected: At least some tenants with `max_action_count >= action_count_threshold`

3. **Check application logs for errors:**
   ```
   grep -i "error\|exception" application.log | grep -i weight
   ```

**Resolution:**

- If `enabled: false`, set to `true` and redeploy.
- If threshold is too high (e.g., 100), lower it to 3-5 and monitor behavior.
- If errors are present, check authorization and database connectivity.

### 4.2 Issue: Weighting Too Frequent (High Compute Cost)

**Symptom:** `weight_update_triggered` counter is extremely high; database CPU is elevated.

**Diagnosis:**

1. **Check the threshold:**
   ```bash
   grep -A 2 "weighting:" config.yaml | grep threshold
   ```
   If `threshold: 1` or `threshold: 2`, it's too aggressive.

2. **Measure actual action rate:**
   ```
   SELECT
     tenant_id,
     COUNT(DISTINCT session_id) as sessions,
     AVG(session_action_count) as avg_actions_per_session
   FROM memory_nodes
   WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
   GROUP BY tenant_id
   ORDER BY avg_actions_per_session DESC
   ```

**Resolution:**

- Increase threshold to 5-10 for high-activity tenants.
- Use environment-specific configs (higher thresholds in Prod).
- Consider disabling weighting temporarily and monitoring impact on memory quality.

### 4.3 Issue: Some Tenants Never Trigger Weighting

**Symptom:** Low-activity tenants consistently show "weight_update_skipped"; no weight updates ever.

**Diagnosis:**

1. **Expected behavior:** Low-activity tenants perform < threshold actions per session.
   ```
   SELECT
     tenant_id,
     COUNT(*) as action_count
   FROM memory_nodes
   WHERE tenant_id IN ('low_activity_tenant_1', 'low_activity_tenant_2')
   GROUP BY tenant_id
   ```

2. **Verify threshold:** If action count is consistently low, this is expected.

**Resolution:**

This is not an issue—it's expected behavior for low-activity tenants. Weighting is only triggered when action count reaches or exceeds the threshold. To increase weighting frequency for these tenants:
- Lower the threshold in their deployment config.
- Or, move them to a different deployment with a lower threshold.

---

## 5. Rollout Strategy

### 5.1 Shadow Mode (Testing)

1. **Deploy with weighting disabled** in a test environment:
   ```yaml
   governance:
     weighting:
       enabled: false
   ```

2. **Verify baseline behavior:**
   - No weighting skips should appear in logs
   - Tenant action counts should be tracked but not affect weights

3. **Monitor for 24 hours** to ensure stability.

### 5.2 Canary Rollout (1% of Traffic)

1. **Deploy with weighting enabled** in a small-scale canary environment:
   ```yaml
   governance:
     weighting:
       enabled: true
       action_count_threshold: 3
   ```

2. **Monitor key metrics:**
   - Weight update frequency
   - Memory quality (grounding rate)
   - Query latency
   - Database contention

3. **Compare against control:**
   - Weight metrics should show ~33% of actions triggering weighting (1/3 cross threshold).
   - Memory quality should improve slightly (but may not be statistically significant in 24 hours).
   - No latency regression expected.

4. **Proceed to 10% if metrics look healthy** for 24 hours.

### 5.3 Production Rollout (100%)

1. **Increase deployment percentage** gradually (10% → 50% → 100%) over 3 days.
2. **Monitor cumulative metrics** for anomalies.
3. **Have rollback plan ready:** Set `enabled: false` and redeploy if issues arise.

---

## 6. Tuning Recommendations

### 6.1 Threshold Tuning by Tenant Tier

| Tenant Tier | Expected Actions/Day | Recommended Threshold |
|-------------|----------------------|----------------------|
| Free        | 100-500              | 2                    |
| Starter     | 500-2,000            | 3                    |
| Professional| 2,000-10,000         | 5                    |
| Enterprise  | 10,000+              | 10                   |

### 6.2 Periodic Review

Every 2 weeks, review:
1. **Weighting trigger rate** by tenant cohort.
2. **Memory quality metrics** (grounding rate, fact reuse rate).
3. **Database performance** (CPU, latency, contention).
4. **Cost per weighting operation**.

Adjust threshold if:
- Weighting frequency is > 2x expected.
- Memory quality plateau has been reached.
- Database CPU is elevated (> 70%) during peak hours.

---

## 7. Rollback Procedure

If weighting causes issues (e.g., high latency, memory quality degradation):

```bash
# 1. Disable weighting immediately
kubectl set env deployment/memory-api \
  GOVERNANCE__WEIGHTING__ENABLED=false

# 2. Monitor logs for graceful shutdown of in-flight updates
kubectl logs -f deployment/memory-api | grep weight_update

# 3. Verify action counts continue to be tracked (for future re-enablement)
# 4. Create incident post-mortem and file follow-up bug
```

Typical rollback time: **< 5 minutes**

---

## 8. FAQ

**Q: Why does weighting trigger only after 3 actions?**
A: The threshold of 3 is a tunable default chosen to balance weighting frequency with compute cost. Adjust per your deployment's activity patterns.

**Q: Can I have different thresholds per memory tier?**
A: Currently, the threshold is global. Future phase may allow per-tier or per-label thresholds.

**Q: What happens if session action count resets?**
A: Counters are session-scoped. A new session starts with a count of 0.

**Q: Is weighting retroactive to past sessions?**
A: No. Weighting is only applied to nodes accessed in the current session when the threshold is crossed.

**Q: How do I monitor fairness between tenants?**
A: Use the "Weighting Trigger Rate by Tenant" dashboard. High-volume tenants should show 3-10x more triggers than low-volume tenants (proportional to activity).

---

## 9. References

- **DEVELOPMENT_PLAN.md**: Phase 1 goals and success criteria
- **src/security/governance.py**: `WeightingTriggerPolicy` implementation
- **src/memory/api.py**: `_update_weight_on_successful_use()` implementation
- **tests/load/test_comparative_weighting.py**: Comparative load tests
