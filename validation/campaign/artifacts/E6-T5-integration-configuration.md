# E6-T5 — Integration Configuration and Credential Setup

**Epic:** E6 — Cloud Data Provisioning and Integration Bring-up
**Task:** E6-T5
**Date:** 2026-07-19
**Status:** Approved
**Owner:** Backend Engineer

---

## 1. Objective

Configure mandatory integrations (Slack, Google Calendar, Jira, GitHub) from frozen specs (E2-T3, E2-T4) and test credential access patterns. Populate Cloud Run environment variables and verify end-to-end integration connectivity.

**Dependencies:** E2-T3 (integration inventory), E2-T4 (OAuth specs), E5-T5 (secrets stored), E5-T8 (Cloud Run deployed)

---

## 2. Integration Matrix (Frozen from E2-T3)

| Integration | Purpose | Auth Method | Secrets | Config Env Vars | Status |
|-------------|---------|------------|---------|-----------------|--------|
| **Slack** | Notifications, escalations | OAuth 2.0 Bot | slack-bot-token | SLACK_BOT_TOKEN, SLACK_CHANNEL_ALERTS | ☐ |
| **Google Calendar** | Schedule meetings, track availability | OAuth 2.0 (SA) | calendar-service-account-key | CALENDAR_CALENDAR_ID, CALENDAR_SA_EMAIL | ☐ |
| **Jira** | Ticket creation, issue tracking | API Token | jira-api-token | JIRA_BASE_URL, JIRA_PROJECT_KEY, JIRA_API_TOKEN | ☐ |
| **GitHub** | Source control, issue tracking (backup) | Personal Access Token | github-oauth-token | GITHUB_REPO, GITHUB_BRANCH, GITHUB_TOKEN | ☐ |

---

## 3. Integration Configuration Details

### 3.1 Slack Configuration

**Secret:** slack-bot-token (stored in Secret Manager)

**Environment Variables:**
```bash
SLACK_BOT_TOKEN=xoxb-[token]          # From Secret Manager
SLACK_CHANNEL_ALERTS=C06XXXXXX         # Channel ID for campaign alerts
SLACK_CHANNEL_ESCALATIONS=C07XXXXXX    # Channel ID for critical escalations
SLACK_WORKSPACE_ID=T01XXXXXX           # Workspace ID
```

**Python Integration (Cloud Run):**
```python
import os
from google.cloud import secretmanager
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class SlackIntegration:
    def __init__(self):
        """Initialize Slack bot with token from Secret Manager."""
        secret_client = secretmanager.SecretManagerServiceClient()
        secret_name = f"projects/{os.environ['PROJECT_ID']}/secrets/slack-bot-token/versions/latest"
        response = secret_client.access_secret_version(request={"name": secret_name})
        token = response.payload.data.decode("UTF-8")
        self.client = WebClient(token=token)
        self.alerts_channel = os.environ.get('SLACK_CHANNEL_ALERTS')

    def send_campaign_alert(self, message: str, severity: str = "info"):
        """Send alert to Slack."""
        try:
            response = self.client.chat_postMessage(
                channel=self.alerts_channel,
                text=f"[{severity.upper()}] {message}",
                metadata={
                    "event_type": "campaign_alert",
                    "event_payload": {"campaign_id": "amg-validation-2026-q3"}
                }
            )
            return {"status": "sent", "ts": response['ts']}
        except SlackApiError as e:
            raise RuntimeError(f"Slack API error: {e.response['error']}")

# Test
slack = SlackIntegration()
slack.send_campaign_alert("E6 data provisioning started", severity="info")
```

### 3.2 Google Calendar Configuration

**Secret:** calendar-service-account-key (JSON file in Secret Manager)

**Environment Variables:**
```bash
CALENDAR_CALENDAR_ID=c_XXXXXX%40group.calendar.google.com  # Campaign calendar
CALENDAR_SA_EMAIL=sa-calendar@amg-validation-2026-07-q3.iam.gserviceaccount.com
GOOGLE_APPLICATION_CREDENTIALS=/tmp/calendar-sa-key.json  # Mounted secret
```

**Python Integration (Cloud Run):**
```python
import os
import json
from google.cloud import secretmanager
from google.oauth2 import service_account
from googleapiclient.discovery import build

class GoogleCalendarIntegration:
    def __init__(self):
        """Initialize Google Calendar with SA key from Secret Manager."""
        secret_client = secretmanager.SecretManagerServiceClient()
        secret_name = f"projects/{os.environ['PROJECT_ID']}/secrets/calendar-service-account-key/versions/latest"
        response = secret_client.access_secret_version(request={"name": secret_name})
        sa_key = json.loads(response.payload.data.decode("UTF-8"))

        credentials = service_account.Credentials.from_service_account_info(
            sa_key,
            scopes=['https://www.googleapis.com/auth/calendar']
        )
        self.service = build('calendar', 'v3', credentials=credentials)
        self.calendar_id = os.environ.get('CALENDAR_CALENDAR_ID')

    def create_campaign_event(self, summary: str, start_time: str, end_time: str):
        """Create calendar event for campaign milestone."""
        try:
            event = {
                'summary': summary,
                'description': 'Cognitive Agent Memory Graph validation campaign event',
                'start': {'dateTime': start_time, 'timeZone': 'UTC'},
                'end': {'dateTime': end_time, 'timeZone': 'UTC'},
                'attendees': [
                    {'email': 'product-team@example.com'},
                    {'email': 'data-lead@example.com'}
                ]
            }
            result = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()
            return {"status": "created", "event_id": result['id']}
        except Exception as e:
            raise RuntimeError(f"Calendar API error: {str(e)}")

# Test
calendar = GoogleCalendarIntegration()
calendar.create_campaign_event(
    "E6 Complete - Data Provisioning Finished",
    "2026-07-19T18:00:00Z",
    "2026-07-19T18:30:00Z"
)
```

### 3.3 Jira Configuration

**Secret:** jira-api-token (stored in Secret Manager)

**Environment Variables:**
```bash
JIRA_BASE_URL=https://latam.atlassian.net
JIRA_PROJECT_KEY=AMGVAL
JIRA_API_TOKEN=ATATT[token]  # From Secret Manager
JIRA_REPORTER_EMAIL=amg-validation@latam.com
```

**Python Integration (Cloud Run):**
```python
import os
import base64
from google.cloud import secretmanager
import requests

class JiraIntegration:
    def __init__(self):
        """Initialize Jira client with API token from Secret Manager."""
        secret_client = secretmanager.SecretManagerServiceClient()
        secret_name = f"projects/{os.environ['PROJECT_ID']}/secrets/jira-api-token/versions/latest"
        response = secret_client.access_secret_version(request={"name": secret_name})
        self.api_token = response.payload.data.decode("UTF-8")
        self.base_url = os.environ.get('JIRA_BASE_URL')
        self.project_key = os.environ.get('JIRA_PROJECT_KEY')
        self.reporter_email = os.environ.get('JIRA_REPORTER_EMAIL')

    def create_issue(self, summary: str, description: str, issue_type: str = "Task"):
        """Create a Jira issue."""
        try:
            auth = base64.b64encode(
                f"{self.reporter_email}:{self.api_token}".encode()
            ).decode()

            headers = {
                'Authorization': f'Basic {auth}',
                'Content-Type': 'application/json'
            }

            payload = {
                'fields': {
                    'project': {'key': self.project_key},
                    'summary': summary,
                    'description': description,
                    'issuetype': {'name': issue_type},
                    'labels': ['amg-campaign', 'validation-2026']
                }
            }

            response = requests.post(
                f'{self.base_url}/rest/api/3/issues',
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            return {"status": "created", "issue_key": result['key']}
        except Exception as e:
            raise RuntimeError(f"Jira API error: {str(e)}")

# Test
jira = JiraIntegration()
jira.create_issue(
    "E6 Data Provisioning Complete",
    "All datasets provisioned, 37 DQ checks passed, ready for E7 benchmark runs"
)
```

### 3.4 GitHub Configuration

**Secret:** github-oauth-token (stored in Secret Manager)

**Environment Variables:**
```bash
GITHUB_REPO=bmatonte-t/agent-memory-graph
GITHUB_BRANCH=develop
GITHUB_TOKEN=[token]  # From Secret Manager
```

**Python Integration (Cloud Run):**
```python
import os
from google.cloud import secretmanager
from github import Github

class GitHubIntegration:
    def __init__(self):
        """Initialize GitHub client with PAT from Secret Manager."""
        secret_client = secretmanager.SecretManagerServiceClient()
        secret_name = f"projects/{os.environ['PROJECT_ID']}/secrets/github-oauth-token/versions/latest"
        response = secret_client.access_secret_version(request={"name": secret_name})
        token = response.payload.data.decode("UTF-8")
        self.github = Github(token)
        self.repo_name = os.environ.get('GITHUB_REPO')
        self.repo = self.github.get_repo(self.repo_name)

    def create_issue(self, title: str, body: str, labels: list = None):
        """Create a GitHub issue."""
        try:
            issue = self.repo.create_issue(
                title=title,
                body=body,
                labels=labels or []
            )
            return {"status": "created", "issue_number": issue.number}
        except Exception as e:
            raise RuntimeError(f"GitHub API error: {str(e)}")

# Test
github = GitHubIntegration()
github.create_issue(
    "E6 Complete - Ready for E7 Benchmark Runs",
    "Data provisioning finished. All systems healthy. Ready to begin measured agent runs.",
    labels=["epic-06", "validation-2026", "ready-for-testing"]
)
```

---

## 4. Cloud Run Integration Configuration

### 4.1 Environment Variables Manifest

```yaml
# deploy/cloud-run-env.yaml
env_vars:
  # Campaign context
  PROJECT_ID: amg-validation-2026-07-q3
  CAMPAIGN_ID: amg-validation-2026
  TENANT_ID: campaign-validation-2026-q3

  # Spanner
  SPANNER_INSTANCE: amg-campaign-spanner
  SPANNER_DATABASE: memory_db

  # BigQuery
  BQ_DATASET_RAW: raw_retail_public
  BQ_DATASET_CURATED: curated_retail_campaign
  BQ_DATASET_BENCHMARK: benchmark_metrics

  # GCS
  CORPUS_BUCKET: amg-campaign-corpus-q3

  # Integrations
  SLACK_BOT_TOKEN: "{{SECRET:slack-bot-token}}"
  SLACK_CHANNEL_ALERTS: C06XXXXXX
  SLACK_CHANNEL_ESCALATIONS: C07XXXXXX

  CALENDAR_CALENDAR_ID: "c_XXXXXX%40group.calendar.google.com"
  CALENDAR_SA_EMAIL: "sa-calendar@amg-validation-2026-07-q3.iam.gserviceaccount.com"

  JIRA_BASE_URL: "https://latam.atlassian.net"
  JIRA_PROJECT_KEY: AMGVAL
  JIRA_API_TOKEN: "{{SECRET:jira-api-token}}"
  JIRA_REPORTER_EMAIL: "amg-validation@latam.com"

  GITHUB_REPO: "bmatonte-t/agent-memory-graph"
  GITHUB_BRANCH: "develop"
  GITHUB_TOKEN: "{{SECRET:github-oauth-token}}"

  # Logging
  LOG_LEVEL: INFO
  TRACE_ENABLED: "true"
```

### 4.2 Deployment Script

```bash
#!/bin/bash
# deploy_integrations.sh

set -e

PROJECT_ID="amg-validation-2026-07-q3"
SERVICE_NAME="amg-campaign-agents"
REGION="us-central1"

echo "Deploying Cloud Run service with integration configuration..."

# Read env vars from manifest
gcloud run deploy $SERVICE_NAME \
  --project=$PROJECT_ID \
  --region=$REGION \
  --env-vars-file=deploy/cloud-run-env.yaml \
  --update-secrets=SLACK_BOT_TOKEN=slack-bot-token:latest,\
CALENDAR_SA_KEY=calendar-service-account-key:latest,\
JIRA_API_TOKEN=jira-api-token:latest,\
GITHUB_TOKEN=github-oauth-token:latest \
  --no-gen2

echo "✓ Cloud Run service updated with integration configuration"
```

---

## 5. Integration Connectivity Tests

### 5.1 Test Suite (Python)

```python
# test_integrations.py
import asyncio
import os
from slack import SlackIntegration
from calendar_client import GoogleCalendarIntegration
from jira_client import JiraIntegration
from github_client import GitHubIntegration

async def test_all_integrations():
    """Test each integration's connectivity and auth."""
    results = {
        "slack": None,
        "calendar": None,
        "jira": None,
        "github": None
    }

    # Test Slack
    try:
        slack = SlackIntegration()
        slack.send_campaign_alert("Integration test: Slack connectivity check", severity="info")
        results["slack"] = {"status": "PASS", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        results["slack"] = {"status": "FAIL", "error": str(e)}

    # Test Google Calendar
    try:
        calendar = GoogleCalendarIntegration()
        calendar.create_campaign_event(
            "Integration Test Event",
            "2026-07-19T14:00:00Z",
            "2026-07-19T14:30:00Z"
        )
        results["calendar"] = {"status": "PASS", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        results["calendar"] = {"status": "FAIL", "error": str(e)}

    # Test Jira
    try:
        jira = JiraIntegration()
        jira.create_issue(
            "E6-T5 Integration Test",
            "Testing Jira integration connectivity for E6"
        )
        results["jira"] = {"status": "PASS", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        results["jira"] = {"status": "FAIL", "error": str(e)}

    # Test GitHub
    try:
        github = GitHubIntegration()
        github.create_issue(
            "E6-T5 Integration Test",
            "Testing GitHub integration connectivity for E6",
            labels=["integration-test"]
        )
        results["github"] = {"status": "PASS", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        results["github"] = {"status": "FAIL", "error": str(e)}

    return results

# Execute tests
if __name__ == "__main__":
    test_results = asyncio.run(test_all_integrations())

    print("\n=== Integration Connectivity Report ===")
    all_pass = True
    for integration, result in test_results.items():
        status = result.get("status", "UNKNOWN")
        print(f"{integration.upper()}: {status}")
        if status != "PASS":
            print(f"  Error: {result.get('error', 'Unknown error')}")
            all_pass = False

    if all_pass:
        print("\n✓ All integrations connected and operational")
    else:
        print("\n✗ Some integrations failed; see details above")
        exit(1)
```

---

## 6. Configuration Deployment Plan

### 6.1 Day 1: Secret Verification and Setup

```
09:00 — Verify all 4 secrets stored in Secret Manager (check versions)
10:00 — Test secret access from local environment
11:00 — Confirm IAM permissions (amg-campaign-svc can access secrets)
12:00 — CHECKPOINT: Secrets accessible
```

### 6.2 Day 2: Cloud Run Deployment

```
09:00 — Update Cloud Run environment variables from manifest
10:00 — Mount secrets as environment variables
11:00 — Redeploy Cloud Run service
12:00 — CHECKPOINT: Cloud Run updated
```

### 6.3 Day 3: Integration Testing

```
09:00 — Run integration connectivity tests (all 4 integrations)
10:00 — Verify Slack message appears in alerts channel
11:00 — Verify Google Calendar event created
12:00 — Verify Jira issue created in AMGVAL project
13:00 — Verify GitHub issue created in bmatonte-t/agent-memory-graph
14:00 — CHECKPOINT: All 4 integrations operational
```

---

## 7. Quality Checklist

| Check | Status | Expected |
|-------|--------|----------|
| All 4 secrets stored in Secret Manager | ☐ | ✓ Verified |
| Environment variables configured | ☐ | ✓ All 20+ vars set |
| Cloud Run deployed with env vars | ☐ | ✓ Service restarted |
| Slack connectivity test passed | ☐ | ✓ Alert message sent |
| Calendar connectivity test passed | ☐ | ✓ Event created |
| Jira connectivity test passed | ☐ | ✓ Issue created |
| GitHub connectivity test passed | ☐ | ✓ Issue created |

---

## 8. Cost Estimate (E6-T5)

| Resource | Quantity | Unit Cost | Total |
|----------|----------|-----------|-------|
| Secret Manager API calls | ~10 | $0.06/10k | Negligible |
| Slack API calls | ~5 | Free (included) | $0.00 |
| Calendar API calls | ~2 | Free (included) | $0.00 |
| Jira API calls | ~5 | Free (included) | $0.00 |
| GitHub API calls | ~5 | Free (included) | $0.00 |
| **Total (E6-T5)** | — | — | **~$0.00** |

**Budget Impact:** Week 5 integrations budget: $2 (mostly for verification); $0.00 utilization

---

## 9. Sign-Off

| Role | Owner | Sign-Off | Date |
|------|-------|----------|------|
| Backend Engineer | D. Williams | ☐ | ____ |
| Infrastructure Lead | T. Chen | ☐ | ____ |
| Program Manager | S. Gupta | ☐ | ____ |
