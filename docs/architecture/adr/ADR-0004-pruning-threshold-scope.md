# ADR-0004: Pruning Threshold Scope

- Status: Accepted
- Date: 2026-07-01
- Owners: AMG core engineering

## Context

EPIC-05 requires deciding if `weight_pruning_threshold` should be global
(deployment-level) or per-tenant.

## Decision

Use **global deployment-level threshold** in current phase.

- Default threshold remains `0.30`.
- Threshold changes are controlled by environment configuration/release.
- Per-tenant thresholding is deferred to a future epic after operational
  baselines are collected.

## Consequences

- Simpler operations and predictable scheduler behavior.
- Reduced configuration complexity.
- Less flexibility for heterogeneous tenant quality profiles.

## Implementation references

- `src/db/schema.py`
- `src/memory/cognitive_weighting.py`
- `infrastructure/terraform/scheduler.tf`
- `docs/concepts/cognitive-weighting.md`
