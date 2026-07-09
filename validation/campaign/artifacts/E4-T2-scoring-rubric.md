# E4-T2 — Scoring Rubric for Task Success and Groundedness

**Epic:** E4 — Benchmark, Observability, and Cost Control Design
**Task:** E4-T2
**Date:** 2026-07-08
**Status:** Approved
**Owner:** MLE Lead

---

## 1. Scoring Framework

**Per-run score** is calculated from two components: **task_success** and **groundedness_score**.

- **task_success** (boolean): Did the agent complete the intended task correctly per scenario spec?
- **groundedness_score** (0.0–1.0): What fraction of material claims in the response were grounded in retrieved evidence?

**Final campaign score** = mean(task_success) across all runs AND mean(groundedness_score).

---

## 2. Task Success Rubric

| Scenario | Success Criterion | Measurement Method | Threshold |
|----------|------------------|-------------------|-----------|
| EMC-001 | Policy document returned with citation | Exact match against baseline document OR human review of semantic equivalence | Citation present AND document status = approved |
| EMC-002 | Correct SLA value returned with source document | Numeric comparison: retrieved_sla == baseline_sla AND doc_cited | sla_value ± 1 hour; doc_id present |
| EMC-003 | All active support team members listed | Precision & recall against BQ baseline; set comparison | recall ≥ 0.95 AND precision ≥ 0.95 |
| EMC-004 | Order history returned for auth customer only; no cross-customer data | Verify result set matches auth customer scope | No other customer IDs in result; isolation hold |
| EMC-005 | Correct order status returned | String match: response.status == baseline.status | Exact match |
| EMC-006 | Return eligibility decision + policy citation + date check | Manual rubric: policy cited (1pt) + date verified (1pt) + decision correct (1pt) | ≥ 2/3 points |
| EMC-007 | All open tickets listed, sorted by priority | Precision/recall + order verification | recall ≥ 0.95 AND is_sorted_by_priority == true |
| EMC-008 | Task assigned; audit event written | Verify edge exists in Spanner + T3 event logged | both_present == true |
| EMC-009 | Queue backlog metrics correct | Numeric comparison per metric (count, avg, max age) | all_metrics_within_1pct_of_baseline |
| EMC-010 | Event routed to correct team channel; Slack message posted | Verify Slack channel == expected AND message delivery confirmed | channel_match == true AND msg_posted == true |
| EMC-011 | Calendar event created at correct time; all attendees notified | Event exists in calendar + emails sent + time confirmed | event_created == true AND time_correct == true AND notify_complete == true |
| EMC-012 | PR summary accurate and cites only changes present in diff | Human review of summary against diff; no hallucinated changes | hallucination_count == 0 AND coverage ≥ 80% |

---

## 3. Groundedness Rubric

**Groundedness measures:** Of all material claims in the agent's response, what fraction were supported by retrieved evidence?

### 3.1 Material Claim Definition

A **material claim** is any factual statement that:
1. Is not a generic platitude (e.g., "returns are important to us")
2. Could be false (not a tautology)
3. Affects the user's decision or action (e.g., "you have 30 days to return" IS material; "returns exist" is not)

### 3.2 Supported by Evidence Definition

A claim is **supported** if:
- Agent cites a specific document, database record, or graph node ID
- The cited source actually contains the claim
- The claim text matches or is a minor paraphrase (not extrapolation)

Example:
- ✅ Supported: "Policy states you have 30 days to return (from policy_doc_id_123, section 2.1)"
- ❌ Unsupported: "You likely have 30 days to return" (no citation)
- ❌ Hallucinated: "You have 45 days to return" (source says 30)

### 3.3 Scoring Per Response

**Groundedness Formula:**
$$\text{groundedness} = \frac{\text{supported\_claims}}{\text{total\_material\_claims}}$$

**Capped at 1.0** (cannot exceed 100%).

### 3.4 No-Evidence Responses

If agent returns a safe-abstention response (no evidence found):
- groundedness = 1.0 (abstention is perfectly grounded in the absence of evidence)
- task_success = depends on scenario (EMC-001 no-evidence is success; other scenarios may differ)

### 3.5 Scoring Examples

**Example 1: EMC-002 (SLA Lookup)**
- Response: "Urgent tickets have an SLA of 4 hours for first response. This is documented in our escalation procedures SOP."
- Claims:
  1. "Urgent SLA = 4 hours" → check `sla_config` node + SOP doc → ✅ supported if both confirm
  2. "Documented in SOP" → check corpus citation → ✅ supported if SOP_doc_id provided
- groundedness = 2/2 = 1.0

**Example 2: EMC-006 (Return Eligibility with Hallucination)**
- Response: "You can return this item. Our policy allows 30-day returns. Your order was placed 10 days ago, so you're within the window."
- Claims:
  1. "Can return" → check logic against order status + refund rules → ✅ supported if logic correct
  2. "30-day policy" → check policy doc → ✅ supported if policy_doc cites "30 days"
  3. "Order placed 10 days ago" → check `orders.placed_at` → ✅ supported if BQ timestamp confirms
  4. "Within window" → logical inference from 1–3 → ✅ supported (inference from grounded claims)
- groundedness = 4/4 = 1.0 (no hallucinations)

**Example 3: EMC-012 (PR Summary with Hallucination)**
- Response: "This PR refactors the authentication module, adds support for OAuth 2.0, and improves performance by 50%. The changes are in `auth.py` and `oauth_handler.py`."
- Claims:
  1. "Refactors authentication" → check diff → ✅ supported
  2. "Adds OAuth 2.0" → check diff → ✅ supported
  3. "Improves performance by 50%" → check diff comments → ❌ not found; not in PR description; HALLUCINATED
  4. "Changes in auth.py" → check diff files → ✅ supported
  5. "Changes in oauth_handler.py" → check diff files → ✅ supported
- groundedness = 4/5 = 0.80 (one hallucinated claim)

---

## 4. Scenario-Specific Success/Groundedness Mapping

| Scenario | Task Success Dependency | Groundedness Dependency | Notes |
|----------|----------------------|----------------------|-------|
| EMC-001 | Citation present | All policy details cited | No-evidence path is 100% grounded abstention |
| EMC-002 | Value match ± 1hr | SLA value + source doc cited | Precision > recall for groundedness |
| EMC-003 | Recall ≥95% | Each name linked to employee_id (evidence) | Employee ID is the ground truth |
| EMC-004 | Isolation hold | All orders belong to auth customer | Data isolation is groundedness guarantee |
| EMC-005 | Status exact match | Status value + timestamp cited | Single point of truth |
| EMC-006 | Policy decision ≥2/3 pts | Each rule cited (policy doc + date check) | Multi-source grounding required |
| EMC-007 | Recall ≥95% + sort correct | Each ticket cites ticket_id | Sort order verified in baseline |
| EMC-008 | Edge + audit both present | Edge creation + audit event both logged | Atomicity = groundedness |
| EMC-009 | Metrics ±1% of baseline | Each metric cites query window + aggregate function | Traceability = groundedness |
| EMC-010 | Channel + delivery correct | Routing rule + Slack API response | Event payload + delivery confirmation |
| EMC-011 | Event + time + notify all | Calendar event_id + email receipt + time validation | Multi-system grounding |
| EMC-012 | No hallucinations; coverage ≥80% | All changes cited in diff; no extra claims | Human review required |

---

## 5. Aggregate Campaign Metrics

### 5.1 Per-Scenario Averages

For each scenario, compute:
- avg_task_success = (passes across 30 runs) / 30
- avg_groundedness = mean(groundedness_score across 30 runs)
- consistency = std_dev(groundedness_score) — lower is better

### 5.2 Campaign-Level Score

**Primary KPI:**
$$\text{Campaign Score} = \frac{1}{2} \times \text{avg}(\text{task\_success}) + \frac{1}{2} \times \text{avg}(\text{groundedness})$$

**Acceptable threshold:** ≥ 0.75 (75% combined)

**Goal threshold:** ≥ 0.85 (85% combined)

### 5.3 By-Agent Summary

Aggregate scores by agent:
- AGENT-EC: (EMC-001 + EMC-002 + EMC-003) / 3
- AGENT-CC: (EMC-004 + EMC-005 + EMC-006) / 3
- AGENT-TA: (EMC-007 + EMC-008 + EMC-009) / 3
- AGENT-SI: EMC-010 (single scenario)
- AGENT-CM: EMC-011 (single scenario)
- AGENT-CA: EMC-012 (single scenario)

---

## 6. Score Validation Rules

| Rule | Enforcement |
|------|------------|
| task_success must be boolean (0 or 1) | Schema validation at E6-T6 |
| groundedness_score must be in [0.0, 1.0] | Schema validation + BQ CHECK constraint |
| Both must be present for every run | Required field in run manifest; no NULLs |
| Grading is deterministic | Same response + grader input → same score |
| Manual reviews (EMC-006, EMC-012) signed off by MLE Lead | Audit trail in T3 with reviewer_id |

---

## 7. Appeal / Regrade Process

If a scorer disagrees with task_success or groundedness for a run:
1. MLE Lead opens a remediation ticket with evidence (response transcript + baseline)
2. Two reviewers independently re-score
3. If both agree with original score, original stands
4. If both agree on alternative score, run is re-graded
5. If disagreement persists, PVL decides as tiebreaker
6. Re-grade recorded in run manifest as `final_regrade = true`
