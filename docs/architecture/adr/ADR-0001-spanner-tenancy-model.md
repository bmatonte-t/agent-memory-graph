# ADR-0001: Spanner Tenancy Model

- Status: Accepted
- Date: 2026-07-01
- Owners: AMG core engineering

## Context

EPIC-05 requires freezing the tenancy strategy for Cloud Spanner. The pending
decision was whether to use shared Spanner instances across teams with logical
isolation, or dedicated instances per adopting team/environment.

## Decision

Use **dedicated Spanner instance and database per adopting team and environment**
(dev/intg/prod triad). Do not share Spanner instances across teams.

## Consequences

- Strong isolation boundary per team and environment.
- Simpler operational blast-radius control and rollback.
- Higher infrastructure footprint than a shared-instance strategy.
- TenantId remains mandatory at data-model level for in-graph scoping and
  future flexibility, but is not the primary cross-team isolation boundary.

## Implementation references

- `docs/deployment.md`
- `docs/architecture.md`
