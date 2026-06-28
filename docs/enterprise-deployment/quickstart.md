# Quickstart

## Goal

Get a local environment ready and execute one successful grounded request path in approximately 10 to 15 minutes.

## Prerequisites

- Python 3.14 available.
- `uv` installed.
- Local repository checkout.

Optional for cloud-integrated validation:

- GCP project and credentials for deployed services.

## 1. Install Dependencies

```bash
uv sync
```

## 2. Run Core Validation

```bash
just check-all
```

If you need a faster smoke check first:

```bash
uv run pytest tests/unit/test_setup.py -q
```

## 3. Start API Service

Run the project API entrypoint according to your local workflow. The main application is implemented in:

- `src/api/main.py`

## 4. Execute a Request

Use the agent endpoint path described in:

- [docs/technical-report.md](../technical-report.md)

Expected behavior:

- successful response envelope,
- grounded response when evidence exists,
- explicit "Insufficient graph evidence." when evidence is missing.

## 5. Verify Observability Artifacts

Review local or deployed artifacts:

- `infrastructure/phase2/cloud-monitoring-dashboard.json`
- `infrastructure/phase2/alert-policies.yaml`

## Troubleshooting

- General troubleshooting: [docs/help/troubleshooting.md](../help/troubleshooting.md)
- Operations guidance: [docs/operations/ops-runbook.md](../operations/ops-runbook.md)

## Known Limitations (Current Phase)

- Marketplace legal/commercial packaging is still in progress.
- Full production rollout validation belongs to Phase 6.
