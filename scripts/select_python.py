# /// script
# requires-python = ">=3.14"
# ///

# ruff: noqa: T201 this is a CLI tool so print statements are intentional.

import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta
from typing import Any, TypedDict

# ANSI Colors
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"
RELEASE_CYCLE_URL = "https://peps.python.org/api/release-cycle.json"

# * In general, we must print informational messages to stderr so that the version string is the
# * only thing printed to stdout for easy shell capturing.


class VersionInfo(TypedDict):
    """Schema of data returned by the Python release cycle API."""

    branch: str
    pep: int
    status: str
    first_release: str
    end_of_life: str
    release_manager: str


class AugmentedVersionInfo(VersionInfo):
    """Same as VersionInfo but with a position."""

    position: int  # Position in the sorted non-end-of-life list, added for convenience


type ReleaseCycleData = dict[str, VersionInfo]
type AugmentedReleaseCycleData = dict[str, AugmentedVersionInfo]


def version_key(version: str) -> list[int]:
    """Convert a version string like "3.10.5" into a list of integers [3, 10, 5] for sorting."""
    return list(map(int, version.split(".")))


def eprint(*args: Any, **kwargs: Any) -> None:
    """Helper to print to stderr so stdout remains clean for shell capturing."""
    print(*args, file=sys.stderr, **kwargs)


def fetch_release_cycle_data() -> ReleaseCycleData:
    """Fetch Python release cycle data from the official PEPs API.

    Returns:
        Parsed release cycle data keyed by version string.

    Raises:
        SystemExit: If the request fails or the response is not valid JSON.
    """
    try:
        with urllib.request.urlopen(RELEASE_CYCLE_URL, timeout=10) as response:  # noqa: S310
            return json.loads(response.read().decode())
    except urllib.error.URLError as error:
        eprint(f"❌ Error: Could not fetch release cycle data from {RELEASE_CYCLE_URL}: {error}")
        sys.exit(1)
    except json.JSONDecodeError as error:
        eprint(f"❌ Error: Invalid JSON response from {RELEASE_CYCLE_URL}: {error}")
        sys.exit(1)


def truthy(value: str) -> bool:
    """Determine if a string value is truthy (e.g., "yes", "y", "true", "1").

    Empty is falsy.

    Args:
        value: The input string to evaluate.

    Returns:
        bool: True if the input is considered truthy, False otherwise.
    """
    return value.strip().lower() in {"yes", "y", "true", "1"}


class PythonVersionSelector:
    """Interactive selector that picks a Python version based on release cycle data."""

    def __init__(self) -> None:
        self._data: ReleaseCycleData = fetch_release_cycle_data()
        self._non_end_of_life: AugmentedReleaseCycleData = self._build_non_end_of_life()
        self._default_version: str = self._find_default_version()
        self._chosen: str = ""

    @property
    def _chosen_metadata(self) -> VersionInfo:
        """Metadata for the currently selected version."""
        return self._data[self._chosen]

    def _build_non_end_of_life(self) -> AugmentedReleaseCycleData:
        """Build a sorted mapping of non-end-of-life versions augmented with their rank position.

        Returns:
            AugmentedReleaseCycleData: Versions sorted newest-first, each annotated with
                a `position` index (0 = newest).
        """
        active_versions = sorted(
            [(v, info) for v, info in self._data.items() if info.get("status") != "end-of-life"],
            key=lambda x: version_key(x[0]),
            reverse=True,
        )
        return {v: {**info, "position": idx} for idx, (v, info) in enumerate(active_versions)}

    def _find_default_version(self) -> str:
        """Return the latest bugfix-status version to use as the recommendation.

        Returns:
            str: The recommended Python version string.

        Raises:
            RuntimeError: If no bugfix versions are present in the release cycle data.
        """
        # non_end_of_life is already sorted newest-first, so the first bugfix entry is the latest.
        bugfix_versions = [
            version
            for version, info in self._non_end_of_life.items()
            if info.get("status") == "bugfix"
        ]
        if not bugfix_versions:
            message = "No bugfix versions found in data."
            raise RuntimeError(message)
        # Pick latest bugfix (released) version; feature/pre-release aren't publicly available yet.
        return bugfix_versions[0]

    def _prompt_user_version(self) -> str:
        """Ask the user for the version they want to use.

        Returns:
            str: The version string entered by the user, or `self._default_version` if left blank.
        """
        sys.stderr.write(f"Enter Python version [{self._default_version}]: ")
        sys.stderr.flush()
        try:
            chosen = input() or self._default_version
        except EOFError as eof:
            message = "No input received. Please run the script in an interactive terminal."
            raise RuntimeError(message) from eof

        if not chosen:
            message = "No version entered and no default available."
            raise RuntimeError(message)

        return chosen

    def _ask_use_chosen(self) -> bool:
        """Warn the user that `_chosen` is not the latest and ask whether to keep it.

        Returns:
            bool: True if the user confirms they want to keep `self._chosen`, False to switch to
                `self._default_version`.
        """
        n_versions_old = (
            self._non_end_of_life[self._chosen]["position"]
            - self._non_end_of_life[self._default_version]["position"]
        )

        chosen_released_at = date.strptime(self._chosen_metadata["first_release"], "%Y-%m-%d")
        today = datetime.now(tz=UTC).date()
        days_old = round((today - chosen_released_at) / timedelta(days=1), 1)

        end_of_life = self._chosen_metadata["end_of_life"]
        status = self._chosen_metadata["status"]

        versions_relative = (
            f"{abs(n_versions_old)} version(s) ahead of"
            if n_versions_old < 0
            else f"{n_versions_old} version(s) behind"
        )
        eprint(
            f"\n{YELLOW}The latest stable version is {self._default_version}. You're starting "
            f"with version {self._chosen}, which is {versions_relative} the latest stable "
            f"version, {days_old} day(s) old, will lose support in {end_of_life} and is "
            f"currently in {status} status.{NC}\n"
        )

        sys.stderr.write(
            f"Are you sure you want to use version {self._chosen}? Saying YES uses version "
            f"{self._chosen}, while saying NO uses version {self._default_version} (y/N): "
        )
        sys.stderr.flush()
        return truthy(input())

    def _reconfirm_chosen(self) -> bool:
        """Warn the user about the non-bugfix status of `_chosen` and ask them to reconfirm.

        Returns:
            bool: True if the user still wants `self._chosen`, False to switch to
                `self._default_version`.
        """
        status: str = self._chosen_metadata["status"]

        # Bugfix versions are fully supported; the yellow warning in _ask_use_chosen is sufficient.
        if status == "bugfix":
            return True

        eprint(
            f"\n{RED}This version is in {status} status. Unless you have good reason to use a "
            "non-latest version, it's recommended to use the latest version for better support, "
            f"performance and security updates.{NC}"
        )

        sys.stderr.write(
            f"Are you absolutely sure you want to proceed with version {self._chosen}? Saying "
            f"YES uses version {self._chosen}, while saying NO uses version "
            f"{self._default_version} (y/N): "
        )
        sys.stderr.flush()
        return truthy(input())

    def _final_output(self) -> None:
        """Print a small summary of the chosen version to `stderr`."""
        status = self._chosen_metadata["status"]
        eprint(f"\n✅ Python version selected: {self._chosen}")
        eprint(f"   Status:        {status}")
        eprint(f"   First release: {self._chosen_metadata.get('first_release', 'unknown')}")
        eprint(f"   End of life:   {self._chosen_metadata.get('end_of_life', 'unknown')}\n")

    def run(self) -> None:
        """Run the interactive version selection flow and print the result to `stdout`."""
        try:
            self._chosen = self._prompt_user_version()
        except RuntimeError as error:
            eprint(f"❌ Error: {error}")
            sys.exit(1)

        if self._chosen not in self._data:
            eprint(f"⚠️  Version {self._chosen} not found in official data. Proceeding anyway.")
            print(self._chosen)  # Output version for shell capture
            sys.exit(0)

        if self._chosen != self._default_version:
            use_chosen = self._ask_use_chosen()
            if not use_chosen or not self._reconfirm_chosen():
                self._chosen = self._default_version

        self._final_output()

        # The last thing printed is the version string for the shell to capture
        print(self._chosen)


if __name__ == "__main__":
    PythonVersionSelector().run()
