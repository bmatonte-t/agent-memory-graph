# Testing Health Dashboard

## Core Metrics

- total_test_files: 71
- total_test_items: 873
- integration_test_files: 24
- integration_mock_references: 0
- integration_mock_density_average: 0.0
- duplicate_test_identifiers: 0

## Governance Status

- new_policy_violations: 0
- new_duplicate_identifier_violations: 0
- new_large_test_file_violations: 0

## Largest Test File Hotspots

| file | line_count | test_items | lines_per_test_item |
|---|---:|---:|---:|
| tests/unit/pipelines/test_extraction_orchestrator_phase_b3.py | 786 | 48 | 16.38 |
| tests/unit/pipelines/test_fuzzy_matcher_phase_b2.py | 769 | 74 | 10.39 |
| tests/unit/test_phase5c_evidence_service.py | 583 | 24 | 24.29 |
| tests/unit/test_mindmap_pipeline.py | 570 | 9 | 63.33 |
| tests/unit/pipelines/test_extraction_api_phase_c.py | 564 | 29 | 19.45 |
| tests/integration/test_phase4e_evidence_synthesis.py | 538 | 9 | 59.78 |
| tests/unit/pipelines/test_document_extractor_phase_b1.py | 518 | 44 | 11.77 |
| tests/unit/pipelines/test_bigquery_ingestion_phase_a1.py | 505 | 22 | 22.95 |
| tests/unit/pipelines/test_bigquery_ingestion_phase_a3.py | 497 | 22 | 22.59 |
| tests/unit/test_mcp_service.py | 488 | 1 | 488.0 |

## Duplicate Cluster Hotspots

| identifier | cluster_size |
|---|---:|
| none | 0 |

## Governance Cadence

- Weekly: `just test-governance-audit` and `just test-health-dashboard`.
- Monthly: update `reports/escaped-defects-log.md` with escaped defects and coverage gaps.
- Quarterly: refresh ownership and risks in `docs/testing-capability-matrix.md`.
