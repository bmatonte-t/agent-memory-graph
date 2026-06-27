# Document Extraction Pipeline Quickstart

Get the document extraction pipeline running locally in 5 minutes.

## Prerequisites

- **Python 3.14+**
- **uv** (Python package manager)
- **just** (command runner)
- **Git**
- **Docker** (for container testing)

### Install Prerequisites

**macOS**
```bash
# Install uv
brew install uv

# Install just
brew install just

# Verify installations
uv --version
just --version
```

**Linux**
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install just
cargo install just

# Verify installations
uv --version
just --version
```

## 1. Clone Repository

```bash
git clone https://github.com/bmatonte-t/agent-memory-graph.git
cd agent-memory-graph
```

## 2. Install Dependencies

```bash
# Install all project dependencies
uv sync --all-groups

# Verify installation
uv --version
ls -la .venv
```

Expected output:
```
venv created at: .venv
```

## 3. Run Local API Server

```bash
# Start FastAPI server with hot-reload
uv run uvicorn src.pipelines.api.extraction_api:app --reload

# Expected output:
# INFO:     Uvicorn running on http://127.0.0.1:8000
# INFO:     Application startup complete
```

The API is now available at: `http://127.0.0.1:8000`

## 4. Test Health Endpoint

In a separate terminal:

```bash
# Health check
curl http://127.0.0.1:8000/api/v1/health

# Expected response:
# {
#   "status": "healthy",
#   "message": "Service is running",
#   "api_version": "v1"
# }
```

## 5. Extract a Single Document

### Prepare Test Document

```bash
# Create a test PDF (or use existing document)
# For this example, we'll create a minimal test document

# Using macOS:
touch test_document.txt
echo "Company: ACME Corp
Founded: 2025
CEO: John Doe
Revenue: $1B" > test_document.txt
```

### Extract

```bash
curl -X POST http://127.0.0.1:8000/api/v1/extract/document \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "test_document.txt",
    "detect_entities": true
  }'

# Expected response:
# {
#   "success": true,
#   "file_path": "test_document.txt",
#   "page_count": 1,
#   "entity_count": 3,
#   "message": "Document extracted successfully"
# }
```

## 6. Extract Multiple Documents (Batch)

```bash
# Create additional test documents
echo "Product: Widget A
Price: $99.99
Supplier: ABC Inc" > doc1.txt

echo "Product: Widget B
Price: $149.99
Supplier: XYZ Ltd" > doc2.txt

# Batch extraction with deduplication
curl -X POST http://127.0.0.1:8000/api/v1/extract/batch \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": ["doc1.txt", "doc2.txt"],
    "detect_entities": true,
    "deduplicate_threshold": 0.85,
    "include_low_confidence_matches": false
  }'

# Expected response:
# {
#   "success": true,
#   "total_documents": 2,
#   "failed_documents": 0,
#   "total_entities": 6,
#   "high_confidence_matches": 0,
#   "medium_confidence_matches": 0,
#   "low_confidence_matches": 0,
#   "message": "Batch processing completed successfully"
# }
```

## 7. Access OpenAPI Documentation

Visit interactive API documentation:

```
http://127.0.0.1:8000/docs
```

Features:
- Test endpoints directly in browser
- View all request/response schemas
- Try different parameter combinations
- See live API responses

Alternative ReDoc documentation:
```
http://127.0.0.1:8000/redoc
```

## 8. Run Tests

### Run All Tests

```bash
# Run full test suite
just test

# Or using pytest directly
uv run pytest tests/ -v
```

### Run Only Extraction Pipeline Tests

```bash
# Unit tests (all phases)
uv run pytest tests/unit/deployment/ -v
uv run pytest tests/unit/pipelines/ -v

# Integration tests (Phase E)
uv run pytest tests/integration/test_extraction_pipeline_phase_e.py -v
```

### Run Tests with Coverage

```bash
# Generate coverage report
just test-coverage

# View HTML report
open htmlcov/index.html
```

## 9. Quality Checks

### Run All Quality Gates

```bash
# Lint, type-check, format, test, coverage
just check-all

# Expected output:
# ✓ Linting clean
# ✓ Type checking passed
# ✓ Formatting correct
# ✓ All tests passing (746 tests)
# ✓ Docstring coverage: 95%+
```

### Individual Checks

```bash
# Lint code
just lint

# Type check
just check-types

# Check formatting
just check-format

# Format code (auto-fix)
just format

# Coverage report
just test-coverage

# Docstring coverage
just docstring-coverage
```

## 10. Build Docker Container

### Build Locally

```bash
# Build Docker image
docker build -t extraction-api:dev .

# Run container locally
docker run -p 8000:8000 extraction-api:dev

# Test from another terminal
curl http://127.0.0.1:8000/api/v1/health
```

### Push to Container Registry

```bash
# Set variables
export PROJECT_ID=my-gcp-project
export IMAGE=gcr.io/${PROJECT_ID}/extraction-api:dev

# Authenticate Docker
gcloud auth configure-docker

# Build and tag
docker build -t ${IMAGE} .

# Push to GCR
docker push ${IMAGE}

# Verify
gcloud container images list --repository=gcr.io/${PROJECT_ID}
```

## 11. Deploy to Cloud Run (GCP)

### Prerequisites

```bash
# Authenticate with GCP
gcloud auth login

# Set project
gcloud config set project my-gcp-project
```

### Deploy Development

```bash
# Deploy to Cloud Run
just phase3-deploy-cloudrun my-gcp-project

# Get service URL
SERVICE_URL=$(gcloud run services describe extraction-api \
  --region=us-central1 \
  --format='value(status.url)')

echo $SERVICE_URL

# Test cloud deployment
curl ${SERVICE_URL}/api/v1/health
```

## 12. Troubleshooting

### Server won't start

```bash
# Check Python version
python --version  # Must be 3.14+

# Check if port 8000 is in use
lsof -i :8000

# Kill process on port 8000 (if needed)
kill -9 <PID>

# Try different port
uv run uvicorn src.pipelines.api.extraction_api:app --reload --port 8001
```

### Tests failing

```bash
# Run with verbose output
uv run pytest tests/ -vv

# Run specific test file
uv run pytest tests/integration/test_extraction_pipeline_phase_e.py -v

# Show print statements during test
uv run pytest tests/ -s
```

### Linting errors

```bash
# Check which rules are violated
uv run ruff check .

# Auto-fix violations
uv run ruff check --fix .

# Check specific file
uv run ruff check src/pipelines/api/extraction_api.py
```

### Type checking errors

```bash
# Run type checker with verbose output
uv run basedpyright .

# Check specific file
uv run basedpyright src/pipelines/api/extraction_api.py
```

## Common Workflows

### Add New Dependency

```bash
# Add production dependency
uv add new-package

# Add development dependency
uv add --group dev pytest-new-plugin
```

### Run Specific Integration Test

```bash
# Run one test
uv run pytest tests/integration/test_extraction_pipeline_phase_e.py::TestExtractionPipelineEndToEnd::test_api_health_check -v
```

### Debug Extraction Issues

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run API server
uv run uvicorn src.pipelines.api.extraction_api:app --reload

# Extract document with verbose output
curl -v http://127.0.0.1:8000/api/v1/extract/document \
  -H "Content-Type: application/json" \
  -d '{"file_path": "test.pdf", "detect_entities": true}'
```

### Profile Performance

```bash
# Generate performance profile
uv run python -m cProfile -o stats.prof src/pipelines/api/extraction_api.py

# Analyze profile
uv run python -c "import pstats; p = pstats.Stats('stats.prof'); p.sort_stats('cumulative').print_stats(10)"
```

## What's Included

### Source Code
- Phase A: BigQuery ingestion (schema analysis, POLE classification)
- Phase B1: Document extraction (PDF/PPTX parsing)
- Phase B2: Entity deduplication (fuzzy matching)
- Phase B3: Orchestration (pipeline coordination)
- Phase C: REST API (FastAPI endpoints)
- Phase D: Cloud Run deployment (configuration management)

### Test Suite
- **252 unit tests** across all pipeline phases
- **22 integration tests** for end-to-end validation
- **100%** linting compliance
- **95%+** code coverage

### Documentation
- Architecture diagrams
- API reference with examples
- Deployment guides
- Quickstart tutorials

## Next Steps

1. **Explore API**: Use OpenAPI docs at `/docs` to test endpoints
2. **Run Tests**: Execute `just test` to verify everything works
3. **Deploy**: Follow EXTRACTION_PIPELINE_DEPLOYMENT.md for Cloud Run deployment
4. **Integrate**: Connect to Agent Memory Graph Semantic layer for entity persistence
5. **Monitor**: Set up Cloud Logging and monitoring for production

## Environment Variables

Optional configuration via environment:

```bash
# Logging
export LOG_LEVEL=INFO        # DEBUG, INFO, WARNING, ERROR
export LOG_FORMAT=json       # json or text

# API
export API_HOST=0.0.0.0
export API_PORT=8000

# GCP (for deployed instances)
export PROJECT_ID=my-project
export REGION=us-central1
```

## Additional Resources

- **Full Documentation**: See `docs/` directory
- **Architecture**: [EXTRACTION_PIPELINE_ARCHITECTURE.md](EXTRACTION_PIPELINE_ARCHITECTURE.md)
- **Deployment**: [EXTRACTION_PIPELINE_DEPLOYMENT.md](EXTRACTION_PIPELINE_DEPLOYMENT.md)
- **API Reference**: [EXTRACTION_PIPELINE_API_REFERENCE.md](EXTRACTION_PIPELINE_API_REFERENCE.md)
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md)

## Getting Help

1. Check OpenAPI docs: `http://127.0.0.1:8000/docs`
2. Review architecture: `docs/EXTRACTION_PIPELINE_ARCHITECTURE.md`
3. Check deployment guide: `docs/EXTRACTION_PIPELINE_DEPLOYMENT.md`
4. Run tests with verbose output: `uv run pytest tests/ -vv`
5. Check logs: `uv run pytest tests/ -s`

## Quick Command Reference

```bash
# Setup
git clone https://github.com/bmatonte-t/agent-memory-graph.git
cd agent-memory-graph
uv sync --all-groups

# Development
uv run uvicorn src.pipelines.api.extraction_api:app --reload

# Testing
just test
just test-coverage
just check-all

# Building
docker build -t extraction-api:dev .

# Deployment (after gcloud setup)
just phase3-deploy-cloudrun my-project
```

Happy extracting! 🚀
