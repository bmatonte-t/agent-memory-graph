# Testing Health Dashboard

The unified dashboard is generated from governance artifacts and published to:

- reports/testing-health-dashboard.md

Generate it with:

- `just test-governance-audit`
- `just test-health-dashboard`

Governance source artifacts:

- reports/testing-governance-inventory.json
- reports/testing-governance-inventory.md
- reports/escaped-defects-log.md

Cadence:

- Weekly: refresh governance inventory and dashboard.
- Monthly: update escaped defects log and map to canonical coverage gaps.
- Quarterly: refresh capability ownership and risk mapping.

## SLO dashboards (EPIC-06)

Cloud Monitoring now includes two SLO-oriented dashboards provisioned by Terraform:

- Executive dashboard: SLO goal health for availability, latency, and error-rate.
- Technical dashboard: request volume, MCP error trends, and latency behavior.

These dashboards are generated as Terraform resources in
[infrastructure/terraform/monitoring.tf](infrastructure/terraform/monitoring.tf)
and exposed through outputs in
[infrastructure/terraform/outputs.tf](infrastructure/terraform/outputs.tf).

Operational usage:

- Daily operations: monitor technical dashboard for early regressions.
- Weekly service review: validate executive SLO trend against error budget.
- Incident response: use both dashboards as primary evidence for triage and severity classification in [docs/epic-06-slo-incident-protocol.md](docs/epic-06-slo-incident-protocol.md).
