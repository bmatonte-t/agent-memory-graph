# Scripts

The template includes several utility scripts to help with common development tasks. You may also develop some of your own to *document* and *automate* tasks you perform often.

!!! note
    You may delete included scripts if you don't plan on using them.

Scripts can be written in any language you choose, like Python or shell.

## Location

As stated in the [project structure page](../batteries/project_structure.md), you should place your scripts in the `scripts/` directory.

## Included scripts

### Code Complexity Metrics

Analyzes code complexity and maintainability by calculating metrics like cyclomatic complexity and maintainability index.

This script is mandatory if you plan on using the [`code-complexity-metrics`](https://github.com/tryolabs/repo-template/blob/main/.github/workflows/code-complexity-metrics.yaml) GitHub Workflow.

You may run it with `uv run scripts/code_complexity_metrics.py --help`.

### GitHub Metric calculator

Collects repository metrics and statistics by analyzing issues, pull requests, and contributor activity.

This is useful when filling the Quarterly Delivery Questionnaire, that asks about these metrics.

You can think of this more like a utility, and can safely delete it if you don't plan on using it.

You may run it with `uv run scripts/github_metrics.py --help`.

## Dependency Isolation

Sometimes you want to write a script but don't want to add dependencies to your whole project.

!!! example
    Say you want to run a quick word count per file and output a pretty table. You may use `textual` for output formatting. However, adding the dependency to your `pyproject.toml` may make resolution more complex.

To add new utility scripts to the template or to your project without adding dependencies, use inline metadata ([PEP 723](https://peps.python.org/pep-0723/)).

To run these, you need a runner that supports PEP 723. One such runner is `uv`. You may run these scripts using `uv run scripts/...`.

## TOML replacer

Merge TOML sections from a source file into a target TOML file while preserving comments and formatting. Values that exist only in the target file are kept, new values from the source are added and values that exist in both are overwritten in the target with values from the source.

This is useful when you want to copy specific tool configuration blocks from a template or shared config into your project's `pyproject.toml` or other TOML files without losing existing settings.

!!! example
    Merge sections from `template.toml` into your `pyproject.toml`.

    ```shell
    uv run scripts/toml_replacer.py --target pyproject.toml --source template.toml
    ```

## Creating New Scripts

Just add your new scripts to the `scripts/` directory.

If you want to avoid adding dependencies, consider using `uv add --script` to add PEP 723-compliant inline dependencies to your script.

!!! note
    You must use inlined dependencies when developing scripts for the template, since we don't specify a set of dependencies we can install.
