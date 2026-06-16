# Initialization Modes Development Guide

This guide is for template developers who want to understand or modify the initialization mode system.

## Overview

The template supports many initialization modes. The system uses a merge-based approach where mode-specific configurations are merged into a base configuration file.

For user-facing documentation about choosing a mode, see the main [Initialization Modes](../getting_started/initialization_modes.md) page.

## Directory Structure

The `.init-modes/` directory contains all mode-specific configurations:

```tree
.init-modes/
├── values/            # Mode-specific scalar values.
│   ├── poc.env
│   ├── normal.env
│   └── long-term.env
└── fragments/         # Mode-specific TOML sections to merge.
    └── pyproject/
        ├── poc.toml
        ├── normal.toml
        └── long-term.toml
```

### Mode Values

Files in `values/` contain mode-specific scalar values (numbers, strings) in shell environment format (`.env` files).

### Mode Fragments

Files in `fragments/` contain mode-specific configuration sections that are merged into different configuration files. Each mode should have its own file with all the settings that vary by mode.

## Architecture

The mode system uses a merge-based approach.

### Flow

1. User selects mode during initialization.
2. `init.sh` loads mode-specific values from `.init-modes/values/${MODE}.env`.
3. At some point, loaded environment variables are used to replace scalars in specific files.
    - For example, docstring and test coverage thresholds are applied to the `justfile` via `sed` replacements in `configure_justfile`.
4. Fragments are merged into their base files.
    - For TOML files, `scripts/toml_replacer.py` is used to merge the source mode file to the target file. `generate_template_base_files` function is called:
    - Other formats will have to implement their own strategies, if necessary.
5. For `poc` mode, the PR style check GitHub workflow is disabled.
6. Final configuration files are ready for the new project.

### How the TOML Merger Works

The `scripts/toml_replacer.py` script performs intelligent merging:

- It identifies "concrete sections" in the source TOML (sections that contain actual values, not just nested tables).
- For each section found, it merges that section in the target TOML. That is, if `poc.toml` contains `[tool.ruff.lint]`, that entire section (including all sub-keys) will replace the corresponding sub-keys in `pyproject.toml`. However, any sub-keys present in `pyproject.toml` not in `poc.toml` are kept intact.

## Making Changes

### Updating Shared Settings

Edit the root `pyproject.toml` file directly. Any settings that should be the same across all modes go here.

!!! example "Add a new Ruff rule to all modes"
    1. Edit `pyproject.toml` at the repository root
    2. Add your rule to the `[tool.ruff.lint]` section
    3. Test initialization with all three modes to ensure the setting persists.

!!! warning "Settings Overridden by Modes"
    Some sections in `pyproject.toml` will be merged during initialization based on the mode-specific fragments. Check `.init-modes/fragments/pyproject/` to see which sections vary by mode. Currently these are:

### Updating Mode-Specific Values

Edit files in `values/${mode}.env` to change scalar values for a specific mode.

!!! example "Change POC complexity threshold"
    1. Edit `.init-modes/values/poc.env`.
    2. Change `MCCABE_COMPLEXITY=40` to desired value.
    3. Test POC mode initialization.

### Updating Mode-Specific TOML Settings

Edit files in `.init-modes/fragments/pyproject/` to change linting rules, type checking, or other TOML settings for specific modes.

!!! example "Add an ignore rule to POC mode only"
    1. Edit `.init-modes/fragments/pyproject/poc.toml`.
    2. Add your rule to the `extend-ignore` array under `[tool.ruff.lint]`.
    3. Test POC mode initialization.

!!! example "Make normal mode type checking more strict"
    1. Edit `.init-modes/fragments/pyproject/normal.toml`.
    2. Modify settings under `[tool.pyright]`.
    3. Test normal mode initialization.

### Adding a New Mode-Specific Configuration

To add a new setting that should vary by mode:

#### Scalars values (numbers, strings, booleans)

1. Add the variable to each `.init-modes/values/{mode}.env` file.
2. Use the variable in your shell scripts (it will be available as an environment variable after sourcing).

#### TOML sections

1. Add the section to each `.init-modes/fragments/pyproject/{mode}.toml` file.
2. The section will automatically be merged during initialization.

#### Completely new files

1. Create mode-specific versions in `.init-modes/fragments/`.
2. Update `generate_template_base_files` in `init_utils.sh` to copy the appropriate file or merge them during initialization.
