# For Existing Projects

If you want to improve the current configs of an existing project, these are the files and configurations you should consider adopting:

- [VSCode settings](https://github.com/tryolabs/repo-template/blob/main/.vscode/settings.json): Editor configuration and Python settings.
- [Dependabot config](https://github.com/tryolabs/repo-template/blob/main/.github/dependabot.yml): Dependency update automation.
- **Ruff configs:** See `[tool.ruff]` sections in `pyproject.toml`.
- [Style check GitHub Action](https://github.com/tryolabs/repo-template/blob/main/.github/workflows/style-checks.yaml): Formatting and linting checks.
- [Pytest coverage GitHub Action](https://github.com/tryolabs/repo-template/blob/main/.github/workflows/test-coverage.yaml): Test coverage validation.
- [Pre-commit hooks](https://github.com/tryolabs/repo-template/blob/main/.pre-commit-config.yaml): Git hooks for code quality, including ruff, large file checks, and secret detection.
- [MkDocs config](https://github.com/tryolabs/repo-template/blob/main/mkdocs.yml): Documentation site configuration.
- [Justfile](https://github.com/tryolabs/repo-template/blob/main/justfile): Task runner for common project commands.
