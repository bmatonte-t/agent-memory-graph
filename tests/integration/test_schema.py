"""Integration tests for Spanner schema design."""

import pytest

from src.db.schema import SchemaConfig, SchemaManager


@pytest.mark.integration
class TestSchemaDesign:
    """Tests for Spanner schema structure and design."""

    def test_schema_manager_finds_migrations(self):
        """Test that SchemaManager finds migration files."""
        migrations = SchemaManager.get_migration_files()
        assert len(migrations) >= 3, "Expected at least 3 migration files"
        assert "001_memory_node_table.sql" in migrations
        assert "002_memory_edge_table.sql" in migrations
        assert "003_property_graph.sql" in migrations

    def test_schema_config_valid_memory_tiers(self):
        """Test that SchemaConfig defines all memory tiers."""
        assert "CONTEXT" in SchemaConfig.VALID_MEMORY_TIERS
        assert "SEMANTIC" in SchemaConfig.VALID_MEMORY_TIERS
        assert "AUDIT" in SchemaConfig.VALID_MEMORY_TIERS
        assert len(SchemaConfig.VALID_MEMORY_TIERS) == 3

    def test_schema_config_valid_entity_types(self):
        """Test that SchemaConfig defines all POLE+O entity types."""
        assert "PERSON" in SchemaConfig.VALID_ENTITY_TYPES
        assert "OBJECT" in SchemaConfig.VALID_ENTITY_TYPES
        assert "LOCATION" in SchemaConfig.VALID_ENTITY_TYPES
        assert "EVENT" in SchemaConfig.VALID_ENTITY_TYPES
        assert "ORGANIZATION" in SchemaConfig.VALID_ENTITY_TYPES
        assert len(SchemaConfig.VALID_ENTITY_TYPES) == 5

    def test_schema_config_cognitive_weight_defaults(self):
        """Test that cognitive weight configuration is correct."""
        # Bayesian log-odds: successful use should increment weight
        assert SchemaConfig.INITIAL_WEIGHT == 0.50
        assert SchemaConfig.BAYES_FACTOR_SUCCESS == 1.25
        assert SchemaConfig.TEMPORAL_DECAY_RATE == 0.05
        assert SchemaConfig.WEIGHT_THRESHOLD == 0.30

    def test_schema_config_relationship_types(self):
        """Test that common relationship types are defined."""
        assert SchemaConfig.RELATIONSHIP_HAS_TURN is not None
        assert SchemaConfig.RELATIONSHIP_FOLLOWED_BY is not None
        assert SchemaConfig.RELATIONSHIP_REFERENCES is not None
        assert SchemaConfig.RELATIONSHIP_BELONGS_TO is not None
        assert SchemaConfig.RELATIONSHIP_MANAGES is not None
        assert SchemaConfig.RELATIONSHIP_DEPENDS_ON is not None

    def test_migration_files_have_correct_names(self):
        """Test that migration files follow naming convention."""
        migrations = SchemaManager.get_migration_files()
        for migration in migrations:
            # Should be formatted as NNN_description.sql
            assert migration.endswith(".sql")
            assert migration[0:3].isdigit()
            assert migration[3] == "_"

    def test_memory_node_table_migration_is_first(self):
        """Test that MemoryNode table is created first."""
        migrations = SchemaManager.get_migration_files()
        assert migrations[0] == "001_memory_node_table.sql"

    def test_memory_edge_table_migration_is_second(self):
        """Test that MemoryEdge table is created second (depends on MemoryNode)."""
        migrations = SchemaManager.get_migration_files()
        assert migrations[1] == "002_memory_edge_table.sql"

    def test_property_graph_migration_is_third(self):
        """Test that property graph is created third."""
        migrations = SchemaManager.get_migration_files()
        assert migrations[2] == "003_property_graph.sql"
