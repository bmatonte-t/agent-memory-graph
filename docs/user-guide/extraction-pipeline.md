# Extraction Pipeline

The extraction pipeline reads external data sources — documents and BigQuery tables — and ingests the extracted entities into the memory graph. It runs as part of the main Cloud Run service.

## Document Extraction

### Single document

```
POST /api/v1/extract/document
```

Extracts text blocks and named entities from a single PDF or PPTX file.

**Request body (multipart/form-data):**

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | file | Yes | PDF or PPTX file |
| `tenant_id` | string | Yes | Target tenant |
| `doc_type` | string | No | `pdf` or `pptx` (inferred from extension if omitted) |
| `entity_detection` | boolean | No | Whether to classify entities (default: true) |

**Example (curl):**

```bash
curl -X POST https://<service-url>/api/v1/extract/document \
  -F "file=@report-q3.pdf" \
  -F "tenant_id=latam-airlines" \
  -F "entity_detection=true"
```

**Response:**

```json
{
  "document_id": "doc_abc123",
  "entities_extracted": 34,
  "entities_written": 28,
  "entities_deduplicated": 6,
  "processing_ms": 1241
}
```

Entities that matched existing graph nodes with >85% fuzzy-match confidence are merged (not duplicated). The `entities_deduplicated` count tells you how many were merged rather than created as new nodes.

### Batch extraction

```
POST /api/v1/extract/batch
```

Same as single-document extraction but accepts multiple files and returns per-document results.

**Request body (multipart/form-data):**

| Field | Type | Description |
|---|---|---|
| `files` | file[] | One or more PDF/PPTX files |
| `tenant_id` | string | Target tenant |

**Response:**

```json
{
  "batch_id": "batch_xyz789",
  "documents": [
    {
      "filename": "report-q3.pdf",
      "entities_extracted": 34,
      "entities_written": 28,
      "entities_deduplicated": 6
    },
    {
      "filename": "architecture.pptx",
      "entities_extracted": 12,
      "entities_written": 11,
      "entities_deduplicated": 1
    }
  ],
  "total_entities_written": 39,
  "processing_ms": 2841
}
```

### Entity deduplication (standalone)

```
POST /api/v1/deduplicate
```

Run fuzzy deduplication against the existing graph without writing new nodes. Useful for previewing what would be merged before a batch ingestion.

**Request body:**

```json
{
  "tenant_id": "latam-airlines",
  "entities": [
    {"entity_type": "PERSON", "entity_id": "carlos_mendez", "attributes": {"name": "Carlos Méndez"}},
    {"entity_type": "PERSON", "entity_id": "c_mendez", "attributes": {"name": "C. Mendez"}}
  ]
}
```

**Response:**

```json
{
  "results": [
    {
      "entity_id": "carlos_mendez",
      "match": {"existing_node_id": "person_carlos_mendez", "confidence": 0.93, "match_type": "high"}
    },
    {
      "entity_id": "c_mendez",
      "match": {"existing_node_id": "person_carlos_mendez", "confidence": 0.87, "match_type": "high"}
    }
  ]
}
```

**Confidence tiers:**

| Confidence | Tier | Action on write |
|---|---|---|
| ≥ 0.85 | High | Auto-merge with existing node |
| 0.60 – 0.84 | Medium | Flag for human review |
| < 0.60 | Low | Create new node |

## BigQuery Ingestion

The BigQuery ingestion pipeline reads structured data from a BigQuery table and maps it to the graph. It is triggered manually or via Cloud Scheduler.

### How it works

1. **Schema analysis** — reads the BigQuery table schema and identifies meaningful columns
2. **POLE+ classification** — classifies columns into entity categories: People, Objects, Locations, Events, Organizations
3. **Graph mapping** — translates rows to `MemoryNode` + `MemoryEdge` pairs
4. **Batch write** — writes to Spanner in configurable batches (default: 500 rows)

### Triggering a BigQuery ingestion

The ingestion orchestrator is not yet exposed as a REST endpoint. Run it as a Cloud Run job or as an admin script:

```python
from src.pipelines.bigquery_ingestion.ingest_orchestrator import IngestOrchestrator

orchestrator = IngestOrchestrator(
    project_id="my-gcp-project",
    dataset_id="my_dataset",
    table_id="my_table",
    tenant_id="latam-airlines",
    batch_size=500
)
await orchestrator.run()
```

Or via Cloud Scheduler: create a job that calls a Cloud Run endpoint (coming in a future release — see [Backlog](../backlog.md)).

### Scheduling recurring ingestion

Use `cloud_scheduler_setup.py` to configure a Cloud Scheduler job that runs the ingestion on a cron schedule:

```python
from src.pipelines.bigquery_ingestion.cloud_scheduler_setup import setup_scheduler

setup_scheduler(
    project_id="my-gcp-project",
    region="us-east1",
    schedule="0 2 * * *",  # 2am daily
    table_ref="my_dataset.my_table",
    tenant_id="latam-airlines"
)
```

## Health check for extraction subsystem

The extraction API has its own health endpoint at the same Cloud Run service:

```
GET /api/v1/health
```

This is distinct from the main service health at `/health`.

## What gets extracted

### From documents (PDF/PPTX)

The document extractor produces:
- Named entities with labels (PERSON, ORGANIZATION, LOCATION, CONCEPT)
- Key-value pairs from structured sections
- Relationship hints (e.g., "Carlos owns the revenue dataset" → `DATA_OWNER_OF` edge candidate)

### From BigQuery

The POLE+ classifier maps table columns to entity categories:
- **People** — names, emails, employee IDs
- **Objects** — datasets, reports, files
- **Locations** — airports, routes, cities (LATAM-relevant)
- **Events** — flights, incidents, timestamps
- **Organizations** — squads, teams, departments

Unclassified columns are stored in the node's `Attributes` JSON field.
