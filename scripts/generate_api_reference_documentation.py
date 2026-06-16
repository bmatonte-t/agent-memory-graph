"""Generate the code reference pages and navigation."""

from pathlib import Path

from mkdocs_gen_files.editor import FilesEditor
from mkdocs_gen_files.nav import Nav


def find_package(root: Path) -> Path:
    """Find the package directory under `src/`.

    The project follows the src layout, so the package is the single directory inside `src/` that
    has an `__init__.py`.

    Args:
        root: The root directory to search in.

    Raises:
        ValueError: If no package directory is found.

    Returns:
        Path: The path to the package directory.
    """
    src_directory = root / "src"
    if src_directory.is_dir():
        for item in src_directory.iterdir():
            if item.is_dir() and (item / "__init__.py").is_file():
                return item

    message = f"No package directory found in {src_directory}."
    raise ValueError(message)


def main() -> None:
    """Generate API reference documentation."""
    site_navigation = Nav()
    file_editor = FilesEditor.current()

    root = Path(__file__).parent.parent
    api_reference_documentation_directory = Path("api_reference")

    package_directory = find_package(root)
    src_directory = package_directory.parent

    for path in sorted(package_directory.rglob("*.py")):
        # Module / doc paths are computed relative to `src/` so that the dotted
        # module path matches the actual import path (e.g. `project_base.foo`
        # rather than `src.project_base.foo`).
        path_relative = path.relative_to(src_directory)
        path_repo_relative = path.relative_to(root)
        # parts: similar to splitting the path on / but doesn't depend on OS.
        path_parts_no_extension = path_relative.with_suffix("").parts

        documentation_file = path_relative.with_suffix(".md")

        if path.stem == "__init__":
            # Document __init__.py in index.md.
            path_parts_no_extension = path_parts_no_extension[:-1]
            documentation_file = documentation_file.with_name("index.md")
        elif path.stem == "__main__":
            # Don't document __main__.py files.
            continue

        # Generate new navigation entry.
        site_navigation[path_parts_no_extension] = str(documentation_file)

        # Write documentation file.
        full_doc_path = api_reference_documentation_directory / documentation_file
        with file_editor.open(full_doc_path, "w") as fd:  # type: ignore[reportUnknownMemberType,reportArgumentType,reportUnknownVariableType]; wrong library type-hints.
            module_path = ".".join(path_parts_no_extension)
            fd.write(f"::: {module_path}")  # type: ignore[reportUnknownMemberType]; wrong library type-hints.

        file_editor.set_edit_path(str(full_doc_path), str(path_repo_relative))

    with file_editor.open(api_reference_documentation_directory / "SUMMARY.md", "w") as nav_file:  # type: ignore[reportUnknownMemberType,reportArgumentType,reportUnknownVariableType]; wrong library type-hints.
        nav_file.writelines(site_navigation.build_literate_nav())  # type: ignore[reportUnknownMemberType]; wrong library type-hints.


main()
