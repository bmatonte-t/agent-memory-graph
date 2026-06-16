# Development Environment

## Package and Python Version Management

[`uv`](https://docs.astral.sh/uv/) is used to manage Python versions, dependencies, and virtual environments. It replaces the need for separate tools like `pyenv`, `pip`, and `pipx`.

### Setup

Use their [installer](https://docs.astral.sh/uv/getting-started/installation/) to install it in your system:

```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Why use a package manager instead of just `pip`?

Using a package manager offers clear benefits over relying on `pip` alone.

!!! quote "A little story"
    Once upon a time, an innocent @sebastian-correa wanted to update a piece of code in LATAM.

    This piece of code was a tiny CLI that behind the scenes did a simple `git push`, and he wanted it to do a `git push --no-verify`. The whole company depends on this piece of code, since it's part of every project's CI/CD pipeline, and is in charge of generating Semantic Versioning tags for code merges.

    He submitted a couple PRs with the inconspicuous `--no-verify` flag. Everything was dandy until the new version of that code got built and released into the wild. A weird CLI parsing error started to spread like the plague, and every CI/CD pipeline being executed exploded :boom:.

    @sebastian-correa reverted his changes, but with little faith that that would fix the issue, and it didn't.

    Upon further investigation, it turns out that that LATAM repo specified their dependencies on a `requirements.txt` without any sort of lock/pin:

    ```ini title="requirements.txt"
    typer ~= 0.12.1
    ```

    Between the time the repo was last built (9 months prior to this change) and the moment of the change, `click`, a transitive dependency of the repo (via `typer`) had introduced a breaking change. However, since our spec didn't impose any restrictions over `click` and the fact that we didn't have a commited `.lock` file, the new resolution that happened on this build installed the new, incompatible version of `click`.

    This caused the failure of hundreds of pipelines and a bit of generalized chaos in the incident reporting system.

    If we would've had a `.lock` file, the error wouldn't have happened. It would have only appeared in a controlled environment of trying to update dependencies for some reason, instead of being a surprise when doing some other task.

#### Flexible dependency specifications with reproducible builds

Managing dependencies is more than just listing packages. As a developer, you want to specify flexible version ranges (e.g., `~=1.2.3` for [Semantic Versioning](https://semver.org/)), so your project can receive bug fixes and new features without breaking compatibility. At the same time, you need a way to lock down exact versions for reproducible builds, ensuring everyone installs the same dependencies every time.

Package managers solve this by letting you declare broad version requirements, then generating a lock file with precise versions and hashes. You install from the lock file for consistency, while still keeping your dependency specs flexible.

!!! tip
    Always commit your `.lock` file to source control.

Therefore `.lock` files are paramount to:

- **Reproducible builds**: Ensure all team members use identical dependency versions in all environments.
- **Production reliability**: Deployments use the same tested dependency versions.
- **Security**: Track specific versions for vulnerability management.
- **Debugging**: Easier to identify if issues are caused by dependency changes

#### Automatic dependency resolution

Finds compatible versions for all packages, ensuring all dependencies and subdependencies are compatible.

#### Virtual environment management

Handles creation and activation of isolated environments.

### Why uv?

`uv` is an extremely fast Python package and project manager written in Rust. It provides a unified tool that replaces `pyenv`, `pip`, `pipx`, and `poetry` with a single, fast binary. It handles Python version management, dependency resolution, virtual environments, and tool execution.

### Common Commands

```bash
# Install dependencies
uv sync

# Add a new dependency
uv add requests

# Add a development dependency
uv add --group dev pytest

# Add a scraping dependency
uv add --group scraper scrapy

# Run commands in the virtual environment
uv run python script.py
```

## VS Code Integration

The template includes pre-configured VS Code settings for:

- **Python interpreter:** Automatically uses the local virtual environment.
- **Linting and formatting:** Uses `ruff`.
- **Testing**: Pytest integration.
- **IntelliSense**: Optimized for Python development.

It also includes recommended extensions and some good default debugger configurations.
