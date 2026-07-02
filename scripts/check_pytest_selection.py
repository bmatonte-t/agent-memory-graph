"""Validate marker-based gate selection cardinality.

This script prevents silent gate drift where marker expressions select too few
(or zero) tests, which can create false confidence in CI.
"""

from __future__ import annotations

import argparse
import logging
import re
import subprocess
from dataclasses import dataclass

SUMMARY_PATTERN = re.compile(
    r"(?P<selected>\d+)\/(?P<total>\d+) tests collected(?: \((?P<deselected>\d+) deselected\))?"
)
logger = logging.getLogger(__name__)


class SelectionCheckError(RuntimeError):
    """Raised when pytest selection output cannot be parsed or validated."""


@dataclass(frozen=True, slots=True)
class SelectionCounts:
    """Selected vs total test counts from pytest collect output.

    Attributes:
        selected: Number of tests selected by the marker expression.
        total: Total number of discovered tests.
        deselected: Number of deselected tests. Defaults to 0.
    """

    selected: int
    total: int
    deselected: int = 0


def parse_selection_counts(output: str) -> SelectionCounts:
    """Parse pytest collect-only summary and return selection counts.

    Args:
        output: Combined stdout and stderr from pytest collect-only run.

    Returns:
        SelectionCounts: Parsed selected/total/deselected values.

    Raises:
        SelectionCheckError: If summary line is missing or malformed.
    """
    match: re.Match[str] | None = None
    for line in output.splitlines():
        candidate = SUMMARY_PATTERN.search(line)
        if candidate is not None:
            match = candidate

    if match is None:
        msg = (
            "Could not parse pytest selection summary. "
            "Expected a line like '5/889 tests collected (884 deselected)'."
        )
        raise SelectionCheckError(msg)

    selected = int(match.group("selected"))
    total = int(match.group("total"))
    deselected_group = match.group("deselected")
    deselected = int(deselected_group) if deselected_group is not None else 0
    return SelectionCounts(selected=selected, total=total, deselected=deselected)


def run_selection_check(marker_expression: str, min_selected: int, gate_name: str) -> None:
    """Execute pytest collection and enforce minimum selected tests.

    Args:
        marker_expression: Pytest marker expression passed to -m.
        min_selected: Minimum number of selected tests required to pass.
        gate_name: Human-friendly gate name for logs.

    Raises:
        SelectionCheckError: If pytest fails or selection is below threshold.
    """
    command = ["pytest", "--collect-only", "-q", "-m", marker_expression]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    output = "\n".join(part for part in [result.stdout, result.stderr] if part)

    if result.returncode != 0:
        msg = (
            f"{gate_name}: pytest collection failed with exit code {result.returncode}.\n"
            f"Command: {' '.join(command)}\n"
            f"Output:\n{output}"
        )
        raise SelectionCheckError(msg)

    counts = parse_selection_counts(output)
    logger.info(
        "%s selection: %d selected out of %d total (%d deselected)",
        gate_name,
        counts.selected,
        counts.total,
        counts.deselected,
    )

    if counts.selected < min_selected:
        msg = (
            f"{gate_name}: selected {counts.selected} tests, below minimum {min_selected}. "
            f"Marker expression: {marker_expression}"
        )
        raise SelectionCheckError(msg)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for gate selection enforcement.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Enforce minimum test selection for marker gates")
    parser.add_argument(
        "--marker-expression",
        required=True,
        help="Pytest marker expression passed to '-m'.",
    )
    parser.add_argument(
        "--min-selected",
        required=True,
        type=int,
        help="Minimum selected tests required for this gate.",
    )
    parser.add_argument(
        "--gate-name",
        required=True,
        help="Human-friendly name for the gate.",
    )
    return parser.parse_args()


def main() -> None:
    """Run selection threshold enforcement for one marker gate."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    arguments = parse_args()
    run_selection_check(
        marker_expression=arguments.marker_expression,
        min_selected=arguments.min_selected,
        gate_name=arguments.gate_name,
    )


if __name__ == "__main__":
    main()
