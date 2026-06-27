# Document Extraction Pipeline API Reference

## Base URL

```
https://extraction-api-<env>.<region>.run.app
```

Example:
- Development: `https://extraction-api-dev.us-central1.run.app`
- Staging: `https://extraction-api-staging.us-central1.run.app`
- Production: `https://extraction-api.us-central1.run.app`

## Authentication

### Development
No authentication required.

### Staging & Production
Request must include OAuth 2.0 token:

```bash
curl -H "Authorization: Bearer ${GCLOUD_TOKEN}" \
  https://extraction-api.us-central1.run.app/api/v1/health
```

Obtain token:
```bash
GCLOUD_TOKEN=$(gcloud auth print-identity-token)
```

## Endpoints

### 1. Health Check

**Purpose**: Verify API availability and readiness.

**Endpoint**
```
GET /api/v1/health
```

**Response** (200 OK)
```json
{
  "status": "healthy",
  "message": "Service is running",
  "api_version": "v1"
}
```

**Example**
```bash
curl https://extraction-api.us-central1.run.app/api/v1/health
```

---

### 2. Extract Single Document

**Purpose**: Extract text and entities from a single document.

**Endpoint**
```
POST /api/v1/extract/document
```

**Request Header**
```
Content-Type: application/json
```

**Request Body**
```json
{
  "file_path": "string",              # Required: Path to document
  "detect_entities": boolean           # Optional (default: true)
}
```

**Request Parameters**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_path` | string | Yes | Absolute or relative path to PDF/PPTX file |
| `detect_entities` | boolean | No | Enable entity extraction (default: true) |

**Response** (200 OK)
```json
{
  "success": true,
  "file_path": "string",
  "page_count": integer,
  "entity_count": integer,
  "message": "Document extracted successfully"
}
```

**Response Fields**

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Extraction succeeded (true/false) |
| `file_path` | string | Requested document path |
| `page_count` | integer | Number of pages/slides processed |
| `entity_count` | integer | Total entities extracted |
| `message` | string | Status message |

**Error Response** (400 Bad Request)
```json
{
  "success": false,
  "error_code": "DOCUMENT_EXTRACTION_ERROR",
  "error_message": "Unable to extract text from PDF",
  "detail": "File: /path/to/document.pdf"
}
```

**Error Response** (500 Internal Server Error)
```json
{
  "success": false,
  "error_code": "INTERNAL_ERROR",
  "error_message": "Unexpected error during extraction",
  "detail": "Optional details about the error"
}
```

**Example Request**
```bash
curl -X POST https://extraction-api.us-central1.run.app/api/v1/extract/document \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "reports/sales_report_2025.pdf",
    "detect_entities": true
  }'
```

**Example Response**
```json
{
  "success": true,
  "file_path": "reports/sales_report_2025.pdf",
  "page_count": 42,
  "entity_count": 156,
  "message": "Document extracted successfully"
}
```

---

### 3. Extract Batch with Deduplication

**Purpose**: Extract and deduplicate entities across multiple documents.

**Endpoint**
```
POST /api/v1/extract/batch
```

**Request Header**
```
Content-Type: application/json
```

**Request Body**
```json
{
  "file_paths": [string],                    # Required: List of file paths
  "detect_entities": boolean,                # Optional (default: true)
  "deduplicate_threshold": float,            # Optional (default: 0.85, range: 0.0-1.0)
  "include_low_confidence_matches": boolean  # Optional (default: false)
}
```

**Request Parameters**

| Field | Type | Required | Description | Range |
|-------|------|----------|-------------|-------|
| `file_paths` | array[string] | Yes | List of document paths | 1-100 documents |
| `detect_entities` | boolean | No | Enable entity extraction | default: true |
| `deduplicate_threshold` | float | No | Similarity threshold for duplicates | 0.0-1.0, default: 0.85 |
| `include_low_confidence_matches` | boolean | No | Include matches below 0.75 confidence | default: false |

**Threshold Interpretation**

- **0.95-1.0**: Exact or near-exact matches (HIGH confidence)
- **0.75-0.95**: Similar entities (MEDIUM confidence)
- **0.0-0.75**: Loose matches (LOW confidence, usually filtered)

**Response** (200 OK)
```json
{
  "success": true,
  "total_documents": integer,
  "failed_documents": integer,
  "total_entities": integer,
  "high_confidence_matches": integer,
  "medium_confidence_matches": integer,
  "low_confidence_matches": integer,
  "message": "Batch processing completed successfully"
}
```

**Response Fields**

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Batch processing succeeded (true/false) |
| `total_documents` | integer | Successfully processed documents |
| `failed_documents` | integer | Documents that failed extraction |
| `total_entities` | integer | Unique entities across all documents |
| `high_confidence_matches` | integer | HIGH confidence duplicate groups (>0.95) |
| `medium_confidence_matches` | integer | MEDIUM confidence duplicate groups (0.75-0.95) |
| `low_confidence_matches` | integer | LOW confidence duplicate groups (<0.75) |
| `message` | string | Status message |

**Error Response** (400 Bad Request)
```json
{
  "success": false,
  "error_code": "BATCH_PROCESSING_ERROR",
  "error_message": "Some documents failed processing",
  "detail": "Stage: entity_extraction"
}
```

**Example Request**
```bash
curl -X POST https://extraction-api.us-central1.run.app/api/v1/extract/batch \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": [
      "documents/2025_01_sales.pdf",
      "documents/2025_02_sales.pdf",
      "documents/2025_03_sales.pdf"
    ],
    "detect_entities": true,
    "deduplicate_threshold": 0.85,
    "include_low_confidence_matches": false
  }'
```

**Example Response**
```json
{
  "success": true,
  "total_documents": 3,
  "failed_documents": 0,
  "total_entities": 847,
  "high_confidence_matches": 145,
  "medium_confidence_matches": 67,
  "low_confidence_matches": 0,
  "message": "Batch processing completed successfully"
}
```

---

### 4. Root Information

**Purpose**: Get basic API information.

**Endpoint**
```
GET /
```

**Response** (200 OK)
```json
{
  "name": "Document Extraction & Entity Deduplication API",
  "version": "v1",
  "docs": "/docs"
}
```

**Example Request**
```bash
curl https://extraction-api.us-central1.run.app/
```

---

## OpenAPI Documentation

Interactive API documentation is available at:

```
https://extraction-api.us-central1.run.app/docs
```

This provides:
- Live endpoint testing (Swagger UI)
- Full schema documentation
- Request/response examples
- Authentication configuration

ReDoc documentation also available at:
```
https://extraction-api.us-central1.run.app/redoc
```

## Error Codes

| Code | HTTP Status | Description | Cause |
|------|-------------|-------------|-------|
| `DOCUMENT_EXTRACTION_ERROR` | 400 | Single document extraction failed | File not found, invalid format, or text extraction error |
| `BATCH_PROCESSING_ERROR` | 400 | Batch processing encountered errors | Some or all documents failed |
| `INTERNAL_ERROR` | 500 | Unexpected internal error | Server-side exception (non-extraction related) |
| `ENTITY_EXTRACTION_ERROR` | 400 | Entity detection failed | NER service unavailable or invalid entities |
| `DEDUPLICATION_ERROR` | 400 | Entity deduplication failed | Similarity computation error |

## Supported File Formats

- **PDF** (.pdf)
  - Text-based PDFs
  - Scanned PDFs (requires OCR, not supported in Phase E)
  - Encrypted PDFs (decryption requires password)

- **PowerPoint** (.pptx)
  - OOXML format (PowerPoint 2007+)
  - Text extraction from slides and speaker notes

## Rate Limiting

Production API has the following rate limits:

| Limit | Value |
|-------|-------|
| Requests per second | 100 |
| Concurrent extractions | 50 |
| Max document size | 100 MB |
| Max batch size | 100 documents |
| Timeout per request | 300 seconds |

Requests exceeding limits return:
```
429 Too Many Requests
Retry-After: 60
```

## Timeouts

- **Single document extraction**: 300 seconds (default)
- **Batch processing**: 300 seconds per batch (not per-document)
- **Health check**: 10 seconds

Long-running operations should implement polling:

```bash
# Initial request
REQUEST_ID=$(curl -X POST /api/v1/extract/batch ... | jq -r .request_id)

# Poll status
while true; do
  STATUS=$(curl /api/v1/status/${REQUEST_ID} | jq -r .status)
  [ "$STATUS" = "completed" ] && break
  sleep 5
done
```

Note: Request IDs not yet implemented in Phase E (future enhancement).

## Concurrent Request Handling

The API can handle multiple concurrent requests:

```bash
# Example: Extract 10 documents concurrently
for i in {1..10}; do
  curl -X POST /api/v1/extract/document \
    -d "{\"file_path\": \"doc$i.pdf\"}" &
done

# Wait for all background jobs
wait
```

Each concurrent request:
- Gets isolated extraction state
- Shares orchestrator thread pool
- Reports per-document errors without affecting others

## Response Headers

All responses include:

```
Content-Type: application/json
X-API-Version: v1
X-Request-ID: <unique-request-id>
X-Response-Time-Ms: <milliseconds>
```

**Example**
```
HTTP/1.1 200 OK
Content-Type: application/json
X-API-Version: v1
X-Request-ID: req_abc123def456
X-Response-Time-Ms: 245
```

## Request/Response Examples

### Python

```python
import httpx
import json

# Single document extraction
async with httpx.AsyncClient() as client:
    response = await client.post(
        "https://extraction-api.us-central1.run.app/api/v1/extract/document",
        json={
            "file_path": "report.pdf",
            "detect_entities": True
        }
    )
    result = response.json()
    print(f"Extracted {result['entity_count']} entities")
```

### JavaScript/Node.js

```javascript
const response = await fetch(
  'https://extraction-api.us-central1.run.app/api/v1/extract/batch',
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_paths: ['doc1.pdf', 'doc2.pdf'],
      deduplicate_threshold: 0.85
    })
  }
);

const result = await response.json();
console.log(`Processed ${result.total_documents} documents`);
```

### cURL

```bash
# With authentication (Staging/Production)
GCLOUD_TOKEN=$(gcloud auth print-identity-token)

curl -X POST https://extraction-api.us-central1.run.app/api/v1/extract/batch \
  -H "Authorization: Bearer ${GCLOUD_TOKEN}" \
  -H "Content-Type: application/json" \
  -d @- <<'EOF'
{
  "file_paths": ["report.pdf", "analysis.pptx"],
  "detect_entities": true,
  "deduplicate_threshold": 0.85
}
EOF
```

## Versioning

Current API version: `v1`

Future versions will be available at `/api/v2/*` with backward compatibility:
- v1 endpoints remain available
- v2 introduces new features without breaking v1
- Deprecation notice provided 6 months before v1 removal

## Status Page

Service health and incident status:

```
https://status.extraction-api.cloud/
```

Check this page during deployment windows and reported issues.

## Support & Feedback

For issues or feature requests:

1. Check API logs: `gcloud logging read "resource.service.name=extraction-api"`
2. Review OpenAPI docs: `https://extraction-api.us-central1.run.app/docs`
3. File issue on GitHub: Link to project issue tracker
4. Contact support team: support@example.com

## Version History

### v1.0.0 (Current)
- Single document extraction endpoint
- Batch extraction with deduplication
- Health check endpoint
- Support for PDF and PPTX formats
- Error handling with standard response format

### v0.9.0 (Beta)
- Initial API design
- Phase C testing completed with 24 tests

## Next Steps

1. Test endpoints against your document library
2. Monitor extraction quality and entity accuracy
3. Tune deduplicate_threshold based on use cases
4. Integrate with Agent Memory Graph Semantic layer
5. Set up monitoring and alerting
