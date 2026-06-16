# Code Quality & Safety

Code quality is a cornerstone of successful software projects. Therefore, the Repo Template provides some pre configured tooling to uphold best practices and good code quality.

## Linting and Formatting

[ruff](https://docs.astral.sh/ruff/) is used for both linting and formatting, providing fast and comprehensive code quality checks.

### Features

- **Lightning fast:** Written in Rust and designed for lightning fast performance.
- **Comprehensive:** Replaces multiple tools (flake8, black, isort, etc.).
- **Configurable:** Extensive rule configuration in `pyproject.toml`.
- **Well supported:** Astral has a proven track record when it comes to bug squashing and listening to community feedback.

### How to use `ruff`

In VSCode, install the recommended [Ruff extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff). The included `.vscode/settings.json` already enables linting and formatting on save with `ruff`.

If you use other IDEs, you may consult `ruff's guide`.

!!! tip
    Some integrations (like VSCode's) allow the IDE to use a bundled version of `ruff` instead of that from the environment (i.e., your local venv).

    We recommend you favor using your local venv's to avoid weird issues with difering versions of `ruff`.

### Provided configuration

The template includes sensible defaults for:

- Code style enforcement.
- Import sorting.
- Common Python anti-patterns.
- Complexity checking.

If you find these too restrictive, you may change them directly in your `pyproject.toml`.

## Type checking

Static type checking helps catch bugs early and improves code maintainability. This template uses [Pyright](https://microsoft.github.io/pyright/#/) for static type analysis, integrated via the VSCode Python extension and the `basedpyright` CLI in CI/CD.

For type checking to be effective, your codebase has to be well typed. See the [typing tutorial](../tutorials/typing.md) for more.

### How to use type checking

In VSCode, type checking is enabled by default through the Python extension. You’ll see type errors and warnings directly in the editor, and in the Problems panel.

The template runs type checks automatically on every pull request using the `basedpyright` CLI in the [Test Coverage action](https://github.com/tryolabs/repo-template/blob/main/.github/workflows/test-coverage.yaml). This ensures that all code meets the required type safety standards before merging.

### Configuration

The type checking mode and rules are defined in the [tool.pyright] section of `pyproject.toml`.
You can adjust the strictness or ignore specific warnings as needed.

You may check Pyright's [configuration documentation](https://microsoft.github.io/pyright/#/configuration) for an extensive list of settings, and to understand what each diagnostics rule does. In particular, Pyright supports a couple diagnostic modes, so you can check which rules are enabled for each mode in this [table](https://microsoft.github.io/pyright/#/configuration?id=diagnostic-settings-defaults).

## Secret Detection

[detect-secrets](https://github.com/Yelp/detect-secrets) helps prevent accidental commits of sensitive information.

### How It Works

- Scans files for potential secrets (API keys, passwords, tokens).
- Uses heuristics and entropy analysis.
- Maintains a baseline of known "safe" strings.

### How to use `detect-secrets`

Currently runs as a `pre-commit` hook, so check the [setup section](./git_hooks.md#setup) to see how to install them.

### Managing False Positives

When legitimate code triggers false positives, add the new triggering secrets to the baseline:

```shell
# Update the baseline
uv run detect-secrets scan --baseline .secrets.baseline

# Commit the updated baseline
git add .secrets.baseline
git commit -m "Update secrets baseline"
```

!!! note
    Don't forget to commit the new baseline. Otherwise, the pre-commit hook will continue failing.

## Code Complexity Monitoring

The template includes tools to monitor code complexity and maintainability that run automatically on each PR. See [this section](./scripts.md#code-complexity-metrics) for more details.
