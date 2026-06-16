---
applyTo: "tests/**/*.py"
---

# Testing Guidelines

## Testing

- Write unit tests using `pytest`; aim for high coverage.
- Use classes to group related tests.
- Always include type-hints.
- When testing exceptions, use `pytest.raises` as a context manager. Ensure you pass in the `match` kwarg instead of checking the exception message manually.
- Use fixtures to set up any required state or dependencies for your tests.
- You may parametrize tests if necessary.
- Since asyncio_mode = "auto", you don't need to decorate async test functions with `@pytest.mark.asyncio`.
- Focus on testing the input-output behavior of functions. For example, testing whether functions call other functions is undesirable, though sometimes necessary.

## Docstrings

- Add docstrings to all test functions and classes (private and public).
- Use Google style docstrings.
