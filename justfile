SRC := 'src'
SRC_DIR := 'src'

# Show available commands
default:
  just --list

# Install project dependencies
install:
  uv sync --all-groups

# Remove virtual environment and reinstall dependencies
reinstall:
  rm -rf .venv
  uv sync --all-groups

# Setup pre-commit hooks for all hook types found in .pre-commit-config.yaml
setup-hooks:
  #!/usr/bin/env bash
  set -euo pipefail
  # Extract unique hook types from .pre-commit-config.yaml and install each
  hook_types=$(uv run python "{{justfile_directory()}}/scripts/extract_necessary_pre_commit_types.py")

  if [ -z "$hook_types" ]; then
    echo "No stages defined in hooks, using default pre-commit installation..."
    uv run pre-commit install
  else
    echo "Found hook types: $hook_types"
    for hook_type in $hook_types; do
      echo "Installing $hook_type hooks..."
      uv run pre-commit install --hook-type "$hook_type" || true
    done
  fi

# Run tests
test:
  uv run pytest

# Run tests with coverage report
test-coverage:
  uv run pytest --cov={{SRC}} --cov-fail-under=0

# Run linter to check for issues
lint:
  uv run ruff check

# Run linter and automatically fix issues
lint-fix:
  uv run ruff check --fix

# Run type checker
check-types:
  uv run basedpyright {{SRC_DIR}}/

# Check code formatting without making changes
check-format:
  uv run ruff format --check

# Format code automatically
format:
  uv run ruff format

# Check docstring coverage
docstring-coverage:
  uv run docstr-coverage --fail-under 20 --verbose=2 --skip-file-doc --skip-init {{SRC_DIR}}

# Clean build artifacts and cache files
clean:
  find . -type f -name "*.pyc" -delete
  find . -type d -name "__pycache__" -exec rm -rf {} +
  find . -type d -name "*.egg-info" -exec rm -rf {} +
  find . -type f -name ".coverage" -delete
  find . -type d -name "htmlcov" -exec rm -rf {} +
  find . -type d -name ".pytest_cache" -exec rm -rf {} +
  find . -type d -name ".mypy_cache" -exec rm -rf {} +
  find . -type d -name "dist" -exec rm -rf {} +
  find . -type d -name "build" -exec rm -rf {} +

# Update all dependencies to latest versions
dependency-update:
  uv lock --upgrade

# Show dependency tree
dependency-tree:
  uv tree

# Show outdated dependencies
dependency-outdated:
  uv pip list --outdated

# Run all quality checks
check-all: lint check-types check-format test-coverage docstring-coverage

# Serve docs locally with live reload
serve-docs:
  uv run mkdocs serve --watch-theme

# Build docs and output results to site/
build-docs:
  uv run mkdocs build

# Build documentation server Docker image
build-docs-server:
  docker build -t documentation-server --platform linux/amd64 --file infrastructure/documentation/Dockerfile .

# List all subsites published at documentation.tryolabs.com
docs-list-sites:
  gcloud storage ls "gs://tryolabs-documentation" --project=tryo-documentation | awk -F/ '{print $4}'

# Publish the site to documentation.tryolabs.com
docs-publish-site:
  gcloud storage rsync -r site "gs://tryolabs-documentation/$(basename "$(pwd)")" --project=tryo-documentation

# Locally build documentation and publish the site to documentation.tryolabs.com
docs-build-and-publish-site: build-docs docs-publish-site

# Run the main application
run:
  uv run python {{SRC_DIR}}/src.py

# Render Cloud Run manifest for Phase 3 deployment
phase3-render-cloudrun project_id image_tag='latest' region='us-central1' artifact_repo='agent-memory-graph' image_name='phase3' service_name='agent-memory-graph-phase3' output='infrastructure/phase3/cloudrun-service.rendered.yaml':
  uv run python scripts/render_phase3_cloudrun_manifest.py --project-id "{{project_id}}" --image-tag "{{image_tag}}" --region "{{region}}" --artifact-repository "{{artifact_repo}}" --image-name "{{image_name}}" --service-name "{{service_name}}" --output "{{output}}"

# Build and push Phase 3 container image with Cloud Build
phase3-build-image project_id image_tag='latest' region='us-central1' artifact_repo='agent-memory-graph' image_name='phase3':
  gcloud builds submit --project "{{project_id}}" --tag "{{region}}-docker.pkg.dev/{{project_id}}/{{artifact_repo}}/{{image_name}}:{{image_tag}}" .

# Deploy Phase 3 service to Cloud Run using rendered manifest
phase3-deploy-cloudrun project_id image_tag='latest' region='us-central1' artifact_repo='agent-memory-graph' image_name='phase3' service_name='agent-memory-graph-phase3':
  just phase3-render-cloudrun "{{project_id}}" "{{image_tag}}" "{{region}}" "{{artifact_repo}}" "{{image_name}}" "{{service_name}}"
  gcloud run services replace infrastructure/phase3/cloudrun-service.rendered.yaml --project "{{project_id}}" --region "{{region}}"
