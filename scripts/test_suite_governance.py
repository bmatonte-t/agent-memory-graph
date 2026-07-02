"""Audit and enforce testing governance rules.

This script centralizes operational checks for the testing redesign program:
- Inventory test files and marker usage.
- Detect integration tests with excessive mocking density.
- Enforce baseline policy in CI to avoid new governance regressions.
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

INTEGRATION_PATH_FRAGMENT = "tests/integration"
DEFAULT_DENSITY_THRESHOLD = 12.0
DEFAULT_ABSOLUTE_REFERENCE_THRESHOLD = 80
DEFAULT_MAX_TEST_FILE_LINES = 700
MERGE_TRIAGE_FILE_COUNT = 2
REWRITE_TRIAGE_FILE_COUNT = 3
RECLASSIFY_COMPONENT_DENSITY_THRESHOLD = 6.0
RECLASSIFY_CONTRACT_DENSITY_THRESHOLD = 3.0
RECLASSIFY_COMPONENT_REFERENCE_THRESHOLD = 30
RECLASSIFY_CONTRACT_REFERENCE_THRESHOLD = 15
RECLASSIFY_MINIMUM_DENSITY_THRESHOLD = 2.0
MOCK_PATTERN = re.compile(r"patch\(|MagicMock|AsyncMock|monkeypatch")
TEST_PATTERN = re.compile(r"^\s*def test_|^\s*class Test", flags=re.MULTILINE)
MARKER_PATTERN = re.compile(r"@pytest\.mark\.([a-zA-Z0-9_]+)")
logger = logging.getLogger(__name__)


class BaselineLoadError(Exception):
    """Raised when the baseline policy cannot be loaded or validated."""


@dataclass(slots=True)
class IntegrationMockingRecord:
    """Represents mocking density metrics for one integration test file.

    Attributes:
        path: Relative path to the test file.
        mock_references: Number of mocking references found in the file.
        test_items: Number of test functions or test classes in the file.
        density: Ratio between mocking references and test items.
    """

    path: str
    mock_references: int
    test_items: int
    density: float


@dataclass(slots=True)
class GovernanceSummary:
    """Summarizes suite governance metrics.

    Attributes:
        total_test_files: Number of discovered test files.
        total_test_items: Number of test items (functions and classes).
        integration_test_files: Number of integration test files.
        integration_mock_references: Sum of mocking references in integration tests.
        integration_mock_density_average: Average mocking density in integration tests.
        markers: Marker usage frequency across test files.
        duplicate_test_identifiers: Number of duplicate test identifiers across files.
    """

    total_test_files: int
    total_test_items: int
    integration_test_files: int
    integration_mock_references: int
    integration_mock_density_average: float
    markers: dict[str, int]
    duplicate_test_identifiers: int


@dataclass(slots=True)
class DuplicateTriageRecord:
    """Recommended action for a duplicated test identifier cluster.

    Attributes:
        identifier: Duplicated test identifier.
        files: Files containing the duplicate.
        recommended_action: Suggested triage action.
        rationale: Why this action is recommended.
    """

    identifier: str
    files: list[str]
    recommended_action: str
    rationale: str


@dataclass(slots=True)
class IntegrationReclassificationCandidate:
    """Recommended destination layer for over-mocked integration tests.

    Attributes:
        path: Relative path to the integration test file.
        mock_references: Number of mocking references in the file.
        test_items: Number of test functions or classes in the file.
        density: Mocking references per test item.
        recommended_layer: Suggested target layer after decomposition.
        rationale: Why this candidate should be reclassified.
    """

    path: str
    mock_references: int
    test_items: int
    density: float
    recommended_layer: str
    rationale: str


@dataclass(slots=True)
class LargestTestFileRecord:
    """Represents concentration hotspots by file size.

    Attributes:
        path: Relative path to the test file.
        line_count: Total line count in the file.
        test_items: Number of test functions or classes in the file.
    """

    path: str
    line_count: int
    test_items: int


@dataclass(slots=True)
class LargeTestFileViolationRecord:
    """Represents a test file exceeding line-count governance limits.

    Attributes:
        path: Relative path to the test file.
        line_count: Total line count in the file.
        test_items: Number of test functions or classes in the file.
    """

    path: str
    line_count: int
    test_items: int


@dataclass(slots=True)
class DuplicateClusterRecord:
    """Represents duplicate identifier cluster concentration.

    Attributes:
        identifier: Duplicate test identifier.
        files: Files where the identifier appears.
        cluster_size: Number of files in the cluster.
    """

    identifier: str
    files: list[str]
    cluster_size: int


def discover_test_files(tests_root: Path) -> list[Path]:
    """Discover all pytest test files under the tests root.

    Args:
        tests_root: Root directory for tests.

    Returns:
        List of discovered test files.
    """
    return sorted(tests_root.rglob("test_*.py"))


def relative_path(path: Path, root: Path) -> str:
    """Convert path to a stable POSIX relative representation.

    Args:
        path: Path to convert.
        root: Root used as relative origin.

    Returns:
        Stable relative path.
    """
    return path.relative_to(root).as_posix()


def extract_test_identifiers(content: str) -> list[str]:
    """Extract test identifiers from Python source.

    Args:
        content: Python source content.

    Returns:
        Test identifiers with optional class prefix.
    """
    module = ast.parse(content)
    identifiers: list[str] = []

    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            identifiers.append(node.name)

        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            identifiers.extend(
                [
                    f"{node.name}::{class_node.name}"
                    for class_node in node.body
                    if isinstance(class_node, ast.FunctionDef)
                    and class_node.name.startswith("test_")
                ]
            )

    return identifiers


def duplicate_test_identifiers(root: Path, test_files: list[Path]) -> dict[str, list[str]]:
    """Find duplicate test identifiers across different files.

    Args:
        root: Repository root.
        test_files: Discovered test files.

    Returns:
        Mapping of duplicate identifier to list of files where it appears.
    """
    identifier_to_paths: dict[str, list[str]] = {}

    for file_path in test_files:
        content = file_path.read_text(encoding="utf-8")
        rel_path = relative_path(file_path, root)
        for identifier in extract_test_identifiers(content):
            identifier_to_paths.setdefault(identifier, []).append(rel_path)

    duplicates: dict[str, list[str]] = {}
    for identifier, paths in identifier_to_paths.items():
        unique_paths = sorted(set(paths))
        if len(unique_paths) > 1:
            duplicates[identifier] = unique_paths

    return dict(sorted(duplicates.items(), key=lambda item: item[0]))


def count_markers(content: str) -> dict[str, int]:
    """Count pytest markers in file content.

    Args:
        content: Python source content.

    Returns:
        Marker name to frequency mapping.
    """
    marker_count: dict[str, int] = {}
    for marker in MARKER_PATTERN.findall(content):
        marker_count[marker] = marker_count.get(marker, 0) + 1
    return marker_count


def merge_counts(base: dict[str, int], increment: dict[str, int]) -> dict[str, int]:
    """Merge count dictionaries.

    Args:
        base: Base count mapping.
        increment: Incremental count mapping.

    Returns:
        Updated count mapping.
    """
    for key, value in increment.items():
        base[key] = base.get(key, 0) + value
    return base


def integration_mocking_records(
    root: Path,
    test_files: list[Path],
) -> list[IntegrationMockingRecord]:
    """Build mocking density records for integration tests.

    Args:
        root: Repository root.
        test_files: Discovered test files.

    Returns:
        Sorted integration mocking records by descending density.
    """
    records: list[IntegrationMockingRecord] = []
    for file_path in test_files:
        rel_path = relative_path(file_path, root)
        if INTEGRATION_PATH_FRAGMENT not in rel_path:
            continue

        content = file_path.read_text(encoding="utf-8")
        references = len(MOCK_PATTERN.findall(content))
        test_items = len(TEST_PATTERN.findall(content))
        density = float(references) / max(1, test_items)

        records.append(
            IntegrationMockingRecord(
                path=rel_path,
                mock_references=references,
                test_items=test_items,
                density=round(density, 2),
            )
        )

    return sorted(records, key=lambda item: (item.density, item.mock_references), reverse=True)


def build_summary(root: Path, test_files: list[Path]) -> GovernanceSummary:
    """Compute top-level governance summary.

    Args:
        root: Repository root.
        test_files: Discovered test files.

    Returns:
        Governance summary.
    """
    total_items = 0
    marker_count: dict[str, int] = {}

    for file_path in test_files:
        content = file_path.read_text(encoding="utf-8")
        total_items += len(TEST_PATTERN.findall(content))
        marker_count = merge_counts(marker_count, count_markers(content))

    integration_records = integration_mocking_records(root, test_files)
    duplicated_identifiers = duplicate_test_identifiers(root, test_files)
    integration_density_average = 0.0
    if integration_records:
        integration_density_average = round(
            sum(record.density for record in integration_records) / len(integration_records),
            2,
        )

    return GovernanceSummary(
        total_test_files=len(test_files),
        total_test_items=total_items,
        integration_test_files=len(integration_records),
        integration_mock_references=sum(record.mock_references for record in integration_records),
        integration_mock_density_average=integration_density_average,
        markers=dict(sorted(marker_count.items(), key=lambda item: item[0])),
        duplicate_test_identifiers=len(duplicated_identifiers),
    )


def load_baseline(baseline_path: Path) -> dict[str, Any]:
    """Load baseline policy from JSON file.

    Args:
        baseline_path: Path to baseline JSON file.

    Returns:
        Baseline policy dictionary.

    Raises:
        BaselineLoadError: When baseline file is malformed.
    """
    try:
        baseline_payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        message = f"Baseline file not found: {baseline_path}"
        raise BaselineLoadError(message) from error
    except json.JSONDecodeError as error:
        message = f"Invalid JSON in baseline: {baseline_path}"
        raise BaselineLoadError(message) from error

    if not isinstance(baseline_payload, dict):
        message = "Baseline payload must be a JSON object"
        raise TypeError(message)

    return baseline_payload


def find_new_mocking_violations(
    records: list[IntegrationMockingRecord],
    baseline: dict[str, Any],
) -> list[IntegrationMockingRecord]:
    """Detect violations outside the approved baseline.

    Args:
        records: Integration mocking records.
        baseline: Baseline policy payload.

    Returns:
        Violations not included in allowlist.
    """
    thresholds = baseline.get("thresholds", {})
    density_threshold = float(thresholds.get("max_density", DEFAULT_DENSITY_THRESHOLD))
    absolute_threshold = int(
        thresholds.get("max_mock_references", DEFAULT_ABSOLUTE_REFERENCE_THRESHOLD)
    )

    approved = baseline.get("approved_over_mocked_integration_files", [])
    approved_paths = {
        item.get("path")
        for item in approved
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }

    violations: list[IntegrationMockingRecord] = []
    for record in records:
        is_over_threshold = (
            record.density > density_threshold or record.mock_references > absolute_threshold
        )
        if is_over_threshold and record.path not in approved_paths:
            violations.append(record)

    return violations


def find_new_duplicate_identifier_violations(
    duplicated_identifiers: dict[str, list[str]],
    baseline: dict[str, Any],
) -> dict[str, list[str]]:
    """Detect duplicate identifiers outside the approved baseline.

    Args:
        duplicated_identifiers: Duplicate identifiers and file mappings.
        baseline: Baseline policy payload.

    Returns:
        Duplicate identifiers not approved in baseline.
    """
    approved = baseline.get("approved_duplicate_test_identifiers", [])
    approved_identifiers = {item for item in approved if isinstance(item, str)}

    return {
        identifier: paths
        for identifier, paths in duplicated_identifiers.items()
        if identifier not in approved_identifiers
    }


def triage_duplicate_identifiers(
    duplicated_identifiers: dict[str, list[str]],
) -> list[DuplicateTriageRecord]:
    """Generate action recommendations for duplicate identifier clusters.

    Heuristic policy:
    - 2 files: merge into one canonical test and retire duplicate.
    - 3 files: rewrite into one canonical plus one contract/integration boundary test.
    - 4+ files: keep one canonical, merge related assertions, retire extras.

    Args:
        duplicated_identifiers: Duplicate identifiers and file mappings.

    Returns:
        Sorted triage recommendation records.
    """
    recommendations: list[DuplicateTriageRecord] = []

    for identifier, files in duplicated_identifiers.items():
        file_count = len(files)

        if file_count == MERGE_TRIAGE_FILE_COUNT:
            recommended_action = "merge"
            rationale = (
                "Identifier appears in two files; consolidate assertions into one canonical "
                "test and retire the duplicate."
            )
        elif file_count == REWRITE_TRIAGE_FILE_COUNT:
            recommended_action = "rewrite"
            rationale = (
                "Identifier appears in three files; rewrite into one canonical behavior test "
                "plus one boundary-focused test, then retire remaining duplication."
            )
        else:
            recommended_action = "retire"
            rationale = (
                "Identifier appears in four or more files; keep one canonical test, merge unique "
                "assertions, and retire redundant copies."
            )

        recommendations.append(
            DuplicateTriageRecord(
                identifier=identifier,
                files=files,
                recommended_action=recommended_action,
                rationale=rationale,
            )
        )

    return sorted(recommendations, key=lambda item: item.identifier)


def identify_reclassification_candidates(
    records: list[IntegrationMockingRecord],
) -> list[IntegrationReclassificationCandidate]:
    """Identify integration tests that should be moved to lower layers.

    Args:
        records: Integration mocking records.

    Returns:
        Ordered reclassification candidates.
    """
    candidates: list[IntegrationReclassificationCandidate] = []

    for record in records:
        if record.density < RECLASSIFY_MINIMUM_DENSITY_THRESHOLD:
            continue

        if (
            record.density >= RECLASSIFY_COMPONENT_DENSITY_THRESHOLD
            or record.mock_references >= RECLASSIFY_COMPONENT_REFERENCE_THRESHOLD
        ):
            recommended_layer = "component"
            rationale = (
                "High mocking density indicates behavior-level logic dominates over real wiring; "
                "split into component tests with explicit dependency fakes."
            )
        elif (
            record.density >= RECLASSIFY_CONTRACT_DENSITY_THRESHOLD
            or record.mock_references >= RECLASSIFY_CONTRACT_REFERENCE_THRESHOLD
        ):
            recommended_layer = "contract"
            rationale = (
                "Moderate-to-high mocking suggests boundary verification; move protocol "
                "and adapter "
                "assertions to contract tests and keep thin integration wiring checks."
            )
        else:
            recommended_layer = "integration"
            rationale = (
                "Mocking is elevated but below structural thresholds; keep in "
                "integration and reduce "
                "local patch surface incrementally."
            )

        candidates.append(
            IntegrationReclassificationCandidate(
                path=record.path,
                mock_references=record.mock_references,
                test_items=record.test_items,
                density=record.density,
                recommended_layer=recommended_layer,
                rationale=rationale,
            )
        )

    return candidates


def top_largest_test_files(
    root: Path,
    test_files: list[Path],
    limit: int = 10,
) -> list[LargestTestFileRecord]:
    """Return largest test files by line count.

    Args:
        root: Repository root.
        test_files: Discovered test files.
        limit: Maximum number of records to return.

    Returns:
        Largest file records sorted by descending size.
    """
    records: list[LargestTestFileRecord] = []

    for file_path in test_files:
        content = file_path.read_text(encoding="utf-8")
        line_count = len(content.splitlines())
        test_items = len(TEST_PATTERN.findall(content))
        records.append(
            LargestTestFileRecord(
                path=relative_path(file_path, root),
                line_count=line_count,
                test_items=test_items,
            )
        )

    return sorted(records, key=lambda item: item.line_count, reverse=True)[:limit]


def find_new_large_file_violations(
    records: list[LargestTestFileRecord],
    baseline: dict[str, Any],
) -> list[LargeTestFileViolationRecord]:
    """Detect test files exceeding max line-count outside approved baseline.

    Args:
        records: File size records for test files.
        baseline: Baseline policy payload.

    Returns:
        Large file violations not included in the approved baseline list.
    """
    thresholds = baseline.get("thresholds", {})
    line_count_threshold = int(thresholds.get("max_test_file_lines", DEFAULT_MAX_TEST_FILE_LINES))

    approved = baseline.get("approved_large_test_files", [])
    approved_paths = {
        item.get("path")
        for item in approved
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }

    return [
        LargeTestFileViolationRecord(
            path=record.path,
            line_count=record.line_count,
            test_items=record.test_items,
        )
        for record in records
        if record.line_count > line_count_threshold and record.path not in approved_paths
    ]


def top_duplicate_clusters(
    duplicated_identifiers: dict[str, list[str]],
    limit: int = 10,
) -> list[DuplicateClusterRecord]:
    """Return the largest duplicate identifier clusters.

    Args:
        duplicated_identifiers: Duplicate identifiers and file mappings.
        limit: Maximum number of records to return.

    Returns:
        Largest duplicate clusters sorted by cluster size.
    """
    records = [
        DuplicateClusterRecord(
            identifier=identifier,
            files=files,
            cluster_size=len(files),
        )
        for identifier, files in duplicated_identifiers.items()
    ]
    return sorted(records, key=lambda item: item.cluster_size, reverse=True)[:limit]


def render_new_policy_violations_section(violations: list[IntegrationMockingRecord]) -> list[str]:
    """Render markdown section for unapproved policy violations.

    Args:
        violations: Unapproved over-mocking violations.

    Returns:
        Markdown lines for the section.
    """
    lines = ["## New policy violations", ""]
    if not violations:
        lines.append("- None")
        return lines

    lines.extend(
        [
            (
                f"- {violation.path} (refs={violation.mock_references}, "
                f"tests={violation.test_items}, density={violation.density})"
            )
            for violation in violations
        ]
    )
    return lines


def render_reclassification_section(
    reclassification_candidates: list[IntegrationReclassificationCandidate],
) -> list[str]:
    """Render markdown section for integration reclassification candidates.

    Args:
        reclassification_candidates: Layer reclassification candidates.

    Returns:
        Markdown lines for the section.
    """
    lines = ["## Integration reclassification candidates", ""]
    if not reclassification_candidates:
        lines.append("- None")
        return lines

    lines.append("| file | mock_references | test_items | density | recommended_layer |")
    lines.append("|---|---:|---:|---:|---|")
    lines.extend(
        [
            (
                f"| {candidate.path} | {candidate.mock_references} | "
                f"{candidate.test_items} | {candidate.density} | "
                f"{candidate.recommended_layer} |"
            )
            for candidate in reclassification_candidates
        ]
    )
    return lines


def render_largest_test_files_section(largest_test_files: list[LargestTestFileRecord]) -> list[str]:
    """Render markdown section for largest test files.

    Args:
        largest_test_files: Largest test files by line count.

    Returns:
        Markdown lines for the section.
    """
    lines = ["## Hotspots: largest test files", ""]
    if not largest_test_files:
        lines.append("- None")
        return lines

    lines.append("| file | line_count | test_items |")
    lines.append("|---|---:|---:|")
    lines.extend(
        [
            f"| {record.path} | {record.line_count} | {record.test_items} |"
            for record in largest_test_files
        ]
    )
    return lines


def render_duplicate_clusters_section(
    duplicate_clusters: list[DuplicateClusterRecord],
) -> list[str]:
    """Render markdown section for duplicate cluster hotspots.

    Args:
        duplicate_clusters: Largest duplicate identifier clusters.

    Returns:
        Markdown lines for the section.
    """
    lines = ["## Hotspots: duplicate clusters", ""]
    if not duplicate_clusters:
        lines.append("- None")
        return lines

    lines.append("| identifier | cluster_size | files |")
    lines.append("|---|---:|---|")
    lines.extend(
        [
            (f"| {cluster.identifier} | {cluster.cluster_size} | {', '.join(cluster.files)} |")
            for cluster in duplicate_clusters
        ]
    )
    return lines


def render_duplicate_identifier_violations_section(
    duplicate_identifier_violations: dict[str, list[str]],
) -> list[str]:
    """Render markdown section for unapproved duplicate identifiers.

    Args:
        duplicate_identifier_violations: Duplicate identifiers outside baseline.

    Returns:
        Markdown lines for the section.
    """
    lines = ["## New duplicate identifier violations", ""]
    if not duplicate_identifier_violations:
        lines.append("- None")
        return lines

    lines.extend(
        [
            f"- {identifier}: {', '.join(paths)}"
            for identifier, paths in duplicate_identifier_violations.items()
        ]
    )
    return lines


def render_new_large_file_violations_section(
    violations: list[LargeTestFileViolationRecord],
) -> list[str]:
    """Render markdown section for large-file governance violations.

    Args:
        violations: Files above line-count threshold and outside baseline.

    Returns:
        Markdown lines for the section.
    """
    lines = ["## New large test file violations", ""]
    if not violations:
        lines.append("- None")
        return lines

    lines.append("| file | line_count | test_items |")
    lines.append("|---|---:|---:|")
    lines.extend(
        [
            (f"| {violation.path} | {violation.line_count} | {violation.test_items} |")
            for violation in violations
        ]
    )
    return lines


def render_duplicate_triage_section(
    duplicate_triage_recommendations: list[DuplicateTriageRecord],
) -> list[str]:
    """Render markdown section for duplicate triage recommendations.

    Args:
        duplicate_triage_recommendations: Triage actions for duplicate identifiers.

    Returns:
        Markdown lines for the section.
    """
    lines = ["## Duplicate triage recommendations", ""]
    if not duplicate_triage_recommendations:
        lines.append("- None")
        return lines

    lines.append("| identifier | files | action | rationale |")
    lines.append("|---|---|---|---|")
    lines.extend(
        [
            (
                f"| {recommendation.identifier} | "
                f"{', '.join(recommendation.files)} | "
                f"{recommendation.recommended_action} | "
                f"{recommendation.rationale} |"
            )
            for recommendation in duplicate_triage_recommendations
        ]
    )
    return lines


def markdown_report(
    summary: GovernanceSummary,
    records: list[IntegrationMockingRecord],
    violations: list[IntegrationMockingRecord],
    reclassification_candidates: list[IntegrationReclassificationCandidate],
    largest_test_files: list[LargestTestFileRecord],
    duplicate_clusters: list[DuplicateClusterRecord],
    duplicate_triage_recommendations: list[DuplicateTriageRecord],
    duplicate_identifier_violations: dict[str, list[str]],
    large_file_violations: list[LargeTestFileViolationRecord],
) -> str:
    """Render markdown report for governance state.

    Args:
        summary: Governance summary.
        records: Integration mocking records.
        violations: New unapproved violations.
        reclassification_candidates: Integration candidates for layer reclassification.
        largest_test_files: Largest test files by line count.
        duplicate_clusters: Largest duplicate identifier clusters.
        duplicate_triage_recommendations: Triage actions for duplicate identifiers.
        duplicate_identifier_violations: New unapproved duplicate identifiers.
        large_file_violations: New unapproved large test file violations.

    Returns:
        Markdown report content.
    """
    lines: list[str] = []
    lines.append("# Testing Governance Inventory")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- total_test_files: {summary.total_test_files}")
    lines.append(f"- total_test_items: {summary.total_test_items}")
    lines.append(f"- integration_test_files: {summary.integration_test_files}")
    lines.append(f"- integration_mock_references: {summary.integration_mock_references}")
    lines.append(f"- integration_mock_density_average: {summary.integration_mock_density_average}")
    lines.append(f"- duplicate_test_identifiers: {summary.duplicate_test_identifiers}")
    lines.append("")
    lines.append("## Marker usage")
    lines.append("")

    for marker, count in summary.markers.items():
        lines.append(f"- {marker}: {count}")

    lines.append("")
    lines.append("## Integration mocking density (top 20)")
    lines.append("")
    lines.append("| file | mock_references | test_items | density |")
    lines.append("|---|---:|---:|---:|")
    lines.extend(
        [
            (
                f"| {record.path} | {record.mock_references} | "
                f"{record.test_items} | {record.density} |"
            )
            for record in records[:20]
        ]
    )

    lines.append("")
    lines.extend(render_new_policy_violations_section(violations))
    lines.append("")
    lines.extend(render_reclassification_section(reclassification_candidates))
    lines.append("")
    lines.extend(render_largest_test_files_section(largest_test_files))
    lines.append("")
    lines.extend(render_duplicate_clusters_section(duplicate_clusters))
    lines.append("")
    lines.extend(render_duplicate_identifier_violations_section(duplicate_identifier_violations))
    lines.append("")
    lines.extend(render_new_large_file_violations_section(large_file_violations))
    lines.append("")
    lines.extend(render_duplicate_triage_section(duplicate_triage_recommendations))

    lines.append("")
    return "\n".join(lines)


def build_json_payload(
    summary: GovernanceSummary,
    records: list[IntegrationMockingRecord],
    violations: list[IntegrationMockingRecord],
    duplicated_identifiers: dict[str, list[str]],
    reclassification_candidates: list[IntegrationReclassificationCandidate],
    largest_test_files: list[LargestTestFileRecord],
    duplicate_clusters: list[DuplicateClusterRecord],
    duplicate_triage_recommendations: list[DuplicateTriageRecord],
    duplicate_identifier_violations: dict[str, list[str]],
    large_file_violations: list[LargeTestFileViolationRecord],
) -> dict[str, Any]:
    """Build JSON payload for inventory artifact.

    Args:
        summary: Governance summary.
        records: Integration mocking records.
        violations: Unapproved policy violations.
        duplicated_identifiers: Duplicate identifiers found in the suite.
        reclassification_candidates: Integration candidates for layer reclassification.
        largest_test_files: Largest test files by line count.
        duplicate_clusters: Largest duplicate identifier clusters.
        duplicate_triage_recommendations: Triage actions for duplicate identifiers.
        duplicate_identifier_violations: New duplicate identifier violations.
        large_file_violations: New large-file violations outside baseline approvals.

    Returns:
        Serializable JSON payload.
    """
    return {
        "summary": asdict(summary),
        "integration_mocking_records": [asdict(record) for record in records],
        "new_policy_violations": [asdict(record) for record in violations],
        "integration_reclassification_candidates": [
            asdict(record) for record in reclassification_candidates
        ],
        "top_largest_test_files": [asdict(record) for record in largest_test_files],
        "duplicate_test_identifiers": duplicated_identifiers,
        "top_duplicate_clusters": [asdict(record) for record in duplicate_clusters],
        "duplicate_triage_recommendations": [
            asdict(record) for record in duplicate_triage_recommendations
        ],
        "new_duplicate_identifier_violations": duplicate_identifier_violations,
        "new_large_test_file_violations": [asdict(record) for record in large_file_violations],
    }


def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="Test suite governance audit")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path. Defaults to current directory.",
    )
    parser.add_argument(
        "--tests-root",
        default="tests",
        help="Tests root path relative to repo root. Defaults to tests.",
    )
    parser.add_argument(
        "--baseline",
        default="docs/testing-governance-baseline.json",
        help="Baseline policy JSON file path.",
    )
    parser.add_argument(
        "--output-json",
        default="reports/testing-governance-inventory.json",
        help="Output JSON path.",
    )
    parser.add_argument(
        "--output-markdown",
        default="reports/testing-governance-inventory.md",
        help="Output markdown path.",
    )
    parser.add_argument(
        "--fail-on-new-violations",
        action="store_true",
        help="Exit with code 1 when unapproved violations are found.",
    )
    return parser.parse_args()


def write_text(path: Path, content: str) -> None:
    """Write text content ensuring parent directory exists.

    Args:
        path: Target output path.
        content: Content to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    """Run governance audit and optional policy enforcement.

    Returns:
        Process exit code.
    """
    arguments = parse_arguments()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    repo_root = Path(arguments.repo_root).resolve()
    tests_root = (repo_root / arguments.tests_root).resolve()

    test_files = discover_test_files(tests_root)
    summary = build_summary(repo_root, test_files)
    records = integration_mocking_records(repo_root, test_files)
    duplicated_identifiers = duplicate_test_identifiers(repo_root, test_files)
    reclassification_candidates = identify_reclassification_candidates(records)
    largest_test_files = top_largest_test_files(repo_root, test_files)
    duplicate_clusters = top_duplicate_clusters(duplicated_identifiers)
    duplicate_triage_recommendations = triage_duplicate_identifiers(duplicated_identifiers)

    baseline = load_baseline((repo_root / arguments.baseline).resolve())
    violations = find_new_mocking_violations(records, baseline)
    duplicate_identifier_violations = find_new_duplicate_identifier_violations(
        duplicated_identifiers,
        baseline,
    )
    large_file_violations = find_new_large_file_violations(largest_test_files, baseline)

    report_md = markdown_report(
        summary,
        records,
        violations,
        reclassification_candidates,
        largest_test_files,
        duplicate_clusters,
        duplicate_triage_recommendations,
        duplicate_identifier_violations,
        large_file_violations,
    )
    report_json = build_json_payload(
        summary,
        records,
        violations,
        duplicated_identifiers,
        reclassification_candidates,
        largest_test_files,
        duplicate_clusters,
        duplicate_triage_recommendations,
        duplicate_identifier_violations,
        large_file_violations,
    )

    json_output = (repo_root / arguments.output_json).resolve()
    markdown_output = (repo_root / arguments.output_markdown).resolve()

    write_text(json_output, json.dumps(report_json, indent=2, ensure_ascii=True))
    write_text(markdown_output, report_md)

    has_new_violations = bool(
        violations or duplicate_identifier_violations or large_file_violations
    )
    if arguments.fail_on_new_violations and has_new_violations:
        logger.error("Testing governance violations found:")
        for violation in violations:
            logger.error(
                "- %s: refs=%s, tests=%s, density=%s",
                violation.path,
                violation.mock_references,
                violation.test_items,
                violation.density,
            )
        for identifier, files in duplicate_identifier_violations.items():
            logger.error("- duplicate_identifier=%s files=%s", identifier, ", ".join(files))
        for violation in large_file_violations:
            logger.error(
                "- large_test_file=%s line_count=%s test_items=%s",
                violation.path,
                violation.line_count,
                violation.test_items,
            )
        return 1

    logger.info("Governance report written to %s", json_output)
    logger.info("Governance markdown written to %s", markdown_output)
    if has_new_violations:
        logger.warning(
            "New unapproved violations: mocking=%s duplicate_identifiers=%s large_files=%s",
            len(violations),
            len(duplicate_identifier_violations),
            len(large_file_violations),
        )
    else:
        logger.info("No new unapproved violations detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
