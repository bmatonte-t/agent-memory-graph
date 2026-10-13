"""Regression coverage for the application's generated API reference."""

import runpy
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from mkdocs import config as mkdocs_config
from mkdocs.structure.files import Files
from mkdocs_gen_files.editor import FilesEditor

if TYPE_CHECKING:
    from collections.abc import Mapping


@pytest.mark.unit
def test_api_reference_covers_application_packages(tmp_path: Path) -> None:
    """Generate complete references with importable src-qualified module paths."""
    root = Path(__file__).resolve().parents[2]
    docs_directory = tmp_path / "docs"
    docs_directory.mkdir()
    generated_directory = tmp_path / "generated"
    generated_directory.mkdir()
    config = mkdocs_config.load_config(
        config_file=StringIO(
            "site_name: Reference Test\n"
            f"docs_dir: {docs_directory}\n"
            f"site_dir: {tmp_path / 'site'}\n"
        ),
    )

    with FilesEditor(Files([]), config, str(generated_directory)) as editor:
        runpy.run_path(str(root / "scripts/generate_api_reference_documentation.py"))
        edit_paths: Mapping[str, str | None] = editor.edit_paths
        for module_name in (
            "src.api.main",
            "src.memory.api",
            "src.pipelines.services.extraction_orchestrator",
        ):
            relative_path = module_name.replace(".", "/")
            document_path = f"api_reference/{relative_path}.md"
            assert (generated_directory / document_path).read_text() == f"::: {module_name}"
            assert edit_paths[document_path] == f"{relative_path}.py"

    navigation = (generated_directory / "api_reference/SUMMARY.md").read_text()
    assert "src/api/main.md" in navigation
    assert "src/memory/api.md" in navigation
