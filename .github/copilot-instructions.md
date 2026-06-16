# <PROJECT_NAME> - Global Instructions

## Description

<PROJECT_DESCRIPTION>

## General guidance

- If any conventions or workflows are unclear, please ask for clarification or examples.

## Development process

Before saying you're done, you must always solve all linting, formatting and typing errors. If the typing error is tricky to solve, ask me how to do it; I may grant an exception and allow you to use `# type: ignore[type-checker-error]`.

## Tooling

- When asked to run commands, scripts, or tests, use `uv run`.
- To install dependencies, use `uv add <package>`. Use groups where possible (e.g., `uv add --group dev <package>`).
- For the rest of the available commands, run `just --list` to get preconfigured commands.