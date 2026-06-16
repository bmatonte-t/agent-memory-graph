# Script development for the template

All scripts added to the template must use PEP 723 inline dependencies. This is because the template itself isn't a project, so adding dependencies is tricky.

See the [dependency isolation](../batteries/scripts.md#dependency-isolation) section for more.

## How to develop

Inline dependencies are cool for isolation, but you don't get any IDE support.

To work on scripts and get full IDE support, you may use this snippet to create a local venv:

```shell
uv sync --script scripts/script.py
```

You may then point your IDE to the newly created venv.

Alternatively, if you want more than one venv for some reason, you may use this command

```shell
uv venv script.venv && uv export --script scripts/script.py | uv pip install -r - -p script.venv
```

See [#6637](https://github.com/astral-sh/uv/issues/6637) for discussion around this.
