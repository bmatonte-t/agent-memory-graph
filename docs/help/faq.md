# Frequently Asked Questions

## Where can I have personal files that `git` doesn't track?

Use `.personal_workspace`.

## How do I delete local branches automatically when deleted from the repo?

This ZSH function will help:

```zsh
g_cleanup_branches_force (){
  git remote prune origin && git branch -vv | grep ': gone]'|  grep -v "\*" | awk '{ print $1; }' | xargs -r git branch -D
}
```

Add it to your `~/.zshrc`, run `exec $SHELL` to reload it and execute it from your terminal.

## Python Version Management

### How should I specify my Python version in `pyproject.toml`?

Always include an upper bound in your Python version specification:

```toml
[project]
requires-python = "~=3.14"
```

or

```toml
[project]
requires-python = ">=3.11,<4.0"
```

depending on whether you want to remain in `3.11` (`~=`) or you want minor version bumps (`>=,<`).

Python 4.0 will likely introduce breaking changes and we don't want to be surprised.

## Dependency Management

### Should I commit the `uv.lock` file?

**Yes, always commit `uv.lock`** to version control.

See the [documentation](../batteries/dev_environment.md#why-use-a-package-manager-instead-of-just-pip) on what it does in the development section.

## Code Quality

### How strict should I make the linting rules?

We recommend you start with template defaults, then gradually increase strictness (especially for the type checking rules).

!!! note
    If you disable any specific rules, please let us know by [opening an issue](https://github.com/tryolabs/repo-template/issues/new)! We may need to disable the rule template wide.

Short projects can be more lenient than mature ones. You can also be a bit more lenient at the start to move fast, as long as you budget time to repay that tech debt in the future.

### Pylance type checking is too annoying, what should I do?

First, experiment with disabling the `reportUnknown*` set of rules one by one. Check in `pyproject.toml` under `[tool.pyright]`.

You can then try to decrease the `typeCheckingMode` to `"basic"`, though we'd advise against that.

## Secrets

### Where should I place my `.env` or `.env.sample`?

Place them at the root of your repo, not inside your package code.

## Testing

### What's the difference between unit tests and integration tests?

#### Unit Tests

- Test individual functions/methods in isolation.
- Use mocks for external dependencies.
- Fast execution.
- High coverage of code paths.

#### Integration Tests

- Test multiple components working together.
- Use real dependencies (databases, APIs, etc.).
- Slower execution.
- Test realistic user scenarios.

#### Organization in template

```text
tests/
├── unit/           # Fast, isolated tests
├── integration/    # Tests with real dependencies
└── conftest.py     # Shared fixtures
```

## Documentation

### Should I document every function?

Consult the [docstrings](../tutorials/docstrings.md) tutorial.

## Getting More Help

### Where can I get support?

1. **Repository Issues:** Check existing [issues](https://github.com/tryolabs/repo-template/issues) or create a new one.
2. **Documentation:** Review this documentation thoroughly.
3. **Slack:** You may ask in [:material-slack: #team-repo-template](https://tryo.slack.com/archives/C08TL160ZLK) for template-related things.

### How can I contribute improvements?

See the [contributing](../development/CONTRIBUTING.md) section.
