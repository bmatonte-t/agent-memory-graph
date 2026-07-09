# E1-T4 — Terraform Backend Config Template

**Epic:** E1 — Campaign Framing and Offline Readiness
**Task:** E1-T4
**Date:** 2026-07-08
**Status:** Template (activate at E5-T2)

---

## Purpose

Provides the Terraform backend configuration template for the campaign workspace. All placeholder tokens follow the contract in `E1-T3-placeholder-variable-contract.md`. This file must not be applied until `{{PROJECT_ID}}`, `{{REGION}}`, and `{{TERRAFORM_BACKEND_BUCKET}}` are resolved via E5-T1.

---

## Backend Configuration Template

Save as `infrastructure/terraform/campaign/backend.hcl` when activating:

```hcl
# Campaign Validation — Terraform Remote Backend Configuration
# Template version: 2026-07-08
# Activate only after E5-T1 variable contract is approved.
#
# Resolved values must be substituted for all {{TOKEN}} placeholders
# before running `terraform init -backend-config=backend.hcl`.

terraform {
  backend "gcs" {
    bucket = "{{TERRAFORM_BACKEND_BUCKET}}"
    prefix = "campaign-validation/tfstate"
  }
}
```

## Resolved Example (DO NOT USE until E5-T1)

```hcl
# Example only — replace with actual values from E5-T1 approval
terraform {
  backend "gcs" {
    bucket = "amg-campaign-tfstate-<PROJECT_ID>"
    prefix = "campaign-validation/tfstate"
  }
}
```

---

## Initialization Command

```bash
# Run after E5-T1 approval and value substitution
terraform -chdir=infrastructure/terraform/campaign \
  init \
  -backend-config=backend.hcl \
  -reconfigure
```

---

## Pre-requisites for Activation

- [ ] `{{PROJECT_ID}}` resolved (E5-T1)
- [ ] `{{TERRAFORM_BACKEND_BUCKET}}` GCS bucket created with versioning enabled (E5-T2)
- [ ] Campaign workspace Terraform service account has `storage.objectAdmin` on the backend bucket
- [ ] Terraform version pinned to >= 1.8.0 per `.terraform-version` file
