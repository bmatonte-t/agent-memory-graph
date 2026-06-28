"""Integration tests for Spanner schema design."""

from typing import TYPE_CHECKING

import pytest

from src.db.schema import SchemaConfig, SchemaManager

if TYPE_CHECKING:
    from pathlib import Path

MIN_MIGRATION_FILES = 3
MEMORY_TIER_COUNT = 3
ENTITY_TYPE_COUNT = 5
EXPECTED_INITIAL_WEIGHT = 0.50
EXPECTED_BAYES_FACTOR = 1.25
EXPECTED_DECAY_RATE = 0.05
EXPECTED_WEIGHT_THRESHOLD = 0.30
EXPECTED_PARSED_STATEMENTS = 2


@pytest.mark.integration
class TestSchemaDesign:
    """Tests for Spanner schema structure and design."""

    def test_schema_manager_finds_migrations(self) -> None:
        """Test that SchemaManager finds migration files."""
        migrations = SchemaManager.get_migration_files()
        assert len(migrations) >= MIN_MIGRATION_FILES, "Expected at least 3 migration files"
        assert "001_memory_node_table.sql" in migrations
        assert "002_memory_edge_table.sql" in migrations
        assert "003_property_graph.sql" in migrations

    def test_schema_config_valid_memory_tiers(self) -> None:
        """Test that SchemaConfig defines all memory tiers."""
        assert "CONTEXT" in SchemaConfig.VALID_MEMORY_TIERS
        assert "SEMANTIC" in SchemaConfig.VALID_MEMORY_TIERS
        assert "AUDIT" in SchemaConfig.VALID_MEMORY_TIERS
        assert len(SchemaConfig.VALID_MEMORY_TIERS) == MEMORY_TIER_COUNT

    def test_schema_config_valid_entity_types(self) -> None:
        """Test that SchemaConfig defines all POLE+O entity types."""
        assert "PERSON" in SchemaConfig.VALID_ENTITY_TYPES
        assert "OBJECT" in SchemaConfig.VALID_ENTITY_TYPES
        assert "LOCATION" in SchemaConfig.VALID_ENTITY_TYPES
        assert "EVENT" in SchemaConfig.VALID_ENTITY_TYPES
        assert "ORGANIZATION" in SchemaConfig.VALID_ENTITY_TYPES
        assert len(SchemaConfig.VALID_ENTITY_TYPES) == ENTITY_TYPE_COUNT

    def test_schema_config_cognitive_weight_defaults(self) -> None:
        """Test that cognitive weight configuration is correct."""
        # Bayesian log-odds: successful use should increment weight
        assert SchemaConfig.INITIAL_WEIGHT == EXPECTED_INITIAL_WEIGHT
        assert SchemaConfig.BAYES_FACTOR_SUCCESS == EXPECTED_BAYES_FACTOR
        assert SchemaConfig.TEMPORAL_DECAY_RATE == EXPECTED_DECAY_RATE
        assert SchemaConfig.WEIGHT_THRESHOLD == EXPECTED_WEIGHT_THRESHOLD

    def test_schema_config_relationship_types(self) -> None:
        """Test that common relationship types are defined."""
        assert SchemaConfig.RELATIONSHIP_HAS_TURN is not None
        assert SchemaConfig.RELATIONSHIP_FOLLOWED_BY is not None
        assert SchemaConfig.RELATIONSHIP_REFERENCES is not None
        assert SchemaConfig.RELATIONSHIP_BELONGS_TO is not None
        assert SchemaConfig.RELATIONSHIP_MANAGES is not None
        assert SchemaConfig.RELATIONSHIP_DEPENDS_ON is not None

    def test_migration_files_have_correct_names(self) -> None:
        """Test that migration files follow naming convention."""
        migrations = SchemaManager.get_migration_files()
        for migration in migrations:
            # Should be formatted as NNN_description.sql
            assert migration.endswith(".sql")
            assert migration[0:3].isdigit()
            assert migration[3] == "_"

    def test_memory_node_table_migration_is_first(self) -> None:
        """Test that MemoryNode table is created first."""
        migrations = SchemaManager.get_migration_files()
        assert migrations[0] == "001_memory_node_table.sql"

    def test_memory_edge_table_migration_is_second(self) -> None:
        """Test that MemoryEdge table is created second (depends on MemoryNode)."""
        migrations = SchemaManager.get_migration_files()
        assert migrations[1] == "002_memory_edge_table.sql"

    def test_property_graph_migration_is_third(self) -> None:
        """Test that property graph is created third."""
        migrations = SchemaManager.get_migration_files()
        assert migrations[2] == "003_property_graph.sql"


class TestSchemaExecution:
    """Tests for schema migration execution mechanics."""

    def test_parse_sql_statements_strips_comments(self) -> None:
        """Parser should drop full-line comments and preserve executable statements."""
        sql = """
        -- migration comment
        CREATE TABLE Demo (Id STRING(10) NOT NULL) PRIMARY KEY (Id);

        -- index comment
        CREATE INDEX idx_demo_id ON Demo (Id);
        """

        statements = SchemaManager._parse_sql_statements(sql)

        assert len(statements) == EXPECTED_PARSED_STATEMENTS
        assert statements[0].startswith("CREATE TABLE")
        assert statements[1].startswith("CREATE INDEX")

    def test_init_schema_uses_update_ddl(self, tmp_path: Path) -> None:
        """Schema initialization should execute migrations via update_ddl."""
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        (migrations_dir / "001_test.sql").write_text(
            "CREATE TABLE Demo (Id STRING(10) NOT NULL) PRIMARY KEY (Id);",
            encoding="utf-8",
        )

        class FakeOperation:
            def result(self) -> None:
                return None

        class FakeDatabase:
            def __init__(self) -> None:
                self.statements: list[list[str]] = []

            def update_ddl(self, *, ddl_statements: list[str]) -> FakeOperation:
                self.statements.append(ddl_statements)
                return FakeOperation()

        fake_database = FakeDatabase()
        original_dir = SchemaManager.MIGRATIONS_DIR
        SchemaManager.MIGRATIONS_DIR = migrations_dir
        try:
            SchemaManager.init_schema(fake_database)  # type: ignore[arg-type]
        finally:
            SchemaManager.MIGRATIONS_DIR = original_dir

        assert fake_database.statements == [
            ["CREATE TABLE Demo (Id STRING(10) NOT NULL) PRIMARY KEY (Id)"]
        ]
