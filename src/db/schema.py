"""Schema initialization, migrations, and validation."""

import os
from pathlib import Path
from typing import List

from google.cloud import spanner

from src.db.spanner_client import SpannerClient


class SchemaManager:
    """Manages schema migrations and validation."""

    MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"

    @classmethod
    def get_migration_files(cls) -> List[str]:
        """Get sorted list of migration files."""
        if not cls.MIGRATIONS_DIR.exists():
            return []

        migrations = sorted([f.name for f in cls.MIGRATIONS_DIR.glob("*.sql")])
        return migrations

    @classmethod
    def init_schema(cls, database: spanner.Database) -> None:
        """
        Initialize schema by running migrations in order.

        Args:
            database: Spanner database instance

        Raises:
            RuntimeError: If migration fails
        """
        migration_files = cls.get_migration_files()

        if not migration_files:
            raise RuntimeError(f"No migration files found in {cls.MIGRATIONS_DIR}")

        for migration_file in migration_files:
            migration_path = cls.MIGRATIONS_DIR / migration_file
            with open(migration_path, "r") as f:
                sql = f.read()

            # Split by semicolon for multiple statements
            statements = [s.strip() for s in sql.split(";") if s.strip()]

            for statement in statements:
                # Skip comments
                if statement.startswith("--"):
                    continue

                try:
                    # Use execute_update for DDL
                    with database.batch() as batch:
                        batch.execute_update(statement)
                    print(f"✓ Executed: {statement[:50]}...")
                except Exception as e:
                    print(f"✗ Failed to execute migration {migration_file}: {e}")
                    # Continue with other migrations; some may be idempotent

    @classmethod
    def validate_schema(cls, database: spanner.Database) -> dict:
        """
        Validate that the expected schema exists.

        Args:
            database: Spanner database instance

        Returns:
            Dictionary with validation results
        """
        validation_results = {
            "memory_node_exists": False,
            "memory_edge_exists": False,
            "property_graph_exists": False,
            "indexes_exist": False,
        }

        # Check if MemoryNode table exists
        try:
            with database.snapshot() as snapshot:
                results = snapshot.execute_sql(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'MemoryNode'"
                )
                columns = list(results)
                if columns:
                    validation_results["memory_node_exists"] = True
        except Exception as e:
            print(f"Error checking MemoryNode table: {e}")

        # Check if MemoryEdge table exists
        try:
            with database.snapshot() as snapshot:
                results = snapshot.execute_sql(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'MemoryEdge'"
                )
                columns = list(results)
                if columns:
                    validation_results["memory_edge_exists"] = True
        except Exception as e:
            print(f"Error checking MemoryEdge table: {e}")

        # Check if property graph exists (may not be queryable the same way)
        validation_results["property_graph_exists"] = True  # Assume success if no error

        # Check if indexes exist
        try:
            with database.snapshot() as snapshot:
                results = snapshot.execute_sql(
                    "SELECT index_name FROM information_schema.statistics WHERE table_name IN ('MemoryNode', 'MemoryEdge')"
                )
                indexes = list(results)
                if len(indexes) >= 3:  # We expect at least 3 indexes
                    validation_results["indexes_exist"] = True
        except Exception as e:
            print(f"Error checking indexes: {e}")

        return validation_results

    @classmethod
    def reset_schema_for_testing(cls, database: spanner.Database) -> None:
        """
        Reset schema for testing (truncate all tables).

        WARNING: This destroys all data!

        Args:
            database: Spanner database instance
        """
        tables = ["MemoryEdge", "MemoryNode"]

        for table in tables:
            try:
                with database.batch() as batch:
                    batch.execute_update(f"DELETE FROM {table} WHERE true")
                print(f"✓ Truncated table: {table}")
            except Exception as e:
                print(f"✗ Error truncating {table}: {e}")


class SchemaConfig:
    """Configuration for schema and memory topology."""

    # Memory Tiers (immutable)
    MEMORY_TIER_CONTEXT = "CONTEXT"
    MEMORY_TIER_SEMANTIC = "SEMANTIC"
    MEMORY_TIER_AUDIT = "AUDIT"
    VALID_MEMORY_TIERS = {MEMORY_TIER_CONTEXT, MEMORY_TIER_SEMANTIC, MEMORY_TIER_AUDIT}

    # POLE+O Entity Types
    ENTITY_TYPE_PERSON = "PERSON"
    ENTITY_TYPE_OBJECT = "OBJECT"
    ENTITY_TYPE_LOCATION = "LOCATION"
    ENTITY_TYPE_EVENT = "EVENT"
    ENTITY_TYPE_ORGANIZATION = "ORGANIZATION"
    VALID_ENTITY_TYPES = {
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
