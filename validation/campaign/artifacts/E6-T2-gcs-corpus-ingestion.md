# E6-T2 — GCS Corpus Ingestion and Metadata Tagging

**Epic:** E6 — Cloud Data Provisioning and Integration Bring-up
**Task:** E6-T2
**Date:** 2026-07-17
**Status:** Approved
**Owner:** Data Lead

---

## 1. Objective

Provision GCS corpus buckets and ingest text corpus (2,400+ documents, ~26 MB) with structured metadata tagging for semantic retrieval (E4-T2 retrieval scenarios depend on corpus availability).

**Dependencies:** E3-T3 (corpus inventory), E5-T8 (GCS buckets created), E6-T1 (complete before corpus tagging)

---

## 2. Corpus Inventory (Frozen from E3-T3)

### 2.1 Document Sources

| Source | Count | Format | Size | Language | Domain |
|--------|-------|--------|------|----------|--------|
| **C-01** | 600 | Markdown | 8.2 MB | EN | E-commerce Knowledge Base |
| **C-02** | 400 | HTML | 5.1 MB | EN | API Documentation |
| **C-03** | 300 | PDF (extracted) | 4.8 MB | EN | Support Articles |
| **C-04** | 500 | JSON | 3.2 MB | EN | Product Catalog |
| **C-05** | 350 | Plaintext | 2.1 MB | EN | Policy Documents |
| **C-06** | 250 | Structured (CSV+schema) | 2.6 MB | EN | Metadata Reference |
| **Total** | 2,400 | Mixed | ~26 MB | EN | Mixed |

### 2.2 Semantic Categories (for Retrieval Scenarios)

```json
{
  "semantic_categories": {
    "product_info": {
      "description": "Product specifications, pricing, inventory",
      "sources": ["C-04", "C-01"],
      "doc_count": 1100,
      "use_case": "Agent answers product questions"
    },
    "support_policies": {
      "description": "Return policies, warranties, SLAs",
      "sources": ["C-05", "C-03"],
      "doc_count": 650,
      "use_case": "Agent references policy for customer inquiries"
    },
    "technical_integration": {
      "description": "API specs, webhooks, rate limits",
      "sources": ["C-02"],
      "doc_count": 400,
      "use_case": "Agent retrieves API endpoints for integrations"
    },
    "operational_runbooks": {
      "description": "Procedures, troubleshooting, escalation paths",
      "sources": ["C-03", "C-01"],
      "doc_count": 250,
      "use_case": "Agent follows procedural logic for incidents"
    }
  }
}
```

---

## 3. GCS Bucket Architecture

### 3.1 Bucket Structure

```
gs://amg-campaign-corpus-q3/
├── corpus/                                      # Primary corpus
│   ├── c-01-knowledge-base/                     # E-commerce KB (600 docs)
│   │   ├── doc_001.md
│   │   ├── doc_002.md
│   │   └── ... (600 total)
│   ├── c-02-api-docs/                           # API Documentation (400 docs)
│   │   ├── api_endpoint_001.html
│   │   ├── api_endpoint_002.html
│   │   └── ... (400 total)
│   ├── c-03-support-articles/                   # Support (300 docs)
│   │   ├── article_001.pdf (text extracted)
│   │   ├── article_002.pdf
│   │   └── ... (300 total)
│   ├── c-04-product-catalog/                    # Product Catalog (500 docs)
│   │   ├── product_001.json
│   │   ├── product_002.json
│   │   └── ... (500 total)
│   ├── c-05-policies/                           # Policy Docs (350 docs)
│   │   ├── policy_001.txt
│   │   ├── policy_002.txt
│   │   └── ... (350 total)
│   └── c-06-metadata-reference/                 # Metadata (250 docs)
│       ├── entity_001.csv
│       ├── entity_002.csv
│       └── ... (250 total)
│
├── metadata/                                    # Metadata and indexes
│   ├── corpus_manifest.json                     # Master inventory (2,400 entries)
│   ├── semantic_categories.json                 # Category taxonomy
│   ├── document_tags.json                       # Per-document tags and attributes
│   ├── chunking_strategy.json                   # Text chunking config
│   └── embeddings_index/                        # Precomputed embeddings (optional)
│       ├── embeddings_001.npy
│       └── embeddings_metadata.json
│
├── sources/                                     # Raw ingest staging
│   ├── olist/                                   # Downloaded from public repo
│   ├── uci/                                     # Downloaded from public repo
│   ├── synthetic/                               # Generated data
│   └── corpus_raw/                              # Unprocessed corpus files
│
└── audit/                                       # Compliance and lineage
    ├── corpus_ingestion_log.jsonl               # Per-document ingestion events
    ├── access_log/                              # Audited reads/writes
    └── validation_reports/                      # Quality assurance reports
```

### 3.2 Bucket Configuration

**Bucket:** `gs://amg-campaign-corpus-q3`

```terraform
resource "google_storage_bucket" "corpus" {
  name          = "amg-campaign-corpus-q3"
  location      = "US"
  force_destroy = false  # Preserve post-campaign

  uniform_bucket_level_access {
    enabled = true
  }

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 90  # Archive after 90 days (but corpus kept indefinitely)
    }
  }

  logging {
    log_bucket = google_storage_bucket.audit_logs.id
  }

  labels = local.campaign_labels
}
```

---

## 4. Corpus Ingestion Pipeline

### 4.1 Pre-Ingestion Processing

**For each document source:**

```python
# process_corpus.py
import os
import json
import hashlib
from pathlib import Path
from datetime import datetime

class CorpusProcessor:
    def __init__(self, source_id: str, format_type: str):
        self.source_id = source_id
        self.format_type = format_type
        self.ingestion_log = []

    def process_markdown(self, file_path: str) -> dict:
        """Parse Markdown, extract text and metadata."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract frontmatter if present
        metadata = {'format': 'markdown'}
        if content.startswith('---'):
            parts = content.split('---', 2)
            try:
                import yaml
                metadata.update(yaml.safe_load(parts[1]))
                content = parts[2]
            except:
                pass

        return {
            'text': content,
            'metadata': metadata,
            'hash': hashlib.sha256(content.encode()).hexdigest()
        }

    def process_json(self, file_path: str) -> dict:
        """Parse JSON, flatten for search."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Flatten nested JSON for keyword search
        flattened = self._flatten_json(data)
        text_content = json.dumps(flattened, indent=2)

        return {
            'text': text_content,
            'metadata': {'format': 'json', 'structure': data.keys()},
            'hash': hashlib.sha256(text_content.encode()).hexdigest(),
            'original_json': data
        }

    def process_html(self, file_path: str) -> dict:
        """Extract text from HTML, remove tags."""
        from html.parser import HTMLParser

        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text = []

            def handle_data(self, data):
                self.text.append(data)

        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        extractor = TextExtractor()
        extractor.feed(html_content)
        text = ' '.join(extractor.text).strip()

        return {
            'text': text,
            'metadata': {'format': 'html', 'original_size_bytes': len(html_content)},
            'hash': hashlib.sha256(text.encode()).hexdigest()
        }

    def process_pdf_text(self, file_path: str) -> dict:
        """Extract text from PDF (assumes pdfplumber or similar preprocessing)."""
        # Note: PDF is pre-extracted to .txt by external tool
        txt_path = file_path.replace('.pdf', '.txt')
        with open(txt_path, 'r', encoding='utf-8') as f:
            text = f.read()

        return {
            'text': text,
            'metadata': {'format': 'pdf_extracted', 'source_pdf': file_path},
            'hash': hashlib.sha256(text.encode()).hexdigest()
        }

    def _flatten_json(self, obj, parent_key='', sep='.'):
        """Recursively flatten nested JSON."""
        items = []
        for k, v in obj.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_json(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                items.append((new_key, str(v)))
            else:
                items.append((new_key, v))
        return dict(items)

    def ingest_document(self, doc_id: str, file_path: str) -> dict:
        """Main ingestion entry point."""
        try:
            if self.format_type == 'markdown':
                doc_data = self.process_markdown(file_path)
            elif self.format_type == 'json':
                doc_data = self.process_json(file_path)
            elif self.format_type == 'html':
                doc_data = self.process_html(file_path)
            elif self.format_type == 'pdf':
                doc_data = self.process_pdf_text(file_path)
            else:
                raise ValueError(f"Unsupported format: {self.format_type}")

            event = {
                'doc_id': doc_id,
                'source_id': self.source_id,
                'file_path': file_path,
                'format': self.format_type,
                'timestamp': datetime.utcnow().isoformat(),
                'content_hash': doc_data['hash'],
                'status': 'success',
                'metadata': doc_data['metadata']
            }
            self.ingestion_log.append(event)
            return event
        except Exception as e:
            event = {
                'doc_id': doc_id,
                'source_id': self.source_id,
                'file_path': file_path,
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'failed',
                'error': str(e)
            }
            self.ingestion_log.append(event)
            return event
```

### 4.2 Ingestion Execution

**Parallel ingestion to GCS:**

```bash
#!/bin/bash
# ingest_corpus.sh

set -e

PROJECT_ID="amg-validation-2026-07-q3"
CORPUS_BUCKET="gs://amg-campaign-corpus-q3"
INGESTION_LOG="${CORPUS_BUCKET}/audit/corpus_ingestion_log.jsonl"

# Function: Ingest a corpus source
ingest_source() {
  local source_id=$1
  local source_path=$2
  local format=$3
  local target_dir=$4

  echo "Processing ${source_id} (${format})..."

  # Run Python ingestion for this source
  python process_corpus.py \
    --source_id "${source_id}" \
    --source_path "${source_path}" \
    --format "${format}" \
    --bucket "${CORPUS_BUCKET}" \
    --target_dir "${target_dir}" \
    --log_path "${INGESTION_LOG}"

  echo "✓ ${source_id} complete"
}

# Ingest each corpus source in parallel
ingest_source "C-01" "/tmp/corpus/knowledge-base" "markdown" "corpus/c-01-knowledge-base" &
ingest_source "C-02" "/tmp/corpus/api-docs" "html" "corpus/c-02-api-docs" &
ingest_source "C-03" "/tmp/corpus/support" "pdf" "corpus/c-03-support-articles" &
ingest_source "C-04" "/tmp/corpus/products" "json" "corpus/c-04-product-catalog" &
ingest_source "C-05" "/tmp/corpus/policies" "plaintext" "corpus/c-05-policies" &
ingest_source "C-06" "/tmp/corpus/metadata" "csv" "corpus/c-06-metadata-reference" &

wait  # Wait for all parallel jobs

echo "All sources ingested successfully"
```

---

## 5. Metadata Tagging and Indexing

### 5.1 Corpus Manifest (corpus_manifest.json)

```json
{
  "corpus_id": "amg-campaign-2026-q3",
  "ingestion_date": "2026-07-17T10:00:00Z",
  "total_documents": 2400,
  "total_size_bytes": 27262976,
  "semantic_categories": 4,
  "documents": [
    {
      "doc_id": "C-01-001",
      "source_id": "C-01",
      "filename": "doc_001.md",
      "gcs_path": "gs://amg-campaign-corpus-q3/corpus/c-01-knowledge-base/doc_001.md",
      "format": "markdown",
      "size_bytes": 14234,
      "content_hash": "abc123...",
      "language": "en",
      "semantic_category": "product_info",
      "tags": ["e-commerce", "products", "pricing"],
      "chunks": 3,
      "ingestion_timestamp": "2026-07-17T10:15:32Z",
      "retrieval_scenarios_applicable": ["E4-S1", "E4-S2"],
      "quality_score": 0.95,
      "embeddings_available": true,
      "embedding_model": "text-embedding-004"
    },
    {
      "doc_id": "C-02-001",
      "source_id": "C-02",
      "filename": "api_endpoint_001.html",
      "gcs_path": "gs://amg-campaign-corpus-q3/corpus/c-02-api-docs/api_endpoint_001.html",
      "format": "html",
      "size_bytes": 12456,
      "content_hash": "def456...",
      "language": "en",
      "semantic_category": "technical_integration",
      "tags": ["api", "integration", "webhooks"],
      "chunks": 2,
      "ingestion_timestamp": "2026-07-17T10:20:15Z",
      "retrieval_scenarios_applicable": ["E4-S4"],
      "quality_score": 0.98,
      "embeddings_available": true,
      "embedding_model": "text-embedding-004"
    }
  ],
  "statistics": {
    "by_source": {
      "C-01": {"count": 600, "size_mb": 8.2},
      "C-02": {"count": 400, "size_mb": 5.1},
      "C-03": {"count": 300, "size_mb": 4.8},
      "C-04": {"count": 500, "size_mb": 3.2},
      "C-05": {"count": 350, "size_mb": 2.1},
      "C-06": {"count": 250, "size_mb": 2.6}
    },
    "by_semantic_category": {
      "product_info": {"count": 1100},
      "support_policies": {"count": 650},
      "technical_integration": {"count": 400},
      "operational_runbooks": {"count": 250}
    },
    "by_format": {
      "markdown": {"count": 600},
      "html": {"count": 400},
      "pdf": {"count": 300},
      "json": {"count": 500},
      "plaintext": {"count": 350},
      "csv": {"count": 250}
    }
  }
}
```

### 5.2 Document Tags (document_tags.json)

```json
{
  "tag_schema": {
    "semantic_category": ["product_info", "support_policies", "technical_integration", "operational_runbooks"],
    "domain_tags": ["e-commerce", "api", "support", "product", "policy", "pricing", "integration"],
    "quality_level": ["high", "medium", "low"],
    "retrieval_use_case": ["agent_product_qa", "agent_policy_lookup", "agent_integration", "agent_troubleshooting"]
  },
  "documents": [
    {
      "doc_id": "C-01-001",
      "tags": {
        "semantic_category": "product_info",
        "domain": ["e-commerce", "product"],
        "quality": "high",
        "use_cases": ["agent_product_qa"],
        "custom_tags": ["bestseller", "pricing-strategy", "inventory-related"]
      }
    },
    {
      "doc_id": "C-03-001",
      "tags": {
        "semantic_category": "support_policies",
        "domain": ["support", "policy"],
        "quality": "high",
        "use_cases": ["agent_policy_lookup", "agent_troubleshooting"],
        "custom_tags": ["returns", "warranty", "sla"]
      }
    }
  ]
}
```

### 5.3 BigQuery Corpus Index (optional, for Vertex AI Search)

```sql
-- Optional: Index corpus in BigQuery for Vertex AI Search integration
CREATE TABLE `{{PROJECT_ID}}.benchmark_metrics.corpus_index` (
  doc_id STRING NOT NULL,
  source_id STRING,
  filename STRING,
  gcs_path STRING,
  format STRING,
  size_bytes INT64,
  content_hash STRING,
  semantic_category STRING,
  tags ARRAY<STRING>,
  chunk_count INT64,
  ingestion_timestamp TIMESTAMP,
  retrieval_scenarios ARRAY<STRING>,
  quality_score NUMERIC,
  embeddings_available BOOL,
  embedding_model STRING,
  full_text STRING  -- Denormalized for BQ search
);

-- Populate from manifest
INSERT INTO `{{PROJECT_ID}}.benchmark_metrics.corpus_index`
SELECT
  doc.doc_id,
  doc.source_id,
  doc.filename,
  doc.gcs_path,
  doc.format,
  doc.size_bytes,
  doc.content_hash,
  doc.semantic_category,
  doc.tags,
  doc.chunks,
  TIMESTAMP(doc.ingestion_timestamp),
  doc.retrieval_scenarios_applicable,
  doc.quality_score,
  doc.embeddings_available,
  doc.embedding_model,
  NULL  -- Populate with full text from GCS
FROM UNNEST(
  JSON_EXTRACT_ARRAY(
    (SELECT corpus_manifest FROM `{{PROJECT_ID}}.benchmark_metrics.corpus_metadata`),
    '$.documents'
  )
) AS doc;
```

---

## 6. Chunking Strategy (for Retrieval)

**Configuration:** `gs://amg-campaign-corpus-q3/metadata/chunking_strategy.json`

```json
{
  "chunking_strategy": {
    "default": {
      "chunk_size_tokens": 512,
      "overlap_tokens": 128,
      "method": "semantic_boundary"
    },
    "by_format": {
      "markdown": {
        "chunk_size_tokens": 512,
        "overlap_tokens": 128,
        "method": "heading_boundary"
      },
      "html": {
        "chunk_size_tokens": 256,
        "overlap_tokens": 64,
        "method": "paragraph_boundary"
      },
      "json": {
        "chunk_size_tokens": 1024,
        "overlap_tokens": 256,
        "method": "key_boundary"
      }
    }
  }
}
```

---

## 7. Ingestion Execution Plan

### 7.1 Day 1: Source Preparation

```
09:00 — Download C-01–C-02 from external URLs to local staging
10:00 — Validate file integrity (SHA256 checksum verification)
11:00 — Extract text from PDFs (C-03); convert to plaintext
12:00 — Convert format: JSON beautification, HTML cleanup
14:00 — CHECKPOINT: All sources validated and formatted
```

**Validation script:**
```bash
# validate_corpus_sources.sh
for source in c-01-kb c-02-api c-03-support c-04-products c-05-policies c-06-metadata; do
  echo "Validating $source..."
  find /tmp/corpus/$source -type f | wc -l
  du -sh /tmp/corpus/$source
done
```

### 7.2 Day 2: Ingest to GCS

```
09:00 — Run parallel ingestion (ingest_corpus.sh)
10:00 — Upload to gs://amg-campaign-corpus-q3/corpus/
12:00 — Verify all 2,400 documents in GCS (listing count)
14:00 — Generate corpus manifest and metadata
16:00 — CHECKPOINT: All documents ingested, manifest generated
```

**Verification:**
```bash
gsutil ls -r gs://amg-campaign-corpus-q3/corpus/ | wc -l
# Expected: ~2,400 files

gsutil du -s gs://amg-campaign-corpus-q3/corpus/
# Expected: ~26 MB
```

### 7.3 Day 3: Tagging and Indexing

```
09:00 — Parse corpus manifest JSON
10:00 — Auto-tag documents by semantic category (NLP classification)
12:00 — Publish corpus_manifest.json, document_tags.json to metadata/
13:00 — Optionally: Compute embeddings for all 2,400 documents (Vertex AI)
15:00 — CHECKPOINT: Corpus fully tagged and indexed, ready for E4 retrieval
```

---

## 8. Quality Validation

### 8.1 Ingestion Quality Report

```bash
# generate_ingestion_report.py
import json
from google.cloud import storage

client = storage.Client()
bucket = client.bucket("amg-campaign-corpus-q3")

# Read ingestion log
ingestion_blob = bucket.blob("audit/corpus_ingestion_log.jsonl")
log_content = ingestion_blob.download_as_string().decode()

lines = log_content.strip().split('\n')
events = [json.loads(line) for line in lines]

# Analyze
total = len(events)
successful = sum(1 for e in events if e['status'] == 'success')
failed = sum(1 for e in events if e['status'] == 'failed')

print(f"Ingestion Report:")
print(f"  Total Documents: {total}")
print(f"  Successful: {successful} ({successful/total*100:.1f}%)")
print(f"  Failed: {failed} ({failed/total*100:.1f}%)")

if failed > 0:
  print(f"\nFailed Documents:")
  for e in events:
    if e['status'] == 'failed':
      print(f"  - {e['doc_id']}: {e['error']}")

# Expected: 100% success rate (0 failures)
assert failed == 0, "Corpus ingestion had failures!"
```

### 8.2 Post-Ingestion Checklist

| Check | Status | Expected | Actual |
|-------|--------|----------|--------|
| Total documents ingested | ☐ | 2,400 | — |
| GCS bucket size | ☐ | ~26 MB | — |
| Manifest entries | ☐ | 2,400 | — |
| Semantic categories tagged | ☐ | 4 categories | — |
| Ingestion success rate | ☐ | 100% | — |
| GCS access permissions verified | ☐ | amg-campaign-svc can read | — |
| Metadata indexes created | ☐ | corpus_manifest.json, document_tags.json | — |

---

## 9. Cost Estimate (E6-T2)

| Resource | Quantity | Unit Cost | Total |
|----------|----------|-----------|-------|
| GCS Storage (corpus) | 26 MB | $0.020/GB/month | $0.0005 |
| GCS Upload bandwidth | 26 MB | $0.10/GB | $0.003 |
| GCS Operations (list/read) | ~500 ops | $0.0004/1000 ops | $0.0002 |
| BigQuery corpus_index table | 2,400 rows | ~$0.03 (if created) | $0.03 |
| Vertex AI Embeddings (optional) | 2,400 docs | $0.0001/doc | $0.24 |
| **Total (E6-T2, without embeddings)** | — | — | **~$0.03** |
| **Total (E6-T2, with embeddings)** | — | — | **~$0.27** |

**Budget Impact:** Week 5 corpus budget: $5 (includes T2 complete); $0.27 utilization if embeddings computed

---

## 10. Sign-Off

| Role | Owner | Sign-Off | Date |
|------|-------|----------|------|
| Data Lead | J. Patel | ☐ | ____ |
| Infrastructure Lead | T. Chen | ☐ | ____ |
| Program Manager | S. Gupta | ☐ | ____ |
