"""Generate a unified testing health dashboard from governance artifacts.

The dashboard consolidates key governance and quality indicators into a single
markdown artifact consumed by docs and review workflows.
"""

from __future__ import annotations

import json
from pathlib import Path


def _load_governance_inventory(inventory_path: Path) -> dict[str, object]:
    """Load governance inventory JSON payload.

    Args:
        inventory_path: Path to governance inventory JSON artifact.

    Returns:
        Parsed JSON payload.
    """
    return json.loads(inventory_path.read_text(encoding="utf-8"))


def _render_dashboard(payload: dict[str, object]) -> str:
    """Render a markdown dashboard from governance payload.

    Args:
        payload: Governance inventory payload.

    Returns:
        Markdown dashboard content.
    """
    summary = payload.get("summary", {})
    top_largest_test_files = payload.get("top_largest_test_files", [])
    top_duplicate_clusters = payload.get("top_duplicate_clusters", [])
    new_policy_violations = payload.get("new_policy_violations", [])
    duplicate_identifier_violations = payload.get(
        "new_duplicate_identifier_violations",
        {},
    )
    large_test_file_violations = payload.get("new_large_test_file_violations", [])

    lines: list[str] = [
        "# Testing Health Dashboard",
        "",
        "## Core Metrics",
        "",
        f"- total_test_files: {summary.get('total_test_files', 0)}",
        f"- total_test_items: {summary.get('total_test_items', 0)}",
        f"- integration_test_files: {summary.get('integration_test_files', 0)}",
        f"- integration_mock_references: {summary.get('integration_mock_references', 0)}",
        (
            "- integration_mock_density_average: "
            f"{summary.get('integration_mock_density_average', 0.0)}"
        ),
        f"- duplicate_test_identifiers: {summary.get('duplicate_test_identifiers', 0)}",
        "",
        "## Governance Status",
        "",
        f"- new_policy_violations: {len(new_policy_violations)}",
        (f"- new_duplicate_identifier_violations: {len(duplicate_identifier_violations)}"),
        f"- new_large_test_file_violations: {len(large_test_file_violations)}",
        "",
        "## Largest Test File Hotspots",
        "",
        "| file | line_count | test_items | lines_per_test_item |",
        "|---|---:|---:|---:|",
    ]

    if top_largest_test_files:

        def _ratio(item: dict[str, object]) -> float:
            """Compute line-count concentration ratio for one file."""
            line_count = int(item.get("line_count", 0))
            test_items = int(item.get("test_items", 0))
            return round(line_count / max(1, test_items), 2)

        lines.extend(
            [
                "| "
                f"{item.get('path', 'n/a')} | "
                f"{item.get('line_count', 0)} | "
                f"{item.get('test_items', 0)} | "
                f"{_ratio(item)} |"
                for item in top_largest_test_files
            ]
        )
    else:
        lines.append("| none | 0 | 0 | 0 |")

    lines.extend(
        [
            "",
            "## Duplicate Cluster Hotspots",
            "",
            "| identifier | cluster_size |",
            "|---|---:|",
        ]
    )

    if top_duplicate_clusters:
        lines.extend(
            [
                f"| {item.get('identifier', 'n/a')} | {item.get('cluster_size', 0)} |"
                for item in top_duplicate_clusters
            ]
        )
    else:
        lines.append("| none | 0 |")

    lines.extend(
        [
            "",
            "## Governance Cadence",
            "",
            "- Weekly: `just test-governance-audit` and `just test-health-dashboard`.",
            (
                "- Monthly: update `reports/escaped-defects-log.md` with escaped defects "
                "and coverage gaps."
            ),
            "- Quarterly: refresh ownership and risks in `docs/testing-capability-matrix.md`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    """Generate and persist testing health dashboard markdown artifact.

    Returns:
        Process exit code.
    """
    repo_root = Path(__file__).resolve().parent.parent
    inventory_path = repo_root / "reports" / "testing-governance-inventory.json"
    output_path = repo_root / "reports" / "testing-health-dashboard.md"

    payload = _load_governance_inventory(inventory_path)
    dashboard = _render_dashboard(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(dashboard, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
