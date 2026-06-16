# Configuration Management

The template ships with a ready-to-use configuration system built on [`pydantic-settings`](https://docs.pydantic.dev/latest/concepts/pydantic_settings/). Import one object and you have validated, type-safe access to every setting your application needs.

```python
from project_base.settings import settings

settings.environment          # Environment.DEV
settings.logging.log_level    # LogLevel.DEBUG
```

No boilerplate, full IDE autocompletion, and if anything is wrong you'll know the moment your process starts.

## What You Get

- **Type-safe settings:** with full Pydantic validation and IDE autocompletion.
- **Layered configuration:** YAML files, environment variables, `.env` files, and constructor overrides, with clear precedence rules.
- **Per-environment overrides:** different config for `dev`, `prod`, or any custom environment.
- **Local overrides:** `*.local.yaml` files (git-ignored) for machine-specific tweaks.
- **Fail-fast behavior:** misconfiguration crashes your app on startup, not at 3 AM in production.
- **Near-zero overhead:** the entire settings load takes single-digit milliseconds.

## Quick Start

Settings are already wired up. Import and use:

```python
from project_base.settings import settings

if settings.environment == Environment.PROD:
    enable_monitoring()

configure_logger(level=settings.logging.log_level)
```

## How to add settings

To add your own settings, you only need three steps:

### Define a model

```python
# src/project_base/settings/models.py  (or a new file like database.py)
from pydantic import BaseModel

class Database(BaseModel):
    host: str
    port: int = 5432
    name: str
```

### Register it

```python
# src/project_base/settings/config.py
from project_base.settings.models import Database

class Settings(PreconfiguredSettings):
    logging: Logging
    database: Database  # ← one line
```

### Populate the values

Add the values to your YAML files and you're done:

```yaml
# config.yaml
database:
  host: localhost
  port: 5432
  name: myapp
```

```python
settings.database.host  # "localhost"; fully typed, validated
```

## Where Settings Are Read From

Settings load from multiple sources. **Higher priority wins** when the same key appears in more than one place:

| Priority | Source                             | Typical use                     |
| -------- | ---------------------------------- | ------------------------------- |
| 1        | `Settings()` constructor arguments | Unit tests                      |
| 2        | Environment variables              | CI/CD, production               |
| 3        | `.env` file at project root        | Local secrets                   |
| 4        | `config.{env}.local.yaml`          | Machine-specific overrides      |
| 5        | `config.{env}.yaml`                | Per-environment defaults        |
| 6        | `config.local.yaml`                | Machine-specific base overrides |
| 7        | `config.yaml`                      | Shared defaults                 |
| 8        | Field defaults in Pydantic models  | Last resort                     |

This hierarchy lets you:

- Commit shared defaults in `config.yaml`.
- Override per environment in `config.dev.yaml` or `config.prod.yaml`.
- Keep machine-specific tweaks in `*.local.yaml` files (git-ignored).
- Store secrets in `.env` (git-ignored).
- Override anything via environment variables in CI/CD.

### File layout

All configuration files live in the **project root**:

```text
repo-root/
├── config.yaml              # Base defaults (committed)
├── config.dev.yaml          # Dev overrides (committed)
├── config.dev.local.yaml    # Dev local overrides (git-ignored)
├── config.prod.yaml         # Prod overrides (committed)
├── config.local.yaml        # Base local overrides (git-ignored)
└── .env                     # Local secrets (git-ignored)
```

## Environments

The active environment is read from the `{ENVIRONMENT_VARIABLE_PREFIX}ENVIRONMENT` environment variable.

!!! note
    The environment variable prefix (`PROJECT_BASE_`) is derived automatically from the package directory name. If you rename `src/project_base/` to `src/myapp/`, the prefix becomes `MYAPP_`.

    You may check `.../settings/_core.py` for details.

This determines which `config.{env}.yaml` and `config.{env}.local.yaml` files are loaded.

You can define as many environments as you need:

```python
# src/project_base/settings/enums.py
class Environment(StrEnum):
    LOCAL = "local"
    DEV = "dev"
    PROD = "prod"
    # STAGING = "staging"  ← add your own
```

!!! info
    You may configure the environment for a given command by passing the environment variable inline:

    ```shell
    PROJECT_BASE_ENVIRONMENT=dev uv run python src/project_base/job.py
    ```

## Environment Variables

Environment variables must use the **prefix** and `__` (double underscore) as a **nested delimiter**. The rule is straightforward: replace each `.` in the Python attribute path with `__` and prepend the prefix.

```bash
# Top-level field
export PROJECT_BASE_ENVIRONMENT=prod

# Nested field  →  settings.logging.log_level
export PROJECT_BASE_LOGGING__LOG_LEVEL=ERROR
```

### Nested structures

For deeply nested models, chain `__` delimiters to match the nesting:

```python
class Redis(BaseModel):
    host: str
    port: int

class Cache(BaseModel):
    redis: Redis
    ttl: int

class Settings(PreconfiguredSettings):
    cache: Cache
```

```bash
# settings.cache.redis.host
export PROJECT_BASE_CACHE__REDIS__HOST=redis.example.com

# settings.cache.redis.port
export PROJECT_BASE_CACHE__REDIS__PORT=6379

# settings.cache.ttl
export PROJECT_BASE_CACHE__TTL=3600
```

## Handling Secrets

!!! danger "Never commit secrets"
    Passwords, API keys, and tokens must **never** appear in committed files like `config.yaml` or `config.dev.yaml`.

### Recommended approach

#### Local access

For local access, store your secrets in your `.gitignore`d `.env` or `*.local.yaml` files.

For example, add them to the `.env` file at the project root:

```bash
# .env
PROJECT_BASE_DATABASE__PASSWORD=my_local_password
PROJECT_BASE_API__SECRET_KEY=dev-only-key
```

or in a `*.local.yaml` file if you want to have "visual structure".

#### Production/cloud access

Inject secrets through your platform's secret management (GitHub Actions secrets, Kubernetes secrets, cloud provider vaults) as environment variables.

As stated in the [environment variables](#environment-variables) section, these will indistinctly end up as members of the `settings` object, so code can access them regardless of how they're loaded.

### Always use `SecretStr` (defense in depth)

Use `SecretStr` instead of `str` to prevent secrets from leaking into logs, tracebacks, and `repr()` output:

```python
from pydantic import BaseModel, SecretStr

class Database(BaseModel):
    host: str
    port: int = 5432
    password: SecretStr
```

```python
settings.database.password                    # SecretStr('**********')
settings.database.password.get_secret_value() # "actual_password"
```

!!! warning
    `SecretStr` does **not** encrypt anything; it only masks the value in string representations. The actual secret is still in memory.

## Fail-Fast Behavior

The settings object is created **eagerly** when you first import it. If any value is missing, has the wrong type, or fails validation, your application crashes immediately with a clear Pydantic `ValidationError`:

```python
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
logging.log_level
  Input should be 'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG' or 'NOTSET'
  [type=enum, input_value='INVALID', ...]
```

This is intentional. Finding out about a bad config at startup is infinitely better than discovering it at runtime in production.

!!! tip
    The fail-fast design means you can trust that if your app started, all settings are valid. No need for defensive `if settings.x is not None` checks throughout your code.

## Performance

Settings are loaded once at module import time. The load itself is very fast! Here are numbers from a benchmark provided in PR [#234](https://github.com/tryolabs/repo-template/pull/234):

| What                                                      | Time                           |
| --------------------------------------------------------- | ------------------------------ |
| Settings load (YAML I/O + env scan + Pydantic validation) | **~3 ms**                      |
| With 100 fields                                           | ~4 ms                          |
| With 1 000 fields                                         | ~8 ms                          |
| Every subsequent access                                   | **instant** (in-memory object) |

Pydantic validation scales sub-linearly: 200× more fields only adds ~6× more time. In practice, you'll never notice it.

## Testing

Settings in tests work the same way as in production code: create instances of `Settings` directly with the values you need.

### Basic testing approach

For most tests, create a fresh `Settings` instance with explicit values:

```python
from project_base.settings.config import Settings
from project_base.settings.enums import Environment, LogLevel
from project_base.settings.models import Logging

def test_something():
    settings = Settings(
        environment=Environment.DEV,
        logging=Logging(log_level=LogLevel.INFO, third_party_log_level=LogLevel.WARNING),
    )
    assert settings.logging.log_level == LogLevel.INFO
    assert settings.environment == Environment.DEV
```

### Creating reusable fixtures

If multiple tests need the same settings configuration, create fixtures:

```python
# conftest.py
import pytest
from project_base.settings.config import Settings
from project_base.settings.enums import Environment, LogLevel
from project_base.settings.models import Logging

@pytest.fixture
def dev_settings() -> Settings:
    """Provide settings configured for development environment."""
    return Settings(
        environment=Environment.DEV,
        logging=Logging(log_level=LogLevel.DEBUG, third_party_log_level=LogLevel.DEBUG),
    )

@pytest.fixture
def prod_settings() -> Settings:
    """Provide settings configured for production environment."""
    return Settings(
        environment=Environment.PROD,
        logging=Logging(log_level=LogLevel.WARNING, third_party_log_level=LogLevel.ERROR),
    )

# In tests
def test_dev_behavior(dev_settings):
    assert dev_settings.logging.log_level == LogLevel.DEBUG

def test_prod_behavior(prod_settings):
    assert prod_settings.logging.log_level == LogLevel.WARNING
```

### Testing with environment variables

To test environment variable overrides, use `monkeypatch` and create a new instance:

```python
def test_env_override(monkeypatch):
    monkeypatch.setenv("PROJECT_BASE_LOGGING__LOG_LEVEL", "ERROR")
    monkeypatch.setenv("PROJECT_BASE_ENVIRONMENT", "dev")

    # Create a new instance - it will read the monkeypatched env vars
    from project_base.settings._core import runtime_environment
    from project_base.settings.config import Settings

    settings = Settings(environment=runtime_environment())  # type: ignore[call-arg]
    assert settings.logging.log_level == LogLevel.ERROR
```

### When to use the production settings instance

If you need to test against the actual production settings loaded from your YAML files, you can import the module-level instance:

```python
from project_base.settings import settings

def test_production_config():
    # This uses the real settings loaded from config.yaml
    assert settings.environment in [Environment.DEV, Environment.PROD]
```

!!! warning
    The module-level `settings` instance is created once when first imported. If you modify it in one test, subsequent tests may see those modifications. For test isolation, prefer creating fresh `Settings` instances as shown above.

## Extra Keys

The settings class is configured with `extra="ignore"`, so unknown keys in YAML or environment variables are silently skipped. This makes it safe to have keys in your YAML that are used by other tools or are not yet modeled.

## FAQ

??? question "Where should I put my config files?"
    In the **project root**, next to `pyproject.toml`. The system resolves paths from the `ROOT` constant in `src/project_base/paths.py`.

??? question "Can I add a new environment like `staging`?"
    Yes. Add it to the `Environment` enum in `src/project_base/settings/enums.py`, create the corresponding `config.staging.yaml`, and set `PROJECT_BASE_ENVIRONMENT=staging`.

??? question "How do I add a simple top-level setting (not nested)?"
    Add a field directly to the `Settings` class:
    ```python
    class Settings(PreconfiguredSettings):
        logging: Logging
        debug_mode: bool = False  # ← top-level field with a default
    ```
    Then set it via YAML (`debug_mode: true`) or env var (`PROJECT_BASE_DEBUG_MODE=true`).

??? question "Why are my environment variables not working?"
    Check three things:

    1. The prefix is correct (e.g., `PROJECT_BASE_`).
    2. You're using `__` for nested keys (e.g., `PROJECT_BASE_LOGGING__LOG_LEVEL`).
    3. Variable names are **uppercase**.

??? question "Can I use this in notebooks?"
    Yes. `from project_base.settings import settings` works in notebooks just like in regular Python code.
