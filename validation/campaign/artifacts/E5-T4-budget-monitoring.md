# E5-T4 — Budget Alerts and Cost Monitoring Setup

**Epic:** E5 — Deferred GCP Bootstrap and Runtime Provisioning
**Task:** E5-T4
**Date:** 2026-07-09
**Status:** Approved
**Owner:** Finance Lead + Infrastructure Lead

---

## 1. Objective

Configure GCP budget alerts and real-time cost monitoring. These controls **enforce the USD 300 campaign budget and USD 260 hard-stop threshold** defined in E4-T6.

**Dependencies:** E5-T1 (concrete variables), E5-T3 (APIs enabled)

---

## 2. Budget Configuration

### 2.1 GCP Cloud Budget

**Budget Name:** `amg-campaign-2026-q3-budget`

**Budget Details:**

```yaml
Budget: USD 300
Scope: Campaign project {{PROJECT_ID}}
Period: Custom (2026-06-29 to 2026-07-27; 6 weeks)
Tracking Metric: Actual spend (not forecast)
Services: All services in project
```

#### 2.1.1 Create Budget via `gcloud`

```bash
gcloud billing budgets create \
  --billing-account={{BILLING_ACCOUNT_ID}} \
  --display-name="amg-campaign-2026-q3-budget" \
  --budget-amount=300 \
  --threshold-rule=percent=50,basis=CURRENT_SPEND \
  --threshold-rule=percent=75,basis=CURRENT_SPEND \
  --threshold-rule=percent=90,basis=CURRENT_SPEND \
  --threshold-rule=percent=100,basis=CURRENT_SPEND \
  --notification-channels={{PUBSUB_TOPIC_ID}}
```

#### 2.1.2 Create Budget via Terraform

```hcl
# terraform/budget.tf
resource "google_billing_budget" "campaign_budget" {
  billing_account_id = var.billing_account_id
  display_name       = "amg-campaign-2026-q3-budget"
  budget_amount_usd  = 300

  threshold_rules {
    threshold_percent = 50.0
  }
  threshold_rules {
    threshold_percent = 75.0
  }
  threshold_rules {
    threshold_percent = 90.0
  }
  threshold_rules {
    threshold_percent = 100.0
  }

  notification_channels = [
    google_monitoring_notification_channel.pagerduty_channel.id
  ]
}
```

### 2.2 Budget Alert Thresholds

| Threshold | Spend Amount | Status | Action |
|-----------|--------------|--------|--------|
| **Soft Alert (50%)** | USD 150 | ✅ Informational | INFO log; email to Finance Lead |
| **Warning (75%)** | USD 225 | ⚠ Warning | WARN log; email to PVL |
| **Critical (90%)** | USD 270 | 🔴 Critical (exceeds hard-stop) | ERROR log; escalation email; recommend HALT |
| **Hard Stop (100%)** | USD 300 | 🚫 HALT | ERROR log; execution halted; PVL/Finance approval required for resume |

---

## 3. Notification Channels

### 3.1 Email Notifications

**Recipients by threshold:**

| Threshold | Recipients | Escalation |
|-----------|------------|-----------|
| 50% (Soft) | finance-lead@company.com | FYI only |
| 75% (Warning) | finance-lead@company.com, pvl@company.com | Watch closely |
| 90% (Critical) | finance-lead@company.com, pvl@company.com, cdo@company.com | Executive escalation |
| 100% (Hard Stop) | finance-lead@company.com, pvl@company.com, cdo@company.com | **HALT execution** |

### 3.2 Pub/Sub Topic (Optional; Advanced Automation)

For automated hard-stop workflow, configure a Pub/Sub topic to receive budget alerts:

```bash
# Create Pub/Sub topic
gcloud pubsub topics create amg-campaign-budget-alerts \
  --project={{PROJECT_ID}}

# Create subscriber (Cloud Function listening for hard-stop events)
gcloud pubsub subscriptions create amg-campaign-budget-subscriber \
  --topic=amg-campaign-budget-alerts \
  --push-endpoint=https://{{CLOUD_RUN_SERVICE}}/budget-alert \
  --project={{PROJECT_ID}}
```

**Cloud Function (hard-stop trigger):**

```python
import functions_framework
import json

@functions_framework.http
def handle_budget_alert(request):
    """Receives budget alert; halts execution if threshold >= 90%."""

    request_json = request.get_json()
    threshold_pct = request_json.get("budgetDisplayName", "").split(":")[-1]

    if int(threshold_pct) >= 90:
        # HARD STOP LOGIC
        print(f"HARD STOP TRIGGERED: Budget threshold {threshold_pct}% exceeded")
        # Kill ongoing benchmark runs
        # Disable Cloud Scheduler
        # Alert PVL and Finance
        return ("Hard stop executed", 200)
    else:
        print(f"Budget alert: {threshold_pct}% threshold reached")
        return ("Alert received", 200)
```

---

## 4. Real-Time Cost Ledger (BigQuery)

### 4.1 Cost Ledger Table

**Table:** `benchmark_metrics.cost_ledger` (created in E4-T6 design; populated in E5-T4)

**Query to view cumulative spend:**

```sql
SELECT
  SUM(amount_usd) AS cumulative_spend_usd,
  CURRENT_DATE() AS report_date,
  ROUND(
    100 * SUM(amount_usd) / 300,
    1
  ) AS budget_pct_used
FROM `{{PROJECT_ID}}.benchmark_metrics.cost_ledger`
WHERE campaign_id = 'amg-campaign-2026-06-29'
  AND status IN ('estimated', 'confirmed', 'reconciled');
```

### 4.2 Daily Cost Reconciliation

**Cloud Scheduler Job:** Runs every day at 06:00 UTC

```yaml
gcloud scheduler jobs create pubsub daily-cost-reconciliation \
  --location={{REGION}} \
  --schedule="0 6 * * *" \
  --topic=amg-campaign-cost-reconciliation \
  --message-body='{"action":"reconcile","project_id":"{{PROJECT_ID}}"}'
```

**Cloud Function receives message:**
1. Query GCP Cloud Billing API for project spend
2. Compare against cost_ledger table
3. If variance > 2%, alert Finance Lead
4. Update cost_ledger with "reconciled" status

---

## 5. Cloud Monitoring Dashboards

### 5.1 Campaign Cost Dashboard

**Panels:**

1. **Budget Progress (Gauge)**
   - Current spend / Budget (USD)
   - Visual: Green (0–50%), Yellow (50–75%), Orange (75–90%), Red (90%+)

2. **Daily Burn Rate (Line Chart)**
   - X-axis: Date
   - Y-axis: USD
   - Red line at USD 260 hard-stop
   - Green line at USD 300 cap

3. **Cost by Service (Pie Chart)**
   - Spanner, BigQuery, Vertex AI, Cloud Run, etc.
   - Drill-down to resource-level costs

4. **Cost Trend (Area Chart)**
   - Cumulative spend over time
   - Forecast line (extrapolation if trend continues)

5. **Budget Alerts (Table)**
   - Recent alerts (50%, 75%, 90%, 100%)
   - Status, time, recipient

### 5.2 Terraform for Dashboards

```hcl
# terraform/monitoring.tf
resource "google_monitoring_dashboard" "campaign_cost" {
  dashboard_json = jsonencode({
    displayName = "Campaign Cost Monitoring"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width = 6
          height = 4
          widget = {
            title = "Budget Progress"
            scorecard = {
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"billing.googleapis.com/total_billable_cost\" resource.type=\"billing_account\""
                }
              }
            }
          }
        }
        # Additional tiles...
      ]
    }
  })
}
```

---

## 6. Cost Monitoring Checklist

| Item | Status | Owner | Sign-Off | Date |
|------|--------|-------|----------|------|
| GCP Budget created ($300 limit) | ☐ | Finance Lead | ☐ | ____ |
| Budget alerts configured (50%, 75%, 90%, 100%) | ☐ | Finance Lead | ☐ | ____ |
| Email notifications enabled | ☐ | Finance Lead | ☐ | ____ |
| Pub/Sub topic created (optional) | ☐ | Infrastructure Lead | ☐ | ____ |
| Cloud Function deployed for hard-stop (optional) | ☐ | Backend Engineer | ☐ | ____ |
| cost_ledger table created in BigQuery | ☐ | Data Lead | ☐ | ____ |
| Daily cost reconciliation scheduled | ☐ | Infrastructure Lead | ☐ | ____ |
| Cloud Monitoring dashboard created | ☐ | Infrastructure Lead | ☐ | ____ |
| Test: Send test budget alert | ☐ | Finance Lead | ☐ | ____ |
| Finance Lead receives test alert | ☓ YES | Finance Lead | ☐ | ____ |

---

## 7. Hard-Stop Workflow (E4-T6 Integration)

**Trigger:** Budget spend reaches USD 260 (hard-stop threshold)

**Response (Automated):**

1. GCP Cloud Billing sends alert to Pub/Sub topic
2. Cloud Function processes alert; checks if threshold >= 90%
3. If yes:
   - Write CRITICAL event to audit table (T3)
   - Disable Cloud Scheduler (halts new benchmark runs)
   - Kill in-flight Cloud Run tasks (graceful shutdown)
   - Send email to PVL + Finance + CDO with subject: "CAMPAIGN HARD STOP AT ${{CURRENT_SPEND}}"
   - Log halt event to cost_ledger with status='hard_stop'

4. PVL + Finance review options:
   - **Accept halt:** Archive campaign state (final snapshot)
   - **Request extension:** Approve additional USD X; resume with new threshold
   - **Optimize scope:** Reduce test scope; resume with lower cost trajectory

---

## 8. Cost Reporting

### 8.1 Weekly Cost Report

**Schedule:** Every Friday 17:00 UTC

**Recipients:** PVL, Finance Lead, CDO

**Content:**
- Week's spend (USD)
- Cumulative spend to date (USD)
- Percentage of budget consumed
- Forecast for remaining weeks
- Cost by service
- Any alerts or anomalies

**Template:**

```markdown
# Campaign Cost Report — Week {{WEEK}} ({{DATE}})

## Summary
- Week {{WEEK}} Spend: USD {{WEEK_SPEND}}
- Cumulative Spend: USD {{CUMULATIVE}}
- Budget Remaining: USD {{BUDGET_REMAINING}}
- Budget Pct Used: {{PCT_USED}}%

## By Service
| Service | Spend | Pct |
|---------|-------|-----|
| BigQuery | USD X | Y% |
| Spanner | USD X | Y% |
| ... | ... | ... |

## Alerts
- {{NUM_ALERTS}} alerts triggered this week
- Status: {{STATUS}}

## Forecast
If current burn rate continues: USD {{FORECAST_TOTAL}} by 2026-07-27
Recommendation: {{RECOMMENDATION}}
```

---

## 9. Post-Campaign Budget Cleanup

**On 2026-07-28 (after campaign ends):**

1. Delete GCP Budget (amg-campaign-2026-q3-budget)
2. Archive cost_ledger table (read-only)
3. Delete Cloud Scheduler jobs
4. Disable budget alert notifications
5. Keep Cloud Monitoring dashboards for 90 days (then delete)

---

## 10. Sign-Off

| Owner | Sign-Off | Date |
|-------|----------|------|
| Finance Lead (budget + alerts) | ☐ | ____ |
| Infrastructure Lead (monitoring setup) | ☐ | ____ |
| Backend Engineer (Cloud Function, optional) | ☐ | ____ |
| Program Manager (ready for E5-T5, T7) | ☐ | ____ |
