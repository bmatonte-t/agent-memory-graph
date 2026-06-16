# Debate Questions

## Objectives

1. Which metric is primary for phase one: accuracy, latency, or cost?
2. What minimum explainability standard do we require for every answer?
3. What failure mode is least acceptable: hallucinated recall, stale recall, or missed recall?

## Architecture

4. Do we commit to graph-first or hybrid graph plus vector in phase one?
5. Should memory writes be synchronous with agent responses, asynchronous, or mixed?
6. Where should cognitive scoring run: inline in serving path or background pipeline?

## Governance and Safety

7. What data classes are never persisted in long-term memory?
8. What deletion semantics are mandatory: hard delete, tombstone, or retention windows?
9. What audit evidence is required per memory write and read?

## Evolution

10. Which architecture decisions are reversible without migration pain?
11. What schema versioning strategy should we enforce from day one?
12. What triggers an ADR update versus a minor decision-log note?

## Marketplace Readiness

13. Which buyer profile is phase-one optimized for (platform team, data team, or security/compliance)?
14. What minimum deployment, observability, and support package is required for listing quality?
15. Which enterprise controls must be demonstrable in docs and product behavior before launch?
