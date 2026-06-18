# Troubleshooting

## Imports of my package's code don't work (`ModuleNotFoundError`)

If doing `from my_package.module import symbol` fails, your package may not be correctly installed in your virtual environment, causing issues with Python's default dependency search system.

!!! warning
    If you used the repo template's default setup, this should never happen.

To ensure imports from your package work, you must ensure `uv` correctly installs it. This way, it'll behave like any other package you may import (i.e., `numpy` or  `pandas`).

!!! note
    Once `uv` is able to discover your package, running `uv sync` should install it and print a line to the terminal stating that it did.

`uv` will find your package automatically if the folder containing the code is located in the same folder as the `pyproject.toml` or is a subfolder of `src`. The name of the folder containing the package code must be the same as defined under name in the `name` key of the `[project]` section of the `pyproject.toml`. In case name contains `.` or `-`, these characters must be replaced by `_` for the package folder.

If your package directory doesn't comply with this, you may make it discoverable by configuring the `[tool.hatch.build.targets.wheel]` section in `pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["path_to_my_package"]
```

You may read more about this in [hatchling's build configuration documentation](https://hatch.pypa.io/latest/config/build/#packages).

## `detect-secrets` is bothering me about a hardcoded dummy value

If `detect-secrets` is flagging legitimate test data or configuration as potential secrets, you can update the baseline to include the new detection.

```bash
detect-secrets scan --baseline .secrets.baseline
```

After, commit the updated baseline in its own commit:

```bash
git add .secrets.baseline
git commit -m "Update secrets baseline"
```

If you don't commit the updated baseline, the pre-commit hook will fail and you still won't be able to commit.

## `basedpyright` reports errors that VSCode doesn't

`basedpyright` showing different errors than VS Code's UI can be caused by multiple reasons. However, since we ship uniform configuration for both, this will most likely come down to missing stubs (see [this documentation section](../tutorials/typing.md#stubs) for more on stubs).

The VS Code type checker has common stubs built in, but `basedpyright` doesn't, so you'll need to add them as dependencies. For example, to add stubs for pandas and requests, run

```bash
uv add --group stubs pandas-stubs  # for pandas
uv add --group stubs types-requests  # for requests
```

## Dependabot PR limits

If Dependabot has stopped creating pull requests for dependency updates, it's likely that you may have reached the maximum amount of concurrently open Dependabot PRs.

Check your dependabot configuration in `.github/dependabot.yml` and find the `open-pull-requests-limit` key:

```yaml
# .github/dependabot.yml
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "daily"
    open-pull-requests-limit: 5  # Increase this number or remove the line
```

!!! warning "Important"
    If `open-pull-requests-limit` is set to 0, Dependabot will not create any PRs and will stop security analysis. Make sure it's set to a reasonable number (5-10) or remove the line entirely.

## `pre-commit` hooks are slow

The first time you run your hooks, they get downloaded and their environment set up. Have patience the first time!

If subsequent runs are too slow as well, check if the actions you're performing aren't slow themselves. For example, running tests on push can take a long time.

## Coverage action failing

If the test coverage action is failing in CI/CD, you may check these things:

1. Check coverage locally to see if the coverage is actually low or not. Run `just test-coverage`.
2. If it is too low...

    1. Add missing tests for uncovered code. Always prefer this.
    2. Adjust the coverage threshold in the `just test-coverage` command if the current threshold is too strict.

3. If it is fine, you'll have to do some debugging. Please contribute your findings to this document if you resolve it!

## Agent Memory Graph operational issues

### Health endpoint is healthy but answers are failing

Check the request path in this order:

1. Cloud Run revision health and recent deploy changes.
2. MCP tool logs for `memory_search`, `memory_recall_context`, and `memory_log_trace`.
3. Cloud Trace spans for `orchestrator.respond`, `mcp.invoke`, and `mindmap.execute`.
4. Spanner reachability and recent schema migration changes.

### `Insufficient graph evidence.` appears too often

Common causes:

- query mining produced too few entities
- retrieval horizon is too restrictive
- semantic facts were not ingested for the tenant
- upstream caller is sending the wrong `tenant_id`

Diagnostics:

1. Review the `mindmap.execute` trace and fact count.
2. Confirm semantic nodes exist for the tenant.
3. Check MCP tool traces for earlier ingestion failures.

### Tool errors are spiking

Use the MCP error metric and logs:

1. Check `mcp.tool.errors` by tool name and error code.
2. Inspect structured logs for `mcp_tool_invoke_finish` with error codes.
3. Confirm whether failures are validation, retrieval, or infrastructure-related.

### Cross-tenant access concerns

Treat as a Sev 1/Sev 2 security incident.

1. Preserve request IDs, tenant IDs, and audit events.
2. Confirm the request payload carried the expected tenant.
3. Review audit and structured logs for access-boundary violations.
4. Escalate through the support playbook immediately.

## Known limitations

- Vertex-backed mining and synthesis paths remain environment-dependent.
- Observability exporters degrade gracefully when cloud exporters are not installed, which may hide misconfiguration if startup logs are ignored.
- The current supervisor/worker orchestration path is intentionally lightweight and not a full planner-worker system.

## Getting Help

If you encounter issues not covered here:

1. **Check the repository issues**: Search for similar problems
2. **Create a new issue**: Provide detailed information about your problem
3. **Include environment details**: OS, Python version, uv version, etc.
4. **Provide reproduction steps**: Help others understand and reproduce the issue
