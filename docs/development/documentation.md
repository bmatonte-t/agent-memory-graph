# Template development documentation

This page gets into the specifics for the template's documentation. If you want to find out how to use the documentation in general for your own project, you probably want to visit the [page in the features section](../batteries/documentation.md).

## Build and serve

The template's development setup doesn't have dependencies, because there's no full `pyproject.toml`.

Therefore, we recommend you use `uv` to build and serve the documentation:

```shell
❯ uv run --no-project --with=mkdocs --with=mkdocs-material --with=mkdocs-gen-files --with=mkdocs-literate-nav --with=mkdocs-section-index --with="mkdocstrings[python]" mkdocs serve
```
