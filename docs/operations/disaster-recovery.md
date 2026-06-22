# Disaster Recovery

This document describes the backup, restore, and rollback strategy for Agent Memory Graph.

## Objectives

- preserve graph integrity across Context, Semantic, and Audit tiers
- restore service with controlled data-loss bounds
- support rollback of application revisions without schema ambiguity

## Recovery Targets

Suggested starting targets:

- RTO: 60 minutes
- RPO: 15 minutes or the latest successful Spanner backup window

These targets should be adjusted by environment tier and customer commitments.

## Backups

- Use Cloud Spanner managed backups for database recovery.
- Keep schema migrations under `migrations/` version-controlled and immutable after release.
- Preserve Cloud Run revision history for fast application rollback.
- Preserve alert/dashboard definitions under `infrastructure/phase2/`.

## Restore Procedure

1. Identify the incident scope: application-only, data-only, or combined failure.
2. If data corruption is suspected, stop risky writes and preserve incident evidence.
3. Restore the target Spanner backup into a recovery environment first.
4. Validate schema version against migration history.
5. Run smoke checks on health, retrieval, and audit visibility.
6. Promote the recovered database or redirect the service after verification.

## Application Rollback

1. Route Cloud Run traffic back to the last known good revision.
2. Confirm request success rate and latency recovery.
3. If schema changes were part of the release, verify backward compatibility before rollback.

## Incident Classification

- Application regression: rollback Cloud Run revision first.
- Observability failure: preserve serving path, restore tracing/logging/metrics separately.
- Data corruption or wrong-tenant exposure: freeze writes, preserve audit evidence, initiate security escalation.

## Validation After Recovery

Confirm:

- health endpoint responds normally
- MindMap pipeline returns grounded responses or explicit insufficiency
- audit write path is still append-only
- dashboards and alert policies resume signal ingestion
