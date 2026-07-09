# E3-T3 — Text Corpus Manifest and Metadata Tagging Schema

**Epic:** E3 — Data Design, Fixtures, and Provenance Preparation
**Task:** E3-T3
**Date:** 2026-07-08
**Status:** Approved
**Owner:** MLE Lead

---

## 1. Metadata Tagging Schema

All corpus objects stored in GCS must carry the following metadata tags. Tags are applied as object custom metadata at upload time.

### 1.1 Mandatory Tags

| Tag Key | Allowed Values | Description |
|---------|---------------|-------------|
| `corpus_source` | `synthetic`, `public_domain`, `cc_licensed` | Origin of the document |
| `corpus_type` | `product_manual`, `policy_doc`, `sop`, `customer_comm`, `integration_event_narrative`, `faq` | Document category |
| `sensitivity_class` | `public`, `internal`, `confidential` | Data sensitivity level (all campaign corpus is `public` or `internal`) |
| `language` | `en`, `pt`, `es` | ISO 639-1 language code |
| `date_created` | ISO 8601 date `YYYY-MM-DD` | Document creation or generation date |
| `provenance_id` | `PROV-07` through `PROV-12` | Links to E3-T6 provenance register |
| `version` | Semantic version string `v{major}.{minor}` | Document version |
| `benchmark_relevance` | `agent_ec`, `agent_cc`, `agent_ta`, `agent_ca`, `all`, `none` | Which agents reference this corpus type |

### 1.2 Optional Tags

| Tag Key | Example Value | Description |
|---------|--------------|-------------|
| `domain` | `returns_policy`, `shipping`, `onboarding` | Fine-grained topic |
| `product_category` | `electronics`, `apparel` | Relevant product category if applicable |
| `synthetic_seed` | `12345` | Random seed used to generate synthetic content |

---

## 2. GCS Storage Layout

All corpus objects are stored in `{{GCS_CORPUS_BUCKET}}` under the following prefix hierarchy:

```
{{GCS_CORPUS_BUCKET}}/
├── product-manuals/
│   ├── electronics/
│   ├── apparel/
│   └── home-goods/
├── policy-docs/
│   ├── returns/
│   ├── shipping/
│   ├── privacy/
│   └── terms-of-service/
├── sop-documents/
│   ├── support-ops/
│   ├── returns-processing/
│   └── escalation-procedures/
├── customer-comms/
│   ├── templates/
│   └── synthetic-samples/
├── integration-event-narratives/
│   └── synthetic/
└── faq/
    ├── customer-facing/
    └── internal-hr/
```

---

## 3. Corpus Manifest

### CORP-01 — Product Manuals (Synthetic)

| Field | Value |
|-------|-------|
| **Corpus ID** | `CORP-01` |
| **Type** | `product_manual` |
| **Source** | Synthetic (template-generated) |
| **Sensitivity** | `public` |
| **Language** | `en` |
| **Format** | PDF, plain text (`.txt`) |
| **Target Count** | 500 documents (10 per product category × 50 categories) |
| **Avg Size Per Doc** | ~20 KB |
| **Total Size** | ~10 MB |
| **GCS Prefix** | `product-manuals/` |
| **Generation Method** | Python template engine with `faker`; one manual per product sub-category |
| **Content Structure** | Title, overview, specifications, installation/setup, troubleshooting (5–10 pages per doc) |
| **Provenance ID** | `PROV-07` |
| **Benchmark Agents** | `agent_ec`, `agent_cc` |
| **No-Evidence Coverage** | Includes 10% of manuals for products not in Spanner graph (tests no-evidence abstention) |

---

### CORP-02 — Policy Documents (Synthetic)

| Field | Value |
|-------|-------|
| **Corpus ID** | `CORP-02` |
| **Type** | `policy_doc` |
| **Source** | Synthetic (template-generated) |
| **Sensitivity** | `public` |
| **Language** | `en` |
| **Format** | PDF, plain text |
| **Target Count** | 40 documents (returns, shipping, privacy, ToS, data retention — 8 versions per type) |
| **Avg Size Per Doc** | ~50 KB |
| **Total Size** | ~2 MB |
| **GCS Prefix** | `policy-docs/` |
| **Content Structure** | Policy name, effective date, scope, rules, exceptions, contact information |
| **Provenance ID** | `PROV-08` |
| **Benchmark Agents** | `agent_ec`, `agent_cc`, `all` |
| **Note** | Policy documents are the primary grounding source for AGENT-EC policy queries |

---

### CORP-03 — Standard Operating Procedures (Synthetic)

| Field | Value |
|-------|-------|
| **Corpus ID** | `CORP-03` |
| **Type** | `sop` |
| **Source** | Synthetic (template-generated) |
| **Sensitivity** | `internal` |
| **Language** | `en` |
| **Format** | Markdown, PDF |
| **Target Count** | 60 documents (support ops, returns processing, escalation procedures) |
| **Avg Size Per Doc** | ~30 KB |
| **Total Size** | ~2 MB |
| **GCS Prefix** | `sop-documents/` |
| **Content Structure** | SOP ID, purpose, scope, step-by-step procedure, decision trees, escalation contacts |
| **Provenance ID** | `PROV-09` |
| **Benchmark Agents** | `agent_ec`, `agent_ta` |
| **Note** | SOPs are `internal` sensitivity — AGENT-CC is explicitly not permitted to retrieve them |

---

### CORP-04 — Synthetic Customer Communications (Templates and Samples)

| Field | Value |
|-------|-------|
| **Corpus ID** | `CORP-04` |
| **Type** | `customer_comm` |
| **Source** | Synthetic |
| **Sensitivity** | `public` (templates); `internal` (synthetic samples with ticket context) |
| **Language** | `en` |
| **Format** | Plain text, JSON (email/chat message threads) |
| **Target Count** | 200 template documents + 1,000 synthetic sample threads |
| **Avg Size Per Doc** | ~5 KB |
| **Total Size** | ~6 MB |
| **GCS Prefix** | `customer-comms/` |
| **Content Structure** | Message threads with roles (customer/agent), timestamps (synthetic), topic category |
| **Provenance ID** | `PROV-10` |
| **Benchmark Agents** | `agent_cc`, `agent_ta` |
| **Note** | All customer names are synthetic; no real email addresses; used to test AGENT-CC conversation grounding |

---

### CORP-05 — Integration Event Narratives (Synthetic)

| Field | Value |
|-------|-------|
| **Corpus ID** | `CORP-05` |
| **Type** | `integration_event_narrative` |
| **Source** | Synthetic |
| **Sensitivity** | `internal` |
| **Language** | `en` |
| **Format** | JSON, plain text |
| **Target Count** | 500 event narrative documents (100 per integration type) |
| **Avg Size Per Doc** | ~10 KB |
| **Total Size** | ~5 MB |
| **GCS Prefix** | `integration-event-narratives/synthetic/` |
| **Content Structure** | Event type, timestamp, source system, payload summary, action taken, outcome |
| **Provenance ID** | `PROV-11` |
| **Benchmark Agents** | `agent_si`, `agent_cm`, `agent_ta` |
| **Note** | Used to test AGENT-SI routing recall and AGENT-TA task dispatch grounding |

---

### CORP-06 — FAQ Documents (Mixed: Public-Domain + Synthetic)

| Field | Value |
|-------|-------|
| **Corpus ID** | `CORP-06` |
| **Type** | `faq` |
| **Source** | Mixed: CC0 / public domain (government consumer FAQ pages) + synthetic internal HR FAQ |
| **Sensitivity** | `public` (customer-facing), `internal` (HR FAQ) |
| **Language** | `en` |
| **Format** | Plain text, HTML scraped and cleaned |
| **Target Count** | 50 customer-facing FAQs (public domain) + 50 internal HR FAQs (synthetic) |
| **Avg Size Per Doc** | ~10 KB |
| **Total Size** | ~1 MB |
| **GCS Prefix** | `faq/` |
| **Provenance ID** | `PROV-12` |
| **Benchmark Agents** | `agent_cc` (customer FAQ), `agent_ec` (HR FAQ) |
| **Public Domain Sources** | US FTC consumer FAQ pages (public domain); FCC consumer guides (public domain) |

---

## 4. Total Corpus Summary

| Corpus ID | Type | Count | Size | Sensitivity | Provenance |
|-----------|------|-------|------|------------|-----------|
| CORP-01 | Product manuals | 500 docs | ~10 MB | public | PROV-07 |
| CORP-02 | Policy docs | 40 docs | ~2 MB | public | PROV-08 |
| CORP-03 | SOPs | 60 docs | ~2 MB | internal | PROV-09 |
| CORP-04 | Customer comms | 1,200 items | ~6 MB | mixed | PROV-10 |
| CORP-05 | Event narratives | 500 docs | ~5 MB | internal | PROV-11 |
| CORP-06 | FAQs | 100 docs | ~1 MB | mixed | PROV-12 |
| **Total** | — | **~2,400 items** | **~26 MB** | — | — |

---

## 5. Ingestion Readiness Checklist (Verified at E6-T2)

| Corpus | Generation/Download Script | Metadata Tags Applied | Uploaded to GCS | Object Inventory Complete |
|--------|--------------------------|----------------------|----------------|--------------------------|
| CORP-01 | ☐ | ☐ | ☐ | ☐ |
| CORP-02 | ☐ | ☐ | ☐ | ☐ |
| CORP-03 | ☐ | ☐ | ☐ | ☐ |
| CORP-04 | ☐ | ☐ | ☐ | ☐ |
| CORP-05 | ☐ | ☐ | ☐ | ☐ |
| CORP-06 | ☐ | ☐ | ☐ | ☐ |
