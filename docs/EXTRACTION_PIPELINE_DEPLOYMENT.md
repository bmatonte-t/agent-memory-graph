# Document Extraction Pipeline Deployment Guide

## Prerequisites

Before deploying, ensure you have:

- **GCP Project** with billing enabled
- **gcloud CLI** installed and authenticated (v440.0.0+)
- **Docker** installed locally (for image building)
- **Service Account** with Cloud Run Admin and GCR permissions
- **Python 3.14+** for local builds
- **uv** and **just** for dependency management

### Install gcloud CLI

```bash
# macOS
brew install --cask google-cloud-sdk

# Linux
curl https://sdk.cloud.google.com | bash

# Verify installation
gcloud --version
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

## Architecture Topology

The extraction pipeline deploys to Google Cloud Run with the following topology:

```
┌─────────────────────────────────────────┐
│       Cloud Load Balancer (Optional)    │
└────────────────────┬────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
      ┌──▼──┐ PROD          ┌──▼──┐
      │ Run │ (90% traffic) │ Run │ CANARY
      │  v1 │               │ v2  │ (10% traffic)
      └──┬──┘               └──┬──┘
         │                     │
         └───────────┬─────────┘
                     │
        ┌────────────▼────────────┐
        │  Cloud Scheduler (Opt)  │
        │  Auto-scale monitoring  │
        └─────────────────────────┘
```

## Environment Tiers

### Development (DEV)

**Use Case**: Local testing, feature development  
**Configuration**: No authentication, 512MB memory

```bash
export PROJECT_ID=my-project-dev
export REGION=us-central1
export IMAGE=gcr.io/${PROJECT_ID}/extraction-api:dev-latest
```

### Staging

**Use Case**: Integration testing, pre-production validation  
**Configuration**: Authentication enabled, 1GB memory

```bash
export PROJECT_ID=my-project-staging
export REGION=us-central1
export IMAGE=gcr.io/${PROJECT_ID}/extraction-api:staging-v1
```

### Production (PROD)

**Use Case**: Live traffic, enterprise workloads  
**Configuration**: Full authentication, 2GB memory, auto-scaling

```bash
export PROJECT_ID=my-project-prod
export REGION=us-central1
export IMAGE=gcr.io/${PROJECT_ID}/extraction-api:v1.0.0
```

## Step 1: Build Container Image

### Option A: Local Build

```bash
# Navigate to repository root
cd /path/to/agent-memory-graph

# Build Docker image
docker build -t extraction-api:v1.0.0 .

# Tag for GCR
docker tag extraction-api:v1.0.0 gcr.io/${PROJECT_ID}/extraction-api:v1.0.0
```

### Option B: Cloud Build

```bash
# Build in GCP (no local Docker required)
gcloud builds submit \
  --tag gcr.io/${PROJECT_ID}/extraction-api:v1.0.0 \
  --region=${REGION}

# Monitor build progress
gcloud builds log <BUILD_ID> --stream
```

## Step 2: Push Image to Container Registry

```bash
# Authenticate Docker with GCR
gcloud auth configure-docker

# Push image
docker push gcr.io/${PROJECT_ID}/extraction-api:v1.0.0

# Verify push
gcloud container images list --repository=gcr.io/${PROJECT_ID}
```

## Step 3: Deploy to Cloud Run

### Basic Deployment

```bash
gcloud run deploy extraction-api \
  --image gcr.io/${PROJECT_ID}/extraction-api:v1.0.0 \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 2 \
  --timeout 300
```

### Production Deployment (with authentication)

```bash
gcloud run deploy extraction-api \
  --image gcr.io/${PROJECT_ID}/extraction-api:v1.0.0 \
  --region ${REGION} \
  --platform managed \
  --no-allow-unauthenticated \
  --memory 2Gi \
  --cpu 4 \
  --timeout 300 \
  --min-instances 1 \
  --max-instances 100 \
  --set-env-vars "PROJECT_ID=${PROJECT_ID}" \
  --service-account extraction-api@${PROJECT_ID}.iam.gserviceaccount.com \
  --labels env=production,team=data
```

### With Custom Configuration

```bash
# Create environment file
cat > /tmp/env.yaml <<EOF
PROJECT_ID: ${PROJECT_ID}
REGION: ${REGION}
LOG_LEVEL: INFO
ENABLE_METRICS: "true"
EOF

# Deploy with environment variables
gcloud run deploy extraction-api \
  --image gcr.io/${PROJECT_ID}/extraction-api:v1.0.0 \
  --region ${REGION} \
  --env-vars-file /tmp/env.yaml \
  ...
```

## Step 4: Configure Service Account (Production)

### Create Service Account

```bash
# Create service account
gcloud iam service-accounts create extraction-api \
  --display-name "Extraction API Service Account"

# Get service account email
SERVICE_ACCOUNT=$(gcloud iam service-accounts list \
  --filter="displayName:Extraction API" \
  --format='value(email)')

echo ${SERVICE_ACCOUNT}
```

### Grant IAM Roles

```bash
# Cloud Run invoker role
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/run.invoker"

# Cloud Logging writer role
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/logging.logWriter"

# Cloud Trace agent role
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/cloudtrace.agent"
```

## Step 5: Verify Deployment

### Health Check

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe extraction-api \
  --region=${REGION} \
  --format='value(status.url)')

echo ${SERVICE_URL}

# Test health endpoint
curl ${SERVICE_URL}/api/v1/health
```

### Expected Response

```json
{
  "status": "healthy",
  "message": "Service is running",
  "api_version": "v1"
}
```

### View Logs

```bash
# Stream logs in real-time
gcloud logging read "resource.type=cloud_run_instance" \
  --limit 50 \
  --format json \
  --stream

# Or use Cloud Logging UI
gcloud logging read "resource.service.name=extraction-api" \
  --limit 100
```

## Advanced: Canary Deployments

### Deploy New Revision (10% Traffic)

```bash
# Deploy new version
gcloud run deploy extraction-api \
  --image gcr.io/${PROJECT_ID}/extraction-api:v1.1.0 \
  --region ${REGION} \
  --no-traffic

# Get revision names
gcloud run revisions list --service extraction-api --region ${REGION}

# Example output:
# REVISION_A: extraction-api-prod-revision-00001-abc
# REVISION_B: extraction-api-prod-revision-00002-def
```

### Split Traffic: 90% Old, 10% New

```bash
gcloud run services update-traffic extraction-api \
  --region ${REGION} \
  --to-revisions REVISION_A=90,REVISION_B=10

# Verify traffic split
gcloud run services describe extraction-api \
  --region ${REGION}
```

### Monitor Canary Deployment

```bash
# Get metrics for each revision
gcloud monitoring time-series list \
  --filter='resource.service.name=extraction-api' \
  --interval-start-time 2025-06-27T00:00:00Z
```

### Promote Canary to 100% (if successful)

```bash
gcloud run services update-traffic extraction-api \
  --region ${REGION} \
  --to-revisions REVISION_B=100
```

### Rollback (if issues detected)

```bash
gcloud run services update-traffic extraction-api \
  --region ${REGION} \
  --to-revisions REVISION_A=100
```

## Cleanup: Delete Revision

```bash
# Delete old revision after successful rollout
gcloud run revisions delete REVISION_A \
  --region ${REGION} \
  --service extraction-api
```

## Troubleshooting

### Service Won't Start

```bash
# Check deployment status
gcloud run services describe extraction-api \
  --region ${REGION} \
  --format='value(status.conditions[0])'

# View detailed error logs
gcloud run services describe extraction-api \
  --region ${REGION} \
  --format='value(status)'
```

### Permission Denied Error

```bash
# Verify service account has necessary roles
gcloud projects get-iam-policy ${PROJECT_ID} \
  --flatten="bindings[].members" \
  --format='table(bindings.role)' \
  --filter="bindings.members:serviceAccount:${SERVICE_ACCOUNT}"

# Add missing roles
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/run.admin"
```

### Memory Exceeded (OOM)

```bash
# Increase memory allocation
gcloud run deploy extraction-api \
  --region ${REGION} \
  --memory 4Gi  # Increased from 2Gi
  --image gcr.io/${PROJECT_ID}/extraction-api:v1.0.0
```

### Slow Extraction Performance

```bash
# Increase CPU allocation
gcloud run deploy extraction-api \
  --region ${REGION} \
  --cpu 8  # Increased from 4
  --image gcr.io/${PROJECT_ID}/extraction-api:v1.0.0

# Enable autoscaling
gcloud run deploy extraction-api \
  --region ${REGION} \
  --max-instances 50  # Auto-scale up to 50 instances
  --image gcr.io/${PROJECT_ID}/extraction-api:v1.0.0
```

## Monitoring & Observability

### View Cloud Logging Dashboard

```bash
# Open Cloud Console
gcloud logging dashboards list

# Create custom dashboard
gcloud monitoring dashboards create --config-from-file=dashboard.json
```

### Set Up Cloud Monitoring Alerts

```bash
# Create alert for high latency
gcloud alpha monitoring policies create \
  --display-name "Extraction API Latency Alert" \
  --condition-display-name "P99 latency > 5s" \
  --condition-threshold-value 5000 \
  --condition-threshold-duration 300s
```

### Enable Cloud Trace

Traces are automatically captured by Cloud Run. View in Cloud Console:

```
https://console.cloud.google.com/traces/list?project=PROJECT_ID
```

### Custom Metrics

The extraction API logs extraction metrics:

- Request count (total)
- Extraction latency (p50, p95, p99)
- Error rate (failures per minute)
- Entity count (total extracted)
- Deduplication matches (high/medium/low confidence)

Access via Cloud Monitoring dashboard or Metrics Explorer.

## Cost Optimization

### Reduce Cold Start Latency

```bash
# Set minimum instances to reduce cold starts
gcloud run deploy extraction-api \
  --min-instances 1  # Keep 1 instance warm
  --region ${REGION}
```

### Scheduled Cleanup

```bash
# Use Cloud Scheduler to invoke cleanup endpoint
gcloud scheduler jobs create app-engine cleanup-extraction-api \
  --schedule "0 2 * * *" \
  --http-method POST \
  --uri "${SERVICE_URL}/internal/cleanup"
```

### Estimate Monthly Costs

For typical production usage (1M documents/month):

| Component | Estimate |
|-----------|----------|
| Cloud Run compute | $50-200 |
| Container Registry storage | $10-20 |
| Cloud Logging | $20-50 |
| Cloud Trace (optional) | $5-10 |
| **Total** | **$85-280/month** |

## Deployment Checklist

- [ ] GCP project created with billing enabled
- [ ] gcloud CLI installed and authenticated
- [ ] Docker image built locally or via Cloud Build
- [ ] Image pushed to GCR
- [ ] Service account created (production)
- [ ] IAM roles assigned (production)
- [ ] Health endpoint responding (200 OK)
- [ ] Test extraction with sample PDF
- [ ] Logs visible in Cloud Logging
- [ ] Monitoring alerts configured
- [ ] Documentation updated
- [ ] Team notified of deployment

## Rollback Procedure

In case of critical issues post-deployment:

```bash
# 1. Identify working revision
gcloud run revisions list --service extraction-api --region ${REGION}

# 2. Route all traffic to previous revision
gcloud run services update-traffic extraction-api \
  --region ${REGION} \
  --to-revisions <PREVIOUS_REVISION>=100

# 3. Verify service is healthy
curl ${SERVICE_URL}/api/v1/health

# 4. Delete failed revision
gcloud run revisions delete <FAILED_REVISION> \
  --service extraction-api \
  --region ${REGION}

# 5. Notify team and begin investigation
```

## Next Steps

1. Deploy to STAGING first for integration testing
2. Run load tests via Phase E integration test suite
3. Monitor for 24-48 hours in STAGING
4. Promote to PROD with canary deployment (10% traffic)
5. Gradually increase traffic to 100% over 1 hour
6. Monitor error rate, latency, and resource usage
7. Lock down service account permissions after deployment
