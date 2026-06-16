#!/usr/bin/env bash

# Exit if a command fails
set -e
source ./init_utils.sh

# Exit if project name isn't specified as an argument
if [ -z "$1" ]; then
    echo "Usage: $0 <project name>"
    exit 1
fi

ensure_executable_dependencies

OPERATING_SYSTEM=$(uname -s | tr '[:upper:]' '[:lower:]') # darwin or linux

if [[ "$OPERATING_SYSTEM" == "darwin" ]]; then
    SED_INPLACE=(-i '')
else
    SED_INPLACE=(-i)
fi

PACKAGE_NAME=$(echo "$1" | tr "-" "_")

collect_user_inputs
# shellcheck source=.init-modes/values/normal.env
# Pick a sample .env to allow shelcheck to find the schema
source ".init-modes/values/${INIT_MODE}.env"  # Load mode-specific configuration values

echo "Initializing project $1 with package $PACKAGE_NAME and Python version: $PYTHON_VERSION"

generate_template_base_files "$INIT_MODE" "$PYTHON_VERSION"

initialize_uv_project "$PACKAGE_NAME" "$PYTHON_VERSION" "$PROJECT_DESCRIPTION"

echo "Installing pre-commit hooks."
just setup-hooks

# Use the collected notebook configuration
if [[ $use_notebooks =~ ^[Yy]$ ]]; then
    echo "✅ Adding nbstripout hook to strip Jupyter Notebook output when committing."
    cat >>.pre-commit-config.yaml <<'EOF'
  - repo: https://github.com/kynan/nbstripout
    rev: 0.8.1
    hooks:
      - id: nbstripout
EOF
else
    echo "🗑️ Not using nbstripout hook."
fi

echo "Renaming src/project_base to src/$PACKAGE_NAME."
mv src/project_base "src/$PACKAGE_NAME"

echo "Reconfigure mkdocs for the new project"
reconfigure_mkdocs "$PROJECT_DESCRIPTION"

# If testing the template rename project imports in test script (for template development purposes)
# else remove the test script
if [ "${test:-false}" = true ]; then
    sed "${SED_INPLACE[@]}" "s/project_base/$PACKAGE_NAME/" "src/$PACKAGE_NAME/test.py"
else
    rm "src/$PACKAGE_NAME/test.py"
fi

# Update imports and references from project_base to package name
# List of files to update (relative to project root)
FILES_TO_UPDATE=(
    "tests/test_paths.py"
    "tests/test_settings.py"
    "tests/test_logging_configuration.py"
    "docs/batteries/configuration.md"
    "docs/batteries/logging.md"
    "docs/tutorials/logging_internals.md"
    "src/$PACKAGE_NAME/__init__.py"
    "src/$PACKAGE_NAME/settings/__init__.py"
    "src/$PACKAGE_NAME/settings/_core.py"
    "src/$PACKAGE_NAME/settings/config.py"
    "src/$PACKAGE_NAME/settings/models.py"
    "src/$PACKAGE_NAME/logging.py"
)

# Apply replacements to each file
PREFIX=$(echo "$PACKAGE_NAME" | tr '[:lower:]' '[:upper:]')_
for file in "${FILES_TO_UPDATE[@]}"; do
    if [ -f "$file" ]; then
        # Replace imports and references: project_base. -> $PACKAGE_NAME.
        sed "${SED_INPLACE[@]}" "s/project_base\./$PACKAGE_NAME./g" "$file"
        # Replace bare package name: project_base -> $PACKAGE_NAME (catches imports without dot and prose references)
        sed "${SED_INPLACE[@]}" "s/project_base/$PACKAGE_NAME/g" "$file"
        # Replace prefix: PROJECT_BASE_ -> MY_PROJECT_
        sed "${SED_INPLACE[@]}" "s/PROJECT_BASE_/$PREFIX/g" "$file"
        # Replace assertions: assert PACKAGE.name == "project_base" -> assert PACKAGE.name == "$PACKAGE_NAME"
        sed "${SED_INPLACE[@]}" "s/assert PACKAGE\.name == \"project_base\"/assert PACKAGE.name == \"$PACKAGE_NAME\"/g" "$file"
        # Replace assertions: assert PACKAGE_NAME == "project_base" -> assert PACKAGE_NAME == "$PACKAGE_NAME"
        sed "${SED_INPLACE[@]}" "s/assert PACKAGE_NAME == \"project_base\"/assert PACKAGE_NAME == \"$PACKAGE_NAME\"/g" "$file"
        # Replace docstring references: ``project_base`` -> ``$PACKAGE_NAME``
        sed "${SED_INPLACE[@]}" "s/\`\`project_base\`\`/\`\`$PACKAGE_NAME\`\`/g" "$file"
    fi
done

if [ -f ".vscode/launch.json" ]; then
    echo "Updating FastAPI App configuration in launch.json"
    # Replace 'project_base' with the actual package name in the FastAPI configuration.
    sed "${SED_INPLACE[@]}" "s/project_base\.apis\.service\.app:app/$PACKAGE_NAME\.apis\.service\.app:app/g" ".vscode/launch.json"
fi

echo "Ensuring test coverage configuration only considers our package $PACKAGE_NAME."
sed "${SED_INPLACE[@]}" "s/--cov=project_base/--cov=$PACKAGE_NAME/" ".vscode/settings.json"       # VS Code settings.

configure_justfile "$PACKAGE_NAME"

echo "Installing dependencies."
just install

echo "Creating a baseline for detect-secrets."
uv run detect-secrets scan >.secrets.baseline

add_repo_template_metadata
update_instructions_file "$1" "$PYTHON_VERSION"

echo "Removing unnecessary files and directories."
rm -rf CONTRIBUTING.md README.md init_utils.sh "$0" scripts/select_python.py

echo "Creating basic README file."
echo "# $PACKAGE_NAME" >README.md
echo "" >>README.md
echo "$PROJECT_DESCRIPTION" >>README.md


echo "Committing initial project state..."
git add .
SKIP=no-commit-to-branch git commit -m "Initial setup"

echo "Project $PACKAGE_NAME initialized with Python $PYTHON_VERSION and uv in mode $INIT_MODE. Changes are committed locally. Please review and push to your repository when ready."