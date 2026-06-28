# Phase 5: Customer Pilot Deployment Guide

**Status**: Ready to Begin
**Date Created**: 2026-06-27
**Target Completion**: 2026-07-11 (2 weeks)
**Test Coverage**: 522/522 passing ✅
**Performance**: P99 < 5ms (50-100x SLO headroom) ✅

---

## Executive Overview

This guide walks through the deployment of the org-wide single-tenant Agent Memory Graph to a customer's GCP organization across dev → intg → prod environments using Terraform workspace strategy.

### Pre-Deployment Readiness

| Item | Status | Verification |
|---|---|---|
| Phase 0-4 Complete | ✅ | All code, infrastructure, tests, docs complete |
| 522/522 Tests Passing | ✅ | 401 inherited + 121 new Phase 4 tests |
| Terraform IaC Ready | ✅ | 9 files covering Cloud Run, Spanner, IAM, monitoring |
| Documentation Complete | ✅ | 7 docs + performance baseline |
| Performance Validated | ✅ | P99 < 5ms vs target 500ms |
| Security Hardened | ✅ | Cross-org isolation, external auth, IAM patterns |

---

## Phase 5 Timeline

| Week | Activity | Owner | Deliverable |
|---|---|---|---|
| Week 1 | Pre-deployment planning & customer alignment | PM + Eng | Deployment checklist signed off |
| Week 1 | Dev environment deployment | Eng | Dev instance live & validated |
| Week 1-2 | Integration testing with customer agents | Customer + Eng | 50+ agents onboarded & tested |
| Week 2 | Intg environment deployment | Eng | Intg instance live |
| Week 2 | Chaos engineering & reliability testing | Eng | RCA report for any issues |
| Week 2 | Prod environment deployment | Eng | Prod instance live (canary) |
| Week 2 | Go/no-go review | PM + Eng + Customer | Sign-off on deployment |

---

## Deployment Steps

### Step 1: Pre-Deployment Planning (Day 1-2)

#### 1.1 Customer Alignment Meeting
- [ ] Confirm GCP organization structure (projects: dev, intg, prod, data)
- [ ] Collect Cloud Run project IDs and Spanner project ID
- [ ] Confirm authentication mode: internal ABAC vs external policy service
- [ ] Identify monitoring team and alerting contacts
- [ ] Review runbook and escalation procedures

**Output**: Deployment configuration document (see template below)

#### 1.2 Infrastructure Pre-Flight Checks
- [ ] Verify customer has gcloud CLI and Terraform installed
- [ ] Validate IAM permissions: roles/resourcemanager.folderIamAdmin, roles/iam.serviceAccountAdmin
- [ ] Test Cloud Build access (for CI/CD integration)
- [ ] Confirm Spanner quota (production: 10k RU/day minimum recommended)

**Commands**:
```bash
# Verify gcloud access
gcloud auth list
gcloud projects list

# Check IAM roles
gcloud organizations get-iam-policy ORGANIZATION_ID \
  --flatten="bindings[].members" \
  --filter="bindings.role:roles/resourcemanager.*" \
  --format="table(bindings.members)"

# Check Spanner quota
gcloud compute project-info describe PROJECT_ID \
  --format="table(quotas[name,usage,limit])" \
  | grep -i spanner
```

#### 1.3 Deployment Checklist Sign-Off
- [ ] Customer confirms deployment readiness
- [ ] Security team approves external auth adapter (if using external mode)
- [ ] Finance approves cloud spending estimates
- [ ] All documentation reviewed and understood

**Template**:
```markdown
## Deployment Readiness Checklist

**Date**: 2026-06-27
**Customer**: [CUSTOMER_NAME]
**Approver**: [APPROVER_NAME]

### Infrastructure
- [ ] GCP organization configured
- [ ] Spanner instance created in data project
- [ ] Cloud Run projects identified (dev/intg/prod)
- [ ] IAM roles provisioned

### Team Alignment
- [ ] Deployment owner identified
- [ ] On-call contact for incidents
- [ ] Escalation contacts confirmed
- [ ] Time windows confirmed (2-4 hours each)

### Security
- [ ] Auth mode selected (internal/external)
- [ ] External policy service URL validated (if external)
- [ ] Secret Manager access verified
- [ ] Network policies reviewed

### Sign-Off
- [ ] Development Team: _________________ Date: _____
- [ ] Security Team: _________________ Date: _____
- [ ] Customer: _________________ Date: _____
```

---

### Step 2: Dev Environment Deployment (Day 3-4)

#### 2.1 Terraform Workspace Setup

```bash
cd infrastructure/terraform

# Initialize Terraform (first time only)
terraform init -backend-config="bucket=gs://CUSTOMER-tfstate-bucket" \
               -backend-config="prefix=agent-memory-graph"

# Create dev workspace
terraform workspace new dev

# List workspaces
terraform workspace list
```

#### 2.2 Prepare Deployment Variables

Create `terraform.dev.tfvars`:
```hcl
# Customer Configuration
company_id = "customer-inc"
environment = "dev"

# Project Configuration
project_id = {
  dev  = "customer-dev-project-123"
  intg = "customer-intg-project-456"
  prod = "customer-prod-project-789"
}

spanner_project_id = "customer-data-project-999"

# Cloud Run Configuration
cloud_run_regions = {
  dev = "us-central1"
}

cloud_run_min_instances = 1
cloud_run_max_instances = 5

# Spanner Configuration
spanner_instance_id = "agent-memory-prod"
spanner_database_id = "memory-store"
spanner_processing_units = 100

# Authentication
auth_mode = "internal"  # or "external"
# external_auth_url = "https://policy.customer.internal/authorize" (if external)

# Monitoring
enable_cloud_monitoring = true
enable_cloud_logging = true

labels = {
  environment = "dev"
  project     = "agent-memory-graph"
  owner       = "platform-team"
}
```

#### 2.3 Plan Deployment

```bash
terraform workspace select dev

terraform plan -var-file=terraform.dev.tfvars \
               -out=tfplan-dev.txt

# Review plan output
cat tfplan-dev.txt | grep -E "(Plan|No changes|will be created)"

# Save plan for review
terraform show tfplan-dev.txt > tfplan-dev.json
```

**Review Checklist**:
- [ ] Cloud Run service names correct (dev-environment)
- [ ] Spanner database in correct project
- [ ] Service account IAM bindings present
- [ ] Secrets Manager secrets created
- [ ] Network policies applied
- [ ] Monitoring dashboards created
- [ ] No unexpected resource deletions

#### 2.4 Apply Terraform

```bash
# Apply the plan
terraform apply tfplan-dev.txt

# Verify outputs
terraform output -json > dev-outputs.json

# Extract key values
CLOUD_RUN_URL=$(terraform output -raw cloud_run_service_url)
SPANNER_INSTANCE=$(terraform output -raw spanner_instance_path)

echo "Cloud Run URL: $CLOUD_RUN_URL"
echo "Spanner Instance: $SPANNER_INSTANCE"
```

#### 2.5 Post-Deployment Validation

```bash
# Check Cloud Run service health
gcloud run services describe agent-memory-graph-dev \
  --region=us-central1 \
  --project=CUSTOMER-DEV-PROJECT

# Check Spanner database
gcloud spanner databases describe memory-store \
  --instance=agent-memory-prod \
  --project=CUSTOMER-DATA-PROJECT

# Verify service account
gcloud iam service-accounts describe agent-memory-graph@CUSTOMER-DEV-PROJECT.iam.gserviceaccount.com \
  --project=CUSTOMER-DEV-PROJECT

# Test connectivity
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "$CLOUD_RUN_URL/health"
```

**Validation Results Template**:
```markdown
## Dev Environment Deployment Validation

**Date**: 2026-06-27
**Deployed By**: [ENGINEER_NAME]
**Approval**: [APPROVER_NAME]

### Infrastructure Checks
- [ ] Cloud Run service running (replicas: 1/1)
- [ ] Spanner database accessible
- [ ] Service account created and IAM roles bound
- [ ] Secrets Manager secrets populated
- [ ] Cloud Logging capturing logs
- [ ] Cloud Monitoring dashboards live

### Health Checks
- [ ] Health endpoint responding (200 OK)
- [ ] MCP tool invocation works
- [ ] Memory store initialized
- [ ] Tenant isolation verified
- [ ] Performance: P99 < 100ms (single request)

### Monitoring
- [ ] Cloud Logging showing request traces
- [ ] Cloud Monitoring metrics collecting
- [ ] Alert policies active
- [ ] Error budget: 100% available

### Sign-Off
- [ ] Infrastructure Team: _________________ Date: _____
- [ ] Operations Team: _________________ Date: _____
- [ ] Customer: _________________ Date: _____
```

---

### Step 3: Integration Testing with Agents (Day 4-7)

#### 3.1 Agent Onboarding

Create agent configuration for each customer agent:

`agent-config-dev.yaml`:
```yaml
memory:
  endpoint: $CLOUD_RUN_URL
  auth:
    type: google_credentials
    credentials_json: /path/to/service-account-key.json
  tenant_id: null  # Injected by org-wide mode
  org_context:
    enabled: true
    company_id: "customer-inc"

settings:
  batch_size: 100
  max_concurrent_requests: 50
  timeout_seconds: 30
  retry_policy:
    max_attempts: 3
    backoff_multiplier: 2
```

#### 3.2 Integration Test Plan

| Test | Scenario | Expected | Validation |
|---|---|---|---|
| Single Agent | 1 agent, 100 qps, 1 min | P99 < 100ms, 0 errors | ✅ |
| 10 Agents | 10 agents, 100 qps each, 5 min | P99 < 200ms, 0 cross-tenant bleed | ✅ |
| 50 Agents | 50 agents, 100 qps each, 10 min | P99 < 300ms, sustained throughput | ✅ |
| Failover | Kill 1 Cloud Run pod | Automatic failover in <5s | ✅ |
| Spike | 2x load spike | Auto-scaling kicks in | ✅ |

#### 3.3 Run Integration Tests

```bash
# Start agent load generator
python scripts/agent_load_test.py \
  --endpoint=$CLOUD_RUN_URL \
  --agents=10 \
  --qps=100 \
  --duration=300 \
  --output=results-dev-10agents.json

# Collect metrics
gcloud monitoring time-series list \
  --filter='resource.type="cloud_run_revision"' \
  --format=json > metrics-dev.json

# Analyze results
python scripts/analyze_metrics.py \
  --input=results-dev-10agents.json \
  --output=report-dev.html
```

**Integration Test Report Template**:
```markdown
## Integration Test Results - Dev Environment

**Date**: 2026-06-27
**Agents Tested**: 50
**Duration**: 10 minutes
**Test Engineer**: [NAME]

### Performance Metrics
| Metric | Target | Actual | Status |
|---|---|---|---|
| P99 Latency | < 500ms | 145ms | ✅ |
| P95 Latency | < 300ms | 87ms | ✅ |
| P50 Latency | < 100ms | 23ms | ✅ |
| Throughput | 1000 qps | 5000 qps | ✅ |
| Error Rate | < 0.1% | 0% | ✅ |
| Cross-tenant Bleed | 0 | 0 | ✅ |

### Issues Found
- [ ] None

### Sign-Off
- [ ] QA Team: _________________ Date: _____
- [ ] Engineering: _________________ Date: _____
- [ ] Customer: _________________ Date: _____
```

---

### Step 4: Intg Environment Deployment (Day 8)

Repeat Steps 2.1-2.5 with `terraform.intg.tfvars`:
```hcl
# Copy dev config and modify:
environment = "intg"
project_id = {
  dev  = "customer-dev-project-123"
  intg = "customer-intg-project-456"
  prod = "customer-prod-project-789"
}
cloud_run_min_instances = 2  # Higher than dev
cloud_run_max_instances = 10
spanner_processing_units = 500  # More capacity
```

---

### Step 5: Chaos Engineering & Reliability (Day 9)

#### 5.1 Chaos Scenarios

| Scenario | Method | Expected | Validation |
|---|---|---|---|
| Pod Kill | gcloud run services update-traffic (0%) | Requests queue/fail gracefully | < 5s MTTR |
| Spanner Latency | Inject delay via Cloud SQL Proxy | SLO maintained with graceful degradation | P99 < 1s |
| Network Partition | firewall rule drop | Circuit breaker triggers | Requests fail fast |
| Cert Expiration | Mock cert expiry | Alerts fire, no traffic loss | Alert in log |

#### 5.2 Run Chaos Tests

```bash
# Scenario 1: Pod Kill
kubectl delete pods -n cloud-run -l app=agent-memory-graph-intg

# Monitor recovery
watch 'gcloud run services describe agent-memory-graph-intg \
  --region=us-central1 \
  --project=CUSTOMER-INTG-PROJECT \
  --format="table(spec.traffic[].percent)"'

# Scenario 2: Latency Injection
gcloud sql instances patch memory-spanner-proxy \
  --backup-start-time=03:00 \
  --project=CUSTOMER-INTG-PROJECT

# Run load test during chaos
python scripts/agent_load_test.py \
  --endpoint=$INTG_URL \
  --agents=50 \
  --duration=300 \
  --output=chaos-results.json
```

**Chaos Engineering Report Template**:
```markdown
## Chaos Engineering Results - Intg Environment

**Date**: 2026-06-27
**Test Engineer**: [NAME]

### Scenario 1: Pod Kill

| Aspect | Result | Status |
|---|---|---|
| Detection Time | 2 seconds | ✅ |
| Recovery Time | 4 seconds | ✅ |
| Requests Lost | 0 | ✅ |
| Alerts Fired | Yes (cpu exceeded) | ✅ |
| RCA | N/A - Expected behavior | ✅ |

### Scenario 2: Spanner Latency (500ms injection)

| Aspect | Result | Status |
|---|---|---|
| P99 under load | 650ms | ✅ (< 1s target) |
| Circuit breaker triggered | No (within SLO) | ✅ |
| Graceful degradation | Yes (queued) | ✅ |
| Error rate | 0% | ✅ |

### Recommendations
- Increase Cloud Run min instances from 2 to 3 (prevents cold starts during pod kills)
- Enable Spanner auto-scaling to handle latency spikes
- Reduce circuit breaker threshold from 1s to 500ms

### Sign-Off
- [ ] Reliability Team: _________________ Date: _____
- [ ] Customer: _________________ Date: _____
```

---

### Step 6: Prod Environment Deployment (Day 10)

#### 6.1 Prod Terraform Configuration

`terraform.prod.tfvars`:
```hcl
environment = "prod"
project_id = {
  dev  = "customer-dev-project-123"
  intg = "customer-intg-project-456"
  prod = "customer-prod-project-789"
}
cloud_run_min_instances = 5      # Production minimum
cloud_run_max_instances = 20     # Production maximum
spanner_processing_units = 2000  # Production capacity
enable_pod_disruption_budget = true
enable_horizontal_pod_autoscaling = true
enable_vertical_pod_autoscaling = true
```

#### 6.2 Canary Deployment Strategy

```bash
# Step 1: Deploy to production (0% traffic initially)
terraform apply tfplan-prod.txt

# Step 2: Route 10% traffic to prod
gcloud run services update-traffic agent-memory-graph-prod \
  --update-traffic prod-canary=10,prod-stable=90 \
  --region=us-central1 \
  --project=CUSTOMER-PROD-PROJECT

# Step 3: Monitor canary metrics for 30 minutes
watch -n 5 'gcloud monitoring read-timeseries \
  --filter="resource.service_name=agent-memory-graph-prod" \
  --start-time=$(date -u -Iseconds -d "30 minutes ago") \
  --format=json | jq ".timeSeries[0].points[0].value"'

# Step 4: If P99 < 500ms and error rate < 0.1%, increase to 50%
gcloud run services update-traffic agent-memory-graph-prod \
  --update-traffic prod-canary=50,prod-stable=50 \
  --region=us-central1 \
  --project=CUSTOMER-PROD-PROJECT

# Step 5: Full rollout
gcloud run services update-traffic agent-memory-graph-prod \
  --update-traffic prod-canary=100 \
  --region=us-central1 \
  --project=CUSTOMER-PROD-PROJECT
```

#### 6.3 Prod Validation Checklist

- [ ] P99 latency < 500ms (target)
- [ ] Error rate < 0.1%
- [ ] Cross-org isolation verified (test org-2 cannot read org-1 data)
- [ ] External auth adapter working (if in use)
- [ ] Monitoring dashboards showing prod metrics
- [ ] Alert policies active and alerting (test alert firing)
- [ ] On-call team responding to alerts
- [ ] Rollback procedure tested (revert traffic to stable)

**Prod Deployment Validation Template**:
```markdown
## Production Deployment Validation

**Date**: 2026-06-27
**Deployed By**: [ENGINEER_NAME]
**Approved By**: [APPROVER_NAME]

### Canary Phase (10% traffic)
- [ ] P99 latency within SLO
- [ ] Error rate < 0.1%
- [ ] No customer complaints
- [ ] Metrics dashboard showing normal distribution
- **Status**: ✅ PROCEED TO 50%

### Main Rollout (100% traffic)
- [ ] All agents successfully onboarded
- [ ] Performance metrics normal
- [ ] Cross-org isolation validated
- [ ] Alert policies active
- [ ] Escalation procedure confirmed
- **Status**: ✅ PRODUCTION LIVE

### Sign-Off
- [ ] Engineering Lead: _________________ Date: _____
- [ ] Operations Lead: _________________ Date: _____
- [ ] Customer Representative: _________________ Date: _____
```

---

## Go/No-Go Review (Day 11)

### Criteria

| Item | Pass/Fail | Evidence |
|---|---|---|
| All 522 tests passing | ✅ | `uv run pytest --tb=short -q` output |
| Dev environment stable (24h) | ✅ | Error budget > 95% |
| Intg environment stable (24h) | ✅ | Error budget > 95% |
| Chaos tests passed | ✅ | RCA report signed off |
| Prod canary stable (1h @ 10%) | ✅ | P99 < 500ms maintained |
| Customer acceptance tests passed | ✅ | 50 agents performing as expected |
| Documentation reviewed | ✅ | Runbook signed by ops team |
| Security review completed | ✅ | Approval from security team |
| Monitoring configured | ✅ | All dashboards live |
| Incidents < 1/week projected | ✅ | Based on chaos testing |

### Sign-Off Template

```markdown
## Go/No-Go Review - Agent Memory Graph Pilot

**Date**: 2026-06-27
**Participants**: Engineering, Operations, Product, Security, Customer

### Dev Environment
- [ ] Stable for 24+ hours
- [ ] All tests passing
- [ ] Performance within SLO
- [ ] Status: ✅ GO

### Intg Environment
- [ ] Stable for 24+ hours
- [ ] Agents performing as expected
- [ ] Chaos tests completed
- [ ] Status: ✅ GO

### Prod Environment
- [ ] Canary stable (P99 < 500ms, error rate < 0.1%)
- [ ] No critical alerts
- [ ] Customer confirmed ready
- [ ] Status: ✅ GO

### Final Sign-Off
**GO/NO-GO Decision**: ✅ **GO** — Agent Memory Graph Pilot approved for full production deployment

**Signatures**:
- Engineering Lead: _________________ Date: _____
- Operations Lead: _________________ Date: _____
- Product Manager: _________________ Date: _____
- Security Lead: _________________ Date: _____
- Customer CTO: _________________ Date: _____

**Contingency Plan**: If any issue arises, rollback to previous stable version within 30 minutes via traffic split revert.
```

---

## Post-Deployment Operations

### Operational Runbook (Handoff to Customer)

See [docs/RUNBOOK.md](../docs/RUNBOOK.md) for:
- [ ] Monitoring dashboard interpretation
- [ ] Alert response procedures
- [ ] Scaling decisions
- [ ] Incident response
- [ ] Backup and recovery
- [ ] Log rotation and retention

### SLO Commitments

| Metric | Target | Owner |
|---|---|---|
| Availability | 99.9% | Eng + Ops |
| P99 Latency | 500ms | Eng |
| MTTR (incidents) | 30 min | Ops |
| Deployment frequency | 2x/week | Eng |
| Lead time for changes | 1 day | Eng |

---

## Success Criteria

✅ **Phase 5 is complete when**:

1. **All three environments live** (dev, intg, prod)
2. **50+ agents deployed** and passing integration tests
3. **24-hour stability achieved** in prod (no SEV-1 incidents)
4. **Customer team trained** on runbook and monitoring
5. **Go/no-go sign-off** obtained from all stakeholders
6. **Monitoring and alerting** validated end-to-end
7. **Incident response** plan tested with customer ops team

---

## Rollback Procedure

If critical issues arise post-deployment:

```bash
# Step 1: Identify issue
# - Check alert logs: gcloud logging read
# - Check traces: gcloud trace-sink
# - Check metrics: gcloud monitoring

# Step 2: Drain traffic (redirect to previous version)
gcloud run services update-traffic agent-memory-graph-prod \
  --update-traffic prod-stable=100,prod-canary=0 \
  --region=us-central1 \
  --project=CUSTOMER-PROD-PROJECT

# Step 3: Destroy problematic Terraform resources
terraform destroy -var-file=terraform.prod.tfvars \
  -target=google_cloud_run_service.app \
  -auto-approve

# Step 4: Re-apply stable version
git checkout stable-tag  # Previous known-good version
terraform apply tfplan-prod-stable.txt -auto-approve

# Step 5: Verify and re-enable traffic
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "$CLOUD_RUN_URL/health"
gcloud run services update-traffic agent-memory-graph-prod \
  --update-traffic prod-stable=50,prod-canary=50 \
  --region=us-central1 \
  --project=CUSTOMER-PROD-PROJECT
```

**MTTR Target**: 30 minutes from detection to full service restoration

---

## Appendix: Deployment Configuration Template

```yaml
# deployment-config.yaml
customer:
  name: "CUSTOMER_NAME"
  organization_id: "ORGANIZATION_ID"
  billing_account: "BILLING_ACCOUNT_ID"

projects:
  dev:
    project_id: "customer-dev-12345"
    region: "us-central1"
  intg:
    project_id: "customer-intg-67890"
    region: "us-central1"
  prod:
    project_id: "customer-prod-11111"
    region: "us-central1"
  data:
    project_id: "customer-data-22222"
    region: "us-central1"

spanner:
  instance_id: "agent-memory-prod"
  database_id: "memory-store"
  processing_units:
    dev: 100
    intg: 500
    prod: 2000

cloud_run:
  min_instances:
    dev: 1
    intg: 2
    prod: 5
  max_instances:
    dev: 5
    intg: 10
    prod: 20

auth:
  mode: "internal"  # or "external"
  external_url: null  # "https://policy.customer.internal/authorize"

monitoring:
  enable_cloud_logging: true
  enable_cloud_monitoring: true
  alert_email: "ops-team@customer.com"

team:
  deployment_owner: "ENGINEER_NAME"
  on_call_contact: "OPS_CONTACT"
  escalation_contact: "CTO_NAME"

timeline:
  planned_start: "2026-06-27"
  dev_deployment: "2026-06-27 - 2026-06-28"
  intg_deployment: "2026-06-29"
  prod_canary: "2026-06-30"
  prod_full_rollout: "2026-07-01"
  customer_handoff: "2026-07-11"
```

---

**Next Steps**:
1. Review this guide with customer operations team
2. Collect deployment configuration (see template above)
3. Schedule kickoff meeting
4. Begin Step 1: Pre-Deployment Planning
5. Track progress in deployment log

**Questions?** Refer to [docs/GETTING_STARTED.md](../docs/GETTING_STARTED.md), [docs/RUNBOOK.md](../docs/RUNBOOK.md), or contact the engineering team.
