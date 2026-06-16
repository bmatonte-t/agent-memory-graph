# Project Structure

## Directory Layout

The template creates a well-organized directory structure to help you get started quickly. Here are the most relevant parts:

```text
your-project/
├── src/
│   └── package_name/        # Main source code directory ("src layout")
│       ├── __init__.py
│       └── ...              # Your application code goes here
├── tests/                   # Test files
├── docs/                    # Documentation
├── notebooks/               # VSCode Interactive or Jupyter Notebooks
├── scripts/                 # One-off scripts, either Python or shell
├── .vscode/                 # VS Code settings and configurations
├── .github/                 # GitHub Workflows and templates
├── .personal_workspace/     # Non source controlled directory for any files you want
├── pyproject.toml           # Project configuration and dependencies
├── uv.lock                  # Locked dependency versions
├── .pre-commit-config.yaml  # Pre-commit hooks configuration
├── .secrets.baseline        # Baseline for secret detection
├── justfile                 # Common commands
└── README.md                # Project documentation
```

## What Goes Where

- **Source Code**: Place your main application code under `src/<package_name>/`. The template follows the [src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/), which forces you to import your package via its installed name instead of accidentally importing it from the working directory.

    !!! note
        Since we install your package into your `.venv`, you should always use absolute imports to avoid weird import errors.

- **Tests:** All test files go in the `tests/` directory.
- **Documentation:** Use the `docs/` directory for project documentation.
- **Configuration:** If possible, tool settings should be placed in `pyproject.toml`. Only deviate from this standard if the tools doesn't allow this.
- **Dependencies:** You should add dependencies via `uv add` (or `uv add --group`), which ensures the semantic dependency is added to `pyproject.toml` and the exact resolution to `uv.lock`.

    !!! tip
        Use dependency groups to modularize dependencies for deployments. Note that all dependencies will have to be resolvable at once, even if placed in separate groups.

- **VS Code Settings:** Shared editor settings in `.vscode/`.
- **One-off scripts:** Scripts that don't belong in your package but that you still want to source control. These may be helpers for developers, or documentation of usual processes like cleaning a database.
- **Notebooks:** Inside the `notebooks/` directory, which has less stringent linting rules to allow for a more flexible, scrappy environment of rapid prototyping.

## `.personal_workspace` Feature

The template includes a `.personal_workspace/` directory that is git-ignored. This is perfect for:

- Personal notes and scratchpads
- Temporary files and experiments
- Development utilities specific to your workflow

This allows team members to keep personal files without cluttering the shared repository.
