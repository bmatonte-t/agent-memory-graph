---
applyTo: "**/*.py"
---

# Python Source Code Guidelines

## Coding guidelines

- Always write code for **Python 3.14**.
- Write clear and concise comments for complex logic. Do not explain what the code does but, rather, why it's done or why you chose one approach over the other when it's not obvious.
- Prefer functional programming approaches where they make sense.
- Prefer `pathlib` over `os.path` for path manipulations.
- When you need to define structure, you may use Pydantic BaseModels. For return types, you may use NamedTuples.
- Use `f-strings` for string formatting.
- Use `logging` module for logging; avoid `print` statements. All the code you write should use logging extensively where it makes sense.
- Long `try` blocks or broad `except Exception` blocks should be avoided. Instead, try/except blocks should be short and catch specific exceptions, where possible.
- Do not use abbreviations when naming things, except for `env`, `id` or `idx`.

## Type hinting

- **Always use type hints** for function arguments and return values (e.g., `def my_function(name: str) -> int:`).
- Prefer generic types from `collections.abc` (e.g., `Iterable`, `Mapping`) over concrete types (e.g., `list`, `dict`) in type hints for function parameters.
- Prefer concrete types for return types (i.e., `list[str]` over `Iterable[str]`). You know exactly what you are returning, but you don't know how the function will be used.
- Use `type | None` instead of `Optional[type]` (e.g., `str | None`).
- Declare `StrEnum`s when necessary for fixed sets of string values.

## Data Science Best Practices

- Prefer vectorization (numpy/pandas/polars native) over `apply`. Only use iteration over the dataframe (with a `for` loop) as a last resort.
- Always set `random_state` or `seed` in examples and model initializations so that code is reproducible.

## Docstrings

- Add docstrings to all functions and classes (private and public).
- Use Google style docstrings.
- When writing default values, use a new sentence like `Defaults to X` instead of `by default X`. Also, if the default is `None`, include a `When None, do Y`. Example:

  ```python
    as_of (datetime | None, optional): The reference datetime to determine the year from.
        When None, uses current moment. Defaults to None.
    ```

- When documenting BaseModel, NamedTuple, dataclass or TypedDict attributes, do so with docstrings for the attributes themselves and NOT in the class docstring (which only describes the container type).
