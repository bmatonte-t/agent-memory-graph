# Configuration System — Technical Reference

This page covers the internals of the settings system for contributors who need to modify its behavior. For usage documentation, see [Configuration Management](../batteries/configuration.md).

## Architecture

The settings system lives in `src/project_base/settings/` and is composed of four modules:

```text
src/project_base/settings/
├── __init__.py   # Public API — exposes `settings`, `Environment`, and the env var prefix
├── _core.py      # PreconfiguredSettings base class, source wiring, runtime_environment()
├── config.py     # Settings class (user-facing)
├── enums.py      # Environment and LogLevel StrEnums
└── models.py     # Pydantic models for settings groups (e.g. Logging)
```

The separation between `_core.py` and `config.py` is intentional:

- **`_core.py`** contains infrastructure that rarely changes: the base class, source priority wiring, environment detection, and the env var prefix derivation. You shouldn't need to touch it.
- **`config.py`** is where developers add their settings fields. It's deliberately minimal so that adding a new setting group is a one-line change.

## Source Priority and Wiring

All source customization happens in `PreconfiguredSettings.settings_customise_sources()`. This method is called by `pydantic-settings` before the model is instantiated and returns an ordered tuple of sources; earlier entries take priority.

The resolved order is:

1. **`init_settings`** — values passed to `Settings(...)` directly (constructor kwargs).
2. **`EnvSettingsSource`** — environment variables with the derived prefix and `__` nested delimiter.
3. **`DotEnvSettingsSource`** — a `.env` file at `ROOT / ".env"`.
4. **`YamlConfigSettingsSource`** × 4 — YAML files in this order:
    - `config.{env}.local.yaml`
    - `config.{env}.yaml`
    - `config.local.yaml`
    - `config.yaml`

Missing files are silently ignored by `pydantic-settings` — no need to create every file.

### How the prefix is derived

```python
# src/project_base/constants.py
PACKAGE_NAME = Path(__file__).parent.name  # "project_base"

# src/project_base/settings/_core.py
ENVIRONMENT_VARIABLE_PREFIX = f"{PACKAGE_NAME.replace('-', '_').upper()}_"  # "PROJECT_BASE_"
```

This means renaming the `src/project_base/` directory automatically changes the env var prefix everywhere.

## Environment Detection

`runtime_environment()` in `_core.py` reads the `{ENVIRONMENT_VARIABLE_PREFIX}ENVIRONMENT` environment var (defaulting to `"dev"`) and returns an `Environment` enum value. It raises `ValueError` with a descriptive message if the value is invalid.

This function runs **before** `Settings` is instantiated. Its return value is passed as the `environment` constructor argument, which `settings_customise_sources()` then uses to determine which YAML files to load.

## Why Eager Loading (No Lazy Proxy)

The `settings` singleton is created at **import time** in `settings/__init__.py`.

This is intentional. Alternatives like lazy proxies were considered and rejected for several reasons:

### Fail-fast is better

Eager loading means configuration errors surface the moment the module is imported, typically at process startup. A lazy proxy would defer errors to the first attribute access, which could happen deep in a request handler or background task, making misconfiguration much harder to catch and debug.

### Pydantic is very fast

The entire settings load (reading up to 4 YAML files, scanning environment variables, parsing `.env`, and running Pydantic validation) takes **single-digit ms** with the default settings surface. Even with 1000 fields it stays under 100 ms. There's no meaningful startup cost to justify deferring it.

### Singleton pattern

The `settings` object is instantiated exactly once at module import time:

```python
# src/project_base/settings/__init__.py
settings = Settings(environment=runtime_environment())
```

This guarantees all code sees the same settings instance and values throughout the process lifetime.

### If you still want lazy loading

If you have an unusual case where you need it (e.g., a CLI tool where most subcommands don't need settings), you can use `lazy-object-proxy`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    settings: Settings
else:
    from lazy_object_proxy import Proxy

    settings = Proxy(get_settings)
```

This preserves full type-checker support (`settings` appears as `Settings` to them) while deferring the actual load to first access. But for nearly all applications, eager loading is the better default.

## Extra Keys Policy

`PreconfiguredSettings` is configured with `SettingsConfigDict(extra="ignore")`. This means:

- Unknown keys in YAML files are silently ignored.
- Unknown prefixed env vars are silently ignored.
- No `ValidationError` for keys that aren't modeled.

This was chosen for forward compatibility — you can add keys to YAML before adding the corresponding model fields, and shared config files can contain keys used by other tools.

## Adding Sources

To add a new configuration source (e.g., a remote config server, a TOML file, etc.), modify `settings_customise_sources()` in `_core.py`. The `pydantic-settings` library supports [custom sources](https://docs.pydantic.dev/latest/concepts/pydantic_settings/#customise-settings-sources). Implement the `PydanticBaseSettingsSource` protocol and insert it at the appropriate position in the returned tuple.

## `environment` as a Bootstrap Value

The `environment` field is special — it's needed *before* the settings object exists (to know which YAML files to load). This creates a chicken-and-egg problem solved by:

1. `runtime_environment()` reads the raw env var **outside** of pydantic-settings.
2. The result is passed as a constructor kwarg: `Settings(environment=environment)`.

If `environment` is not provided, a `TypeError` is raised with a clear message. This guards against accidental omission since the method runs before Pydantic's own validation.
