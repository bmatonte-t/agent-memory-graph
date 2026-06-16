# Task Runner

[`just`](https://just.systems) is a command runner used to define and execute common project tasks. It replaces ad-hoc `Makefile` targets with a simpler, cross-platform syntax and serves as the single entry point for day-to-day development commands.

## Setup

Install from [pre-built binaries](https://just.systems/man/en/pre-built-binaries.html):

```shell
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin
```

Ensure `~/.local/bin` is in your `PATH`.

## Common Commands

Run `just` or `just --list` to see all available commands for your project. Typical ones include:

```shell
just install       # Install project dependencies
just test          # Run the test suite
just lint          # Run linters
just setup-hooks   # Install pre-commit hooks
```
