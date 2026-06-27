"""Schema initialization, migrations, and validation."""

import logging
import os
from pathlib import Path
from typing import ClassVar

from google.api_core import exceptions as gcp_exceptions  # type: ignore[import-untyped]

from src.integrations.google_sdk_wrappers import (
    SpannerDatabaseProtocol,
    execute_dml,
    execute_sql_rows,
)

logger = logging.getLogger(__name__)

_MINIMUM_INDEX_COUNT = 3
_MINIMUM_AUDIT_INDEX_COUNT = 3


class SchemaManager:
    """Manages schema migrations and validation."""

    MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"

    @classmethod
    def get_migration_files(cls) -> list[str]:
        """Get sorted list of migration files."""
        if not cls.MIGRATIONS_DIR.exists():
            return []

        return sorted([f.name for f in cls.MIGRATIONS_DIR.glob("*.sql")])

    @staticmethod
    def _parse_sql_statements(sql: str) -> list[str]:
        """Parse SQL file content into executable statements.

        Removes line comments and splits on semicolons.

        Args:
            sql: Raw SQL file content.

        Returns:
            list[str]: Non-empty SQL statements.
        """
        uncommented_lines: list[str] = []
        for line in sql.splitlines():
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            uncommented_lines.append(line)

        cleaned_sql = "\n".join(uncommented_lines)
        return [statement.strip() for statement in cleaned_sql.split(";") if statement.strip()]

    @classmethod
    def init_schema(cls, database: SpannerDatabaseProtocol) -> None:
        """Initialize schema by running migrations in order.

        Args:
            database: Spanner database instance

        Raises:
            RuntimeError: If migration fails
        """
        migration_files = cls.get_migration_files()

        if not migration_files:
            msg = f"No migration files found in {cls.MIGRATIONS_DIR}"
            raise RuntimeError(msg)

        for migration_file in migration_files:
            migration_path = cls.MIGRATIONS_DIR / migration_file
            with open(migration_path) as f:
                sql = f.read()

            statements = cls._parse_sql_statements(sql)
            if os.getenv("SPANNER_EMULATOR_HOST"):
                statements = [
                    statement
                    for statement in statements
                    if "PROPERTY GRAPH" not in statement.upper()
                ]
            if not statements:
                logger.warning(
                    "Skipping migration with no executable statements: %s", migration_file
                )
                continue

            try:
                operation = database.update_ddl(ddl_statements=statements)
                operation.result()
            except (gcp_exceptions.GoogleAPICallError, gcp_exceptions.RetryError) as error:
                error_text = str(error).lower()
                if "already exists" in error_text or "duplicate" in error_text:
                    logger.info("Skipping already-applied migration: %s", migration_file)
                    continue
                msg = f"Failed to apply migration {migration_file}: {error}"
                raise RuntimeError(msg) from error

    @classmethod
    def validate_schema(cls, database: SpannerDatabaseProtocol) -> dict[str, bool]:
        """Validate that the expected schema exists.

        Args:
            database: Spanner database instance

        Returns:
            Dictionary with validation results
        """
        validation_results = {
            "memory_node_exists": False,
            "memory_edge_exists": False,
            "audit_events_exists": False,
            "property_graph_exists": False,
            "indexes_exist": False,
            "audit_indexes_exist": False,
        }

        # Check if MemoryNode table exists
        try:
            columns = execute_sql_rows(
                database,
                "SELECT column_name"
                " FROM information_schema.columns"
                " WHERE table_name = 'MemoryNode'",
            )
            if columns:
                validation_results["memory_node_exists"] = True
        except Exception:  # noqa: BLE001
            logger.debug("Error checking MemoryNode table", exc_info=True)

        # Check if MemoryEdge table exists
        try:
            columns = execute_sql_rows(
                database,
                "SELECT column_name"
                " FROM information_schema.columns"
                " WHERE table_name = 'MemoryEdge'",
            )
            if columns:
                validation_results["memory_edge_exists"] = True
        except Exception:  # noqa: BLE001
            logger.debug("Error checking MemoryEdge table", exc_info=True)

        # Check if property graph exists
        try:
            results = execute_sql_rows(
                database,
                "SELECT property_graph_name"
                " FROM information_schema.property_graphs"
                " WHERE property_graph_name = 'AgentMemoryGraph'",
            )
            if results:
                validation_results["property_graph_exists"] = True
        except Exception:  # noqa: BLE001
            logger.debug("Error checking property graph", exc_info=True)

        # Check if AUDIT_EVENTS table exists
        try:
            results = execute_sql_rows(
                database,
                "SELECT column_name"
                " FROM information_schema.columns"
                " WHERE table_name = 'AUDIT_EVENTS'",
            )
            if results:
                validation_results["audit_events_exists"] = True
        except Exception:  # noqa: BLE001
            logger.debug("Error checking AUDIT_EVENTS table", exc_info=True)

        # Check if indexes exist
        try:
            indexes = execute_sql_rows(
                database,
                "SELECT index_name"
                " FROM information_schema.statistics"
                " WHERE table_name IN ('MemoryNode', 'MemoryEdge')",
            )
            if len(indexes) >= _MINIMUM_INDEX_COUNT:  # We expect at least 3 indexes
                validation_results["indexes_exist"] = True
        except Exception:  # noqa: BLE001
            logger.debug("Error checking indexes", exc_info=True)

        # Check if audit indexes exist
        try:
            results = execute_sql_rows(
                database,
                "SELECT index_name"
                " FROM information_schema.statistics"
                " WHERE table_name = 'AUDIT_EVENTS'",
            )
            if len(results) >= _MINIMUM_AUDIT_INDEX_COUNT:
                validation_results["audit_indexes_exist"] = True
        except Exception:  # noqa: BLE001
            logger.debug("Error checking audit indexes", exc_info=True)

        return validation_results

    @classmethod
    def reset_schema_for_testing(cls, database: SpannerDatabaseProtocol) -> None:
        """Reset schema for testing (truncate all tables).

        WARNING: This destroys all data!

        Args:
            database: Spanner database instance
        """
        tables = ["MemoryEdge", "MemoryNode"]

        for table in tables:
            try:
                execute_dml(database, f"DELETE FROM {table} WHERE true", {})  # noqa: S608
            except Exception:  # noqa: BLE001
                logger.debug("Error truncating %s", table, exc_info=True)


class SchemaConfig:
    """Configuration for schema and memory topology."""

    # Memory Tiers (immutable)
    MEMORY_TIER_CONTEXT = "CONTEXT"
    MEMORY_TIER_SEMANTIC = "SEMANTIC"
    MEMORY_TIER_AUDIT = "AUDIT"
    VALID_MEMORY_TIERS: ClassVar[set[str]] = {
        MEMORY_TIER_CONTEXT,
        MEMORY_TIER_SEMANTIC,
        MEMORY_TIER_AUDIT,
    }
    AUDIT_TABLE_NAME = "AUDIT_EVENTS"
    AUDIT_ALLOWED_OPERATIONS: ClassVar[set[str]] = {"INSERT"}

    # POLE+O Entity Types
    ENTITY_TYPE_PERSON = "PERSON"
    ENTITY_TYPE_OBJECT = "OBJECT"
    ENTITY_TYPE_LOCATION = "LOCATION"
    ENTITY_TYPE_EVENT = "EVENT"
    ENTITY_TYPE_ORGANIZATION = "ORGANIZATION"
    VALID_ENTITY_TYPES: ClassVar[set[str]] = {
        ENTITY_TYPE_PERSON,
        ENTITY_TYPE_OBJECT,
        ENTITY_TYPE_LOCATION,
        ENTITY_TYPE_EVENT,
        ENTITY_TYPE_ORGANIZATION,
    }

    # Cognitive Weighting Defaults
    INITIAL_WEIGHT = 0.50
    BAYES_FACTOR_SUCCESS = 1.25  # ln(1.25) ≈ 0.223
    TEMPORAL_DECAY_RATE = 0.05  # 5% per 24 hours
    WEIGHT_THRESHOLD = 0.30  # Minimum weight for inclusion in retrieval horizon

    # Common Relationship Types
    RELATIONSHIP_HAS_TURN = "HAS_TURN"
    RELATIONSHIP_FOLLOWED_BY = "FOLLOWED_BY"
    RELATIONSHIP_REFERENCES = "REFERENCES"
    RELATIONSHIP_BELONGS_TO = "BELONGS_TO"
    RELATIONSHIP_MANAGES = "MANAGES"
    RELATIONSHIP_DEPENDS_ON = "DEPENDS_ON"
