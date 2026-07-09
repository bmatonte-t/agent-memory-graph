# E1-T5 — Campaign Label Policy and Naming Standard

**Epic:** E1 — Campaign Framing and Offline Readiness
**Task:** E1-T5
**Date:** 2026-07-08
**Status:** Approved

---

## 1. Label Policy

### 1.1 Mandatory Labels

All GCP resources provisioned during the campaign MUST carry the following labels. Resources missing any mandatory label are non-compliant and must be remediated before the Week 4 infrastructure gate (E5-T8).

| Label Key | Required Value | Immutable After Apply | Purpose |
|-----------|---------------|----------------------|---------|
| `campaign` | `validation-2026` | Yes | Identifies all resources as belonging to this campaign |
| `owner` | `product-team` | Yes | Ownership for billing and escalation routing |
| `env` | `campaign` | Yes | Distinguishes from `prod`, `staging`, `dev` |
| `ttl` | `6-weeks` | Yes | Signals intended lifecycle duration to resource scanner |
| `auto_delete` | `true` | Yes | Marks resources as eligible for automated teardown |

### 1.2 Optional Labels (Applied by Module)

| Label Key | Example Value | Applied To | Purpose |
|-----------|--------------|-----------|---------|
| `workstream` | `w1-infra`, `w2-data`, `w4-benchmark` | Per-module resources | Enables workstream-level cost breakdown |
| `module` | `spanner`, `bigquery`, `cloudrun` | Per-resource type | Enables resource-type cost breakdown |

### 1.3 Label Enforcement Rules

1. Labels are applied at resource creation time in Terraform and are not managed post-apply.
2. The primary deletion mechanism is **Terraform workspace state** — not labels. Labels are the secondary verification filter only.
3. Label compliance is verified in E5-T6 by running a gcloud asset inventory query and comparing against provisioned modules.
4. Any resource found without mandatory labels is flagged as a compliance violation and must be documented in the E5-T6 artifact.

### 1.4 Label Compliance Verification Query

```bash
# Verify mandatory label compliance after E5-T6
gcloud asset search-all-resources \
  --project={{PROJECT_ID}} \
  --asset-types='compute.googleapis.com/Instance,storage.googleapis.com/Bucket,run.googleapis.com/Service,spanner.googleapis.com/Instance,bigquery.googleapis.com/Dataset' \
  --query='labels.campaign:validation-2026' \
  --format='table(name,assetType,labels)'
```

---

## 2. Artifact Folder Structure

### 2.1 Campaign Worktree Root

```
.worktree/campaign-validation/
├── backlog.md                        ← Campaign backlog (E1-T1)
└── artifacts/
    ├── E1-T1-sequencing-decision-note.md
    ├── E1-T2-artifact-index.md
    ├── E1-T2-evidence-register.md
    ├── E1-T2-raci-matrix.md
    ├── E1-T3-placeholder-variable-contract.md
    ├── E1-T3-unresolved-input-register.md
    ├── E1-T4-backend-config-template.md
    ├── E1-T4-workspace-strategy.md
    ├── E1-T5-label-policy.md         ← this file
    ├── E1-T6-offline-runbook.md
    │
    ├── E2-T1-iam-matrix.md           ← created in E2
    ├── E2-T2-agent-profile-catalog.md
    ├── E2-T3-secret-inventory.md
    ├── E2-T4-integration-prerequisites.md
    ├── E2-T5-security-smoke-plan.md
    │
    ├── E3-T1-schema-map.md           ← created in E3
    ├── E3-T2-source-inventory.md
    ├── E3-T3-corpus-manifest.md
    ├── E3-T4-graph-seed-spec.md
    ├── E3-T5-dq-scorecard-template.md
    ├── E3-T6-provenance-register.md
    │
    ├── E4-T1-benchmark-catalog.md    ← created in E4
    ├── E4-T2-scoring-rubric.md
    ├── E4-T3-run-manifest-schema.md
    ├── E4-T4-observability-design.md
    ├── E4-T5-kpi-sql-templates.md
    ├── E4-T6-cost-control-ledger.md
    ├── E4-T7-dry-run-report.md
    │
    ├── E5-T1-concrete-variable-contract.md   ← created in E5 (cloud phase)
    │
    ├── run-manifests/                ← created in E7
    │   └── {run_id}-manifest.json
    │
    └── gates/
        ├── W1-gate-report.md         ← signed end of Week 1
        ├── W2-security-gate-report.md
        ├── W2-data-gate-report.md
        ├── W3-gate-report.md
        ├── W4-gate-report.md
        ├── W5-readiness-gate-report.md
        ├── W5-execution-gate-report.md
        └── W6-closure-report.md
```

### 2.2 Folder Rules

| Rule | Description |
|------|-------------|
| Flat top-level | All task artifacts live directly under `artifacts/` with no sub-folders by epic (keeps scanning easy) |
| `gates/` sub-folder | Gate reports are isolated for quick milestone navigation |
| `run-manifests/` sub-folder | Created in Week 5 during E7 execution; one file per measured run |
| No inline secrets | No artifact may contain resolved `{{PROJECT_ID}}`, `{{BILLING_ACCOUNT_ID}}`, or credential values. Use token form until E5-T1. |
| Immutable after gate sign-off | Gate reports must not be modified after they are signed. If corrections are needed, a new version file is created with a `-v2` suffix. |

---

## 3. Naming Summary Quick Reference

| Object | Pattern | Example |
|--------|---------|---------|
| Task artifact | `E{e}-T{t}-{descriptor-kebab}.md` | `E2-T1-iam-matrix.md` |
| Gate report | `gates/W{w}-{scope}-gate-report.md` | `gates/W2-security-gate-report.md` |
| Run manifest | `run-manifests/{run_id}-manifest.json` | `run-manifests/campaign-2026-EMC-001-manifest.json` |
| GCP resource | `amg-campaign-{type}[-{qualifier}]` | `amg-campaign-spanner` |
| GCS bucket | `amg-campaign-{type}-{{PROJECT_ID}}` | `amg-campaign-corpus-<id>` |
| Service account | `amg-campaign-{role}@{{PROJECT_ID}}.iam.gserviceaccount.com` | `amg-campaign-svc@<id>.iam...` |
| Secret | `amg-campaign-{integration}-token` | `amg-campaign-slack-token` |
| Benchmark run ID | `campaign-2026-{SCENARIO_ID}-{RUN_SEQ:03d}` | `campaign-2026-EMC-001` |
