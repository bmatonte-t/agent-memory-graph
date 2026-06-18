"""Unit tests for shared security validators."""

from __future__ import annotations

from typing import Any

import pytest

from src.security.validators import (
    validate_entity_type,
    validate_mapping,
    validate_relationship,
    validate_required_string,
    validate_tenant_id,
    validate_window_size,
)


class TestSecurityValidators:
    """Behavioral tests for input validator helpers."""

    def test_validate_tenant_id_returns_normalized_value(self) -> None:
        """Tenant validator should trim surrounding whitespace."""
        assert validate_tenant_id("  tenant_a  ") == "tenant_a"

    def test_validate_tenant_id_rejects_blank(self) -> None:
        """Tenant validator should fail on blank identifiers."""
        with pytest.raises(ValueError, match="tenant_id cannot be blank"):
            validate_tenant_id("   ")

    def test_validate_required_string_rejects_none(self) -> None:
        """Required string validator should reject missing values."""
        with pytest.raises(ValueError, match="session_id must be a non-empty string"):
            validate_required_string(None, field_name="session_id")

    def test_validate_mapping_rejects_non_object(self) -> None:
        """Mapping validator should reject scalar values."""
        with pytest.raises(ValueError, match="attributes must be an object"):
            validate_mapping("not-a-dict", field_name="attributes")

    def test_validate_window_size_rejects_out_of_range(self) -> None:
        """Window-size validator should enforce configured bounds."""
        with pytest.raises(ValueError, match="window_size must be between 1 and 100"):
            validate_window_size(101)

    def test_validate_entity_type_rejects_invalid_value(self) -> None:
        """Entity-type validator should reject values outside allowed set."""
        with pytest.raises(ValueError, match="Invalid entity_type"):
            validate_entity_type("INVALID", allowed_entity_types={"PERSON", "OBJECT"})

    def test_validate_relationship_rejects_invalid_source_type(self) -> None:
        """Relationship validator should reject non-string source identifiers."""
        relationship: dict[str, Any] = {"source_id": 123, "type": "REFERENCES"}
        with pytest.raises(ValueError, match="relationship.source_id must be a string"):
            validate_relationship(relationship)

    def test_validate_relationship_returns_normalized_payload(self) -> None:
        """Relationship validator should return a stripped, typed payload."""
        relationship = validate_relationship({"source_id": " source_1 ", "type": " LINKS "})
        assert relationship == {"source_id": "source_1", "type": "LINKS"}
