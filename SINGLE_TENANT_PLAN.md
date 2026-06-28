# Plan: Org-Wide Plug-and-Play Product — Single Customer Deployment

## TL;DR

Refactor Agent Memory Graph from multi-tenant SaaS to an **org-wide managed service** deployable across the client's full GCP organization (multiple projects: dev/intg/prod). Use **Terraform workspaces** matching the client's Cosmos platform pattern for repeatable, auditable deployments. Auth/governance is externalized as a **pluggable `GovernanceAdapter` protocol** so we can wire to their existing IAM controls without rewriting memory logic. Implement via feature flags in this parallel `single-tenant-variant` worktree — zero breaking changes to multi-tenant `develop`. Enterprise scale: 50+ agents, 1000+ queries/min.

**Timeline**: ~6 weeks

---

## Key Design Decisions

1. **Org-wide multi-project deployment**: Spanner lives in a central data project; Cloud Run per env. Terraform accepts `spanner_project_id` independently from `cloud_run_project_id`.
2. **GovernanceAdapter protocol (pluggable auth)**: `InternalAbacAdapter` wraps existing ABAC; `ExternalPassthroughAdapter` calls client policy URL. Terraform variable `auth_mode = "internal" | "external"`.
3. **Terraform workspace strategy**: Matches client's Cosmos pattern — `dev | intg | prod` with `lookup(var.project_id, terraform.workspace)`.
4. **Feature flags, not rewrites**: `single_company.enabled = true` in config activates org-wide mode. All validation auto-injects the fixed `company_id`.

---

## Progress Tracking

| Phase | Status | Completed | Notes |
|-------|--------|-----------|-------|
| Phase 0: Worktree Setup | ✅ | 2026-06-27 | Worktree at worktrees/single-tenant-variant |
| Phase 1: Code Refactoring | ✅ | 2026-06-27 | 61 tests created and passing; governance adapter + tenant context |
| Phase 2: Infrastructure-as-Code | ✅ | 2026-06-27 | 9 Terraform files; workspace pattern; .gitlab-ci.yml |
| Phase 3: Documentation | ✅ | 2026-06-27 | 7 docs + performance baseline; 3 docs pending commit |
| Phase 4: Testing & Hardening | ✅ | 2026-06-27 | 121 new tests (522 total); P99 < 5ms (50-100x SLO headroom) |
| Phase 5: Customer Pilot | 🔄 | — | In progress; deployment guide + checklist + ADR completed |

---

## Phase 1: Code Changes

### New files
- `src/security/tenant_context.py` — `OrgTenantContext` with `get_fixed_tenant_id() -> str | None`
- `src/security/governance_adapter.py` — `GovernanceAdapter` Protocol + `InternalAbacAdapter` + `ExternalPassthroughAdapter`

### Modified files
| File | Change |
|------|--------|
| `src/project_base/settings/config.py` | Add `SingleCompanySettings` model + field |
| `src/security/validators.py` | Inject `company_id` when `single_company.enabled` |
| `src/models/mcp.py` | `MCPInvokeRequest.tenant_id` optional |
| `src/models/schemas.py` | Request models `tenant_id` optional |
| `src/mcp/service.py` | Route authorization through `GovernanceAdapter` |
| `config.yaml` | Add `single_company` block (disabled by default) |
| `tests/conftest.py` | Add `single_company_settings` fixture |

### Phase 1 verification checklist
- [ ] All 401+ existing tests pass unchanged
- [ ] Coverage ≥ 85%
- [ ] `just check-all` passes

---

## Phase 2: Infrastructure (Terraform)

```
infrastructure/terraform/
├── config.tf        # GCS remote state backend
├── main.tf          # Cloud Run + Monitoring
├── spanner.tf       # Spanner DB + cross-project IAM
├── iam.tf           # Product SA + group impersonation + Spanner SA
├── secrets.tf       # Secret Manager resources
├── monitoring.tf    # Log-based metrics + alert policies
├── variables.tf     # Workspace-resolved map(string) variables
├── terraform.tfvars # dev/intg/prod project IDs, company_id, Spanner config
└── outputs.tf       # Cloud Run URL, Spanner path, SA email
```

Also: `.gitlab-ci.yml` (Cosmos template), `catalog-info.yaml` (Backstage)

---

## Phase 3: Documentation

1. `docs/deployment/org-wide-getting-started.md`
2. `docs/deployment/governance-adapter-guide.md`
3. `docs/api/org-wide-quickstart.md`
4. `docs/operations/org-wide-runbook.md`
5. `docs/architecture/adr/org-wide-pivot-rationale.md`
6. `docs/api/mcp-tools-reference.md`
7. `docs/operations/cost-model.md`

---

## Phase 4: Testing & Hardening

- Scale: 50 agents, 1000 qps, p99 < 500ms
- Cross-org isolation: two mock companies, zero bleed
- External auth adapter integration tests
- Cross-project Spanner IAM tests

---

## Phase 5: Customer Pilot Deployment

**Status**: 🔄 In Progress (Planning & Documentation Complete)
**Timeline**: 14 days (2 weeks)
**Key Deliverables**:
- Deployment in 3 environments (dev → intg → prod)
- 50+ agents onboarded and validated
- Monitoring dashboards live
- Chaos engineering validation complete
- Go/no-go sign-off obtained
- Operations handoff to customer

### Phase 5 Execution Plan

See **PHASE_5_DEPLOYMENT_GUIDE.md** for complete step-by-step procedures:
1. **Pre-Deployment Planning** (Day 1-2)
   - Customer alignment on timeline & requirements
   - Infrastructure readiness checks
   - Deployment checklist sign-off
   - Terraform variable collection

2. **Dev Environment** (Day 3-4)
   - Terraform workspace setup
   - Cloud Run + Spanner deployment
   - Single-agent validation (100 qps)
   - 24-hour stability verification

3. **Integration Testing** (Day 4-7)
   - Agent onboarding: 1 → 10 → 50 agents
   - Load testing: 100 qps per agent
   - Cross-tenant data bleed validation
   - Customer acceptance tests

4. **Intg Environment** (Day 8)
   - Terraform workspace replication
   - Repeat validation with 50 agents
   - Readiness assessment for chaos testing

5. **Chaos Engineering** (Day 9)
   - Pod kill scenario (MTTR < 15s)
   - Spanner latency injection (graceful degradation)
   - Network partition scenario (circuit breaker)
   - RCA & remediation if needed

6. **Prod Deployment** (Day 10)
   - Canary rollout: 0% → 10% → 50% → 100%
   - Monitor P99 latency < 500ms throughout
   - Gradual traffic shift to prod
   - Monitoring dashboard validation

7. **Go/No-Go Review** (Day 11)
   - All stakeholder sign-offs collected
   - Deployment readiness criteria verified
   - Contingency plan confirmed
   - Production declaration

8. **Operations Handoff** (Day 11-14)
   - Customer ops team trained on runbook
   - Monitoring dashboard walkthrough
   - SLO commitments reviewed
   - Support escalation procedures confirmed

### Phase 5 Documentation

| Document | Purpose | Location |
|---|---|---|
| **PHASE_5_DEPLOYMENT_GUIDE.md** | Complete step-by-step deployment procedures | Worktree root |
| **PHASE_5_EXECUTION_CHECKLIST.md** | 8 milestones with detailed checklists | Worktree root |
| **ADR_PHASE_5_DEPLOYMENT_STRATEGY.md** | Deployment strategy decisions & rationale | docs/ |
| **GETTING_STARTED.md** | Customer deployment quickstart (existing) | docs/ |
| **RUNBOOK.md** | Operational procedures & troubleshooting (existing) | docs/ |

### Phase 5 Success Criteria

✅ **Phase 5 is complete when**:
- [x] Planning & documentation complete
- [ ] Pre-deployment planning checklist signed off
- [ ] Dev environment deployed & stable for 24 hours
- [ ] 50 agents successfully integrated & tested
- [ ] Intg environment deployed & stable for 24 hours
- [ ] Chaos engineering scenarios completed successfully
- [ ] Prod canary deployment gradual rollout complete
- [ ] Go/no-go review meeting held with all sign-offs
- [ ] Operations handoff completed with customer trained
- [ ] Production SLOs committed (P99 < 500ms, 99.9% availability)

### Phase 5 Timeline

```
Week 1:
  Day 1-2: Pre-deployment planning & sign-off
  Day 3-4: Dev environment deployment & single-agent validation
  Day 4-7: Integration testing with 50 agents

Week 2:
  Day 8:   Intg environment deployment
  Day 9:   Chaos engineering & reliability testing
  Day 10:  Prod canary deployment & gradual rollout
  Day 11:  Go/no-go review & production declaration
  Day 11-14: Operations handoff to customer team
```

### Phase 5 Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Terraform state corruption | Low | Daily backups + audit logging |
| Spanner quota exceeded | Low | Pre-allocate 3x estimated RU/day |
| Customer IAM issues | Medium | Pre-flight IAM checks + runbook |
| Performance regression | Low | Chaos testing validates graceful degradation |
| Agent integration issues | Low | Phased onboarding (1 → 10 → 50) |
| Customer unavailability | Medium | Schedule 2 weeks in advance |

### Post-Deployment SLOs

| Metric | Target | Owner |
|---|---|---|
| Availability | 99.9% (8.76 hrs/month) | Eng + Ops |
| P99 Latency | < 500ms | Eng |
| P95 Latency | < 300ms | Eng |
| MTTR (incidents) | < 30 minutes | Ops |
| Incident Response | < 5 minutes | Ops |
| Deployment Frequency | 2x/week | Eng |
| Lead Time | < 1 day | Eng |

---

## Appendix: Key Contacts & Escalation

**Engineering Team**:
- Engineering Lead: [NAME]
- DevOps Engineer: [NAME]
- QA Engineer: [NAME]

**Customer Team**:
- Customer CTO: [NAME]
- Customer Ops Lead: [NAME]
- Customer Pilot Sponsor: [NAME]

**Escalation Contacts**:
- On-Call Engineer: [PHONE]
- Customer Emergency Contact: [PHONE]
- Executive Escalation: [NAME] / [EMAIL]
