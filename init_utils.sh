#!/bin/bash

link() {
    local url="$1"
    local text="$2"
    # %b interprets escapes, %s treats input as raw string
    printf "\e]8;;%s\e\\%s\e]8;;\e\\" "$url" "$text"
}

# Function to collect all user inputs at the beginning
collect_user_inputs() {
    echo "🚀 Project Configuration"
    echo "======================="

    # Project description
    read -r -p "Enter a brief description for your project (''): " PROJECT_DESCRIPTION

    if ! PYTHON_VERSION=$(uv run scripts/select_python.py); then
        echo "❌ Error: Failed to determine Python version (select_python.py exited with error)."
        exit 1
    fi
    if [[ -z "$PYTHON_VERSION" ]]; then
        echo "❌ Error: Python version selector returned an empty value."
        exit 1
    fi
    export PYTHON_VERSION

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Template Initialization Mode"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Select the quality vs speed tradeoff for your project:"
    echo ""
    echo "  1) poc        - Fast prototyping with guardrails"
    echo "  2) normal     - Balanced quality and velocity (recommended)"
    echo "  3) long-term  - Production-grade quality"
    echo ""
    echo "You may read more about each mode at $(link "https://documentation.tryolabs.com/getting_started/initialization_modes/" "the documentation")."
    read -r -p "Mode [2]: " mode_choice
    mode_choice=${mode_choice:-2}

    case $mode_choice in
      1) INIT_MODE="poc" ;;
      2) INIT_MODE="normal" ;;
      3) INIT_MODE="long-term" ;;
      *)
        echo "❌ Invalid mode selection"
        exit 1
        ;;
    esac

    # Jupyter notebooks configuration
    read -r -p "Do you want pre-commit hooks to strip output from Jupyter Notebooks (*ipynb)? If you don't plan to use .ipynb, answer N (y/N): " use_notebooks
    use_notebooks=${use_notebooks:-N}

    # Repository URL configuration
    local PWD_NAME
    PWD_NAME=$(basename "$PWD")
    local DEFAULT_REPO_URL="https://github.com/tryolabs/$PWD_NAME"
    read -r -p "Do you have a custom repo URL? (leave blank for default: $DEFAULT_REPO_URL): " REPO_URL
    if [ -z "$REPO_URL" ]; then
        REPO_URL="$DEFAULT_REPO_URL"
    fi

    echo
    echo "📋 Configuration Summary:"
    echo "  Python version: $PYTHON_VERSION"
    echo "  Mode: $INIT_MODE"
    echo "  Description: ${PROJECT_DESCRIPTION:-'(empty)'}"
    echo "  Jupyter notebooks: $use_notebooks"
    echo "  Repository URL: $REPO_URL"
    echo
}

ensure_executable_dependencies() {
    local missing_deps=()

    if ! command -v sed &>/dev/null; then
        missing_deps+=("sed")
    fi

    if ! command -v uv &>/dev/null; then
        missing_deps+=("uv")
    fi

    if ! command -v just &>/dev/null; then
        missing_deps+=("just")
    fi

    if [ ${#missing_deps[@]} -eq 0 ]; then
        return 0
    fi

    echo "❌ Error: The following required dependencies are missing: ${missing_deps[*]}"
    echo "Please install them and re-run the script."
    echo ""

    for dep in "${missing_deps[@]}"; do
        case "$dep" in
            uv)
                echo "  uv:   curl -LsSf https://astral.sh/uv/install.sh | sh"
                ;;
            just)
                echo "  just: curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin"
                echo "        (ensure ~/.local/bin is in your PATH)"
                ;;
            *)
                echo "  $dep: install via your system package manager (e.g. brew, apt, dnf)"
                ;;
        esac
    done

    exit 1
}


initialize_uv_project() {
  echo "Configuring project metadata in pyproject.toml."
  PACKAGE_NAME="$1" PYTHON_VERSION="$2" PROJECT_DESCRIPTION="$3"\
  uv run --with tomlkit python3 - <<'PYEOF'
import os, pathlib
import tomlkit

f = pathlib.Path('pyproject.toml')
doc = tomlkit.loads(f.read_text())
doc['project']['name'] = os.environ['PACKAGE_NAME']
doc['project']['description'] = os.environ.get('PROJECT_DESCRIPTION', '')
doc['project']['requires-python'] = f">={os.environ['PYTHON_VERSION']}"
doc['tool']['hatch']['build']['targets']['wheel']['packages'] = [f"src/{os.environ['PACKAGE_NAME']}"]
f.write_text(tomlkit.dumps(doc))
PYEOF
}

generate_template_base_files() {
  local init_mode=$1
  local python_version=$2

  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  Generating configuration files for $init_mode mode"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  # Configure pyproject.toml
  echo "  → Updating Ruff target-version in pyproject.toml to match Python version $python_version."
  local py_target_version
  py_target_version="py$(echo "$python_version" | cut -d'.' -f1,2 | tr -d '.')"
  sed "${SED_INPLACE[@]}" "s/target-version = \"py[0-9]*\"/target-version = \"$py_target_version\"/" "pyproject.toml"

  echo "  → Merging pyproject.toml fragments for $init_mode mode."
  uv run scripts/toml_replacer.py \
    --target "pyproject.toml" \
    --source ".init-modes/fragments/pyproject/${init_mode}.toml"

  # No way to disable other than setting `on: workflow_dispatch:` which is tricky to do.
  if [[ "$init_mode" == "poc" ]]; then
    mv ".github/workflows/check-pr-style.yaml" ".github/workflows/check-pr-style.yaml.disabled"
  fi

  echo ""
  echo "  ✔ Configuration files generated for $init_mode mode."
  echo ""
}

configure_justfile() {
  local package_name=$1

  echo "Configuring justfile."

  sed "${SED_INPLACE[@]}" "s/project_base/$package_name/g" justfile
  sed "${SED_INPLACE[@]}" -E "s/--cov-fail-under=[0-9]+/--cov-fail-under=$TEST_COVERAGE_THRESHOLD/" justfile
  sed "${SED_INPLACE[@]}" -E "s/--fail-under [0-9]+/--fail-under $DOCSTRING_COVERAGE_THRESHOLD/" justfile
}

reconfigure_mkdocs() {
  local PROJECT_DESCRIPTION="${1:-}"  # Accept description as first parameter, default to empty
  local PWD_NAME
  PWD_NAME=$(basename "$PWD")
  local SITE_NAME
  SITE_NAME=${PWD_NAME//-/ }
  SITE_NAME=${SITE_NAME//_/ }

  # Use the REPO_URL that was collected earlier
  local REPO_NAME
  REPO_NAME=$(uv run python -c "import sys; from urllib.parse import urlparse; print(urlparse(sys.argv[1]).path.lstrip('/'))" "$REPO_URL")

  # Update mkdocs.yml
  # SED_INPLACE inherited from init.sh.
  local MKDOCS_FILE="mkdocs.yml"

  # Set site_name, site_url, repo_url, repo_name, and update logo/favicon.
  sed "${SED_INPLACE[@]}" \
    -e "s/^site_name: .*/site_name: $SITE_NAME/" \
    -e "s|^site_url: .*|site_url: https://documentation.tryolabs.com/$PWD_NAME|" \
    -e "s|^repo_url: .*|repo_url: $REPO_URL|" \
    -e "s|^repo_name: .*|repo_name: $REPO_NAME|" \
    -e "s|logo: assets/logo.svg|logo: assets/tryolabs-isotipo-circle-green.svg|" \
    -e "s|favicon: assets/logo.svg|favicon: assets/tryolabs-isotipo-circle-green.svg|" \
    "$MKDOCS_FILE"

  # Handle site_description separately
  if [ -n "$PROJECT_DESCRIPTION" ]; then
    sed "${SED_INPLACE[@]}" -e "s/^site_description: .*/site_description: $PROJECT_DESCRIPTION/" "$MKDOCS_FILE"
  else
    sed "${SED_INPLACE[@]}" -e '/^site_description:/d' "$MKDOCS_FILE"
  fi

  # Remove specific non-project assets.
  rm -f "docs/assets/logo.svg"
  rm -f "docs/assets/issue_priority.png"

  # Remove everything in docs except assets/javascripts and assets/stylesheets and tryolabs-isotipo-circle-green.svg
  find docs/ -mindepth 1 -maxdepth 1 \! -name assets -exec rm -rf {} +
  find docs/assets/ -mindepth 1 -maxdepth 1 \! -name javascripts \! -name stylesheets \! -name tryolabs-isotipo-circle-green.svg -exec rm -rf {} +

  # Create docs/index.md with project information
  cat > docs/index.md << EOF
# $SITE_NAME

$PROJECT_DESCRIPTION
EOF

  # Replace the entire nav: block with a minimal nav (index + API reference only)
  awk '/^nav:/{skip=1; next} skip && /^[^ ]/{skip=0} !skip' "$MKDOCS_FILE" > "${MKDOCS_FILE}.tmp"
  printf '\nnav:\n  - Home: index.md\n  - API Reference: api_reference/\n' >> "${MKDOCS_FILE}.tmp"
  mv "${MKDOCS_FILE}.tmp" "$MKDOCS_FILE"
}

add_repo_template_metadata() {
  echo "Adding repo-template metadata to pyproject.toml."

  # Get the timestamp of when GitHub created the repo (initial commit)
  INSTANTIATED_AT=$(git log --format=%aI -1 2>/dev/null || echo "unknown")

  # date -u always gives UTC time
  INITIALIZED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  cat <<EOF | uv run scripts/toml_replacer.py --target "pyproject.toml"
[tool.repo-template]
mode = "${INIT_MODE}"
instantiated_at = "${INSTANTIATED_AT}"
initialized_at = "${INITIALIZED_AT}"
EOF
}

update_instructions_file() {
  local project_name=$1
  local python_version=$2

  echo "Updating Copilot instructions with metadata entered by user."

  # Replace project name and description
  sed "${SED_INPLACE[@]}" "s/<PROJECT_NAME>/$project_name/g" ".github/copilot-instructions.md"
  sed "${SED_INPLACE[@]}" "s/<PROJECT_DESCRIPTION>/$PROJECT_DESCRIPTION/g" ".github/copilot-instructions.md"

  # Replace Python version in instructions files
  sed "${SED_INPLACE[@]}" "s/<PYTHON_VERSION>/$python_version/g" ".github/instructions/python.instructions.md"
}
