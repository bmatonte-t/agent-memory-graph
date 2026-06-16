# Notebooks

Notebooks (`*.ipynb`) and interactive scripts (`.py`s with `# %%`-delimited cells) are a crucial part of any ML project. They're even useful in normal software development, since they enable developers to quickly prototype and test solutions in a low friction environment. These solutions can then be moved to package code and made more production ready once the proper structure and functionality has been established.

## Location

As stated in the [project structure page](../batteries/project_structure.md), you should place your notebooks in the `notebooks/` directory.

## Linting in Notebooks

The `notebooks/` directory is special in that it has less linting rules enabled to allow for a faster prototyping cycle.

You may check these exclusions in the [`[tool.ruff.lint.per-file-ignores]`](https://github.com/tryolabs/repo-template/blob/main/pyproject.toml#L106-L120) table of the `pyproject.toml`.

Please note that the closest your notebook code is to your production code, the less painful the transfer will be.

## `.ipynb` vs `.py` Interactive

The template supports both traditional Jupyter notebooks (`.ipynb`) and Python files with interactive capabilities.

You and your team can pick a standard, or even combine them.

!!! tip
    If you don't know what to choose, we'd recommend you start with `.py`s with `# %%`-delimited cells. See more in [VSCode's documentation](https://code.visualstudio.com/docs/python/jupyter-support-py#_jupyter-code-cells).

You'd mainly use `.ipynb` due to their inline output preservation, useful to keep a historical record of any analysis you ran when you committed the file to the repo. However, changes to `.ipynb` are extremely tricky to review since GitHub's diff can be very hard to read, making PRs containing `.ipynb`'s huge and unwieldy.

`.py`s with `# %%`-delimited cells are just normal Python scripts (which you can run as such) and you can also run interactively, almost notebook-like, in VSCode. They don't preserve output, which combined with them being normal `.py` files, means their diffs are normal file diffs.

## Notebook Management

### Output Stripping

The template can optionally include `nbstripout` to automatically clean notebook outputs from commits:

- Prevents large diffs from cell outputs
- Keeps repositories clean
- Reduces merge conflicts
- Maintains focus on code changes

!!! note
    This negates the biggest advantage of `.ipynb` files.

## Best Practices

1. **Use descriptive names**: `001_data_exploration.ipynb`. Including and incremental or a date (such as `2025-09-26`) helps sorting the notebooks by date easily.
