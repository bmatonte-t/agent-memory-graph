# Git Hooks

The template includes the `pre-commit` dependency, which enables automatic execution of tooling on key `git` events like commit generation (`git commit`) or pushing (`git push`).

## Setup

All users of the spawned repo, without exception, should run `just setup-hooks`. This will ensure `pre-commit` is installed and configured to run on relevant `git` events.

!!! note
    This step is run automatically for the person that spawned the template.

### Included Hooks

- **Code formatting and linting with `ruff`:** Automatically formats and lints code before commits. See the [linting and formatting section](./code_quality.md#linting-and-formatting) for more.
- **Secret detection:** Scans for potential secrets and credentials before commits. See the [detect secrets section](./code_quality.md#secret-detection) for more.
- **Prevent commits to commonly important branches:** Prevents committing to `main`, `master` and any branch whose name starts with `dev`.
- **Large file detection:** Prevents accidentally committing files larger than 5120 kB.
- **Common file format checkers:** Check that any to-be-committed JSON, TOML or YAML are valid.
- **Ensure all names are legal in Windows as well:** It should be strange, but sometimes we work under Windows. This hook ensures files committed from UNIX systems have names that are also valid in Windows.
