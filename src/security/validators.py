"""Shared validation helpers for security-critical input boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast


def validate_tenant_id(tenant_id: str | None) -> str:
    """Validate tenant identifier shape, with org-wide mode injection.

    In org-wide single-company mode (``single_company.enabled = True``) a
    ``None`` value is automatically replaced with the configured ``company_id``.
    A mismatched value raises ``ValueError`` immediately.

    In multi-tenant mode (default) the original behaviour is preserved:
    ``None`` or blank values raise ``ValueError``.

    Args:
        tenant_id: Tenant identifier provided by callers.

    Returns:
        str: Normalized tenant identifier.

    Raises:
        ValueError: If tenant_id is not a non-empty string and cannot be
            resolved from org-wide context.
    """
    from src.security.tenant_context import OrgTenantContext  # noqa: PLC0415

    resolved = OrgTenantContext.resolve(tenant_id)
    return validate_required_string(resolved, field_name="tenant_id")


def validate_required_string(value: str | None, *, field_name: str) -> str:
    """Validate a required string and return stripped value.

    Args:
        value: Candidate string value.
        field_name: Field label used in error messages.

    Returns:
        str: Stripped non-empty value.

    Raises:
        ValueError: If value is missing, non-string, or blank.
    """
    if value is None:
        msg = f"{field_name} must be a non-empty string"
        raise ValueError(msg)

    normalized_value = value.strip()
    if not normalized_value:
        msg = f"{field_name} cannot be blank"
        raise ValueError(msg)

    return normalized_value


def validate_optional_string(value: str | None, *, field_name: str) -> str | None:
    """Validate an optional string when present.

    Args:
        value: Candidate optional string value.
        field_name: Field label used in error messages.

    Returns:
        str | None: Stripped string when present, else None.

    Raises:
        ValueError: If a provided value is not a valid non-empty string.
    """
    if value is None:
        return None
    return validate_required_string(value, field_name=field_name)


def validate_mapping(value: object, *, field_name: str) -> dict[str, object]:
    """Validate that a value is a JSON-like object.

    Args:
        value: Candidate mapping value.
        field_name: Field label used in error messages.

    Returns:
        dict[str, object]: Copy of mapping as dictionary.

    Raises:
        TypeError: If value is not a mapping.
    """
    if not isinstance(value, Mapping):
        msg = f"{field_name} must be an object"
        raise TypeError(msg)
    return dict(cast(dict[str, object], value))


def validate_optional_mapping(
    value: object | None,
    *,
    field_name: str,
) -> dict[str, object] | None:
    """Validate optional mapping values.

    Args:
        value: Candidate optional mapping value.
        field_name: Field label used in error messages.

    Returns:
        dict[str, object] | None: Mapping copy when provided, else None.

    Raises:
        ValueError: If provided value is not a mapping.
    """
    if value is None:
        return None
    return validate_mapping(value, field_name=field_name)


def validate_window_size(
    window_size: object,
    *,
    minimum: int = 1,
    maximum: int = 100,
) -> int:
    """Validate context window bounds.

    Args:
        window_size: Requested number of turns.
        minimum: Inclusive minimum value. Defaults to 1.
        maximum: Inclusive maximum value. Defaults to 100.

    Returns:
        int: Validated window size.

    Raises:
        ValueError: If value is not an integer within bounds.
    """
    if not isinstance(window_size, int):
        msg = "window_size must be an integer"
        raise TypeError(msg)
    if not (minimum <= window_size <= maximum):
        msg = f"window_size must be between {minimum} and {maximum}"
        raise ValueError(msg)
    return window_size


def validate_entity_type(entity_type: str, *, allowed_entity_types: set[str]) -> str:
    """Validate POLE+O entity type membership.

    Args:
        entity_type: Candidate entity type.
        allowed_entity_types: Permitted entity type set.

    Returns:
        str: Validated entity type.

    Raises:
        ValueError: If entity type is invalid.
    """
    normalized_type = validate_required_string(entity_type, field_name="entity_type")
    if normalized_type not in allowed_entity_types:
        msg = "Invalid entity_type."
        raise ValueError(msg)
    return normalized_type


def validate_relationship(relationship: dict[str, Any] | None) -> dict[str, str] | None:
    """Validate relationship object used for edge creation.

    Args:
        relationship: Optional relationship payload.

    Returns:
        dict[str, str] | None: Normalized relationship payload.

    Raises:
        ValueError: If relationship object or fields are invalid.
    """
    if relationship is None:
        return None

    normalized_relationship: dict[str, str] = validate_mapping(
        relationship, field_name="relationship"
    )  # type: ignore[assignment]

    source_id = normalized_relationship.get("source_id")
    rel_type = normalized_relationship.get("type")

    if source_id is not None and not isinstance(source_id, str):  # type: ignore[unreachable]
        msg = "relationship.source_id must be a string when provided"
        raise ValueError(msg)
    if rel_type is not None and not isinstance(rel_type, str):  # type: ignore[unreachable]
        msg = "relationship.type must be a string when provided"
        raise ValueError(msg)

    result: dict[str, str] = {}
    if source_id is not None:
        result["source_id"] = validate_required_string(
            source_id,
            field_name="relationship.source_id",
        )
    if rel_type is not None:
        result["type"] = validate_required_string(rel_type, field_name="relationship.type")

    return result
