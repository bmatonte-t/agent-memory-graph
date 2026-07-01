"""Spanner client initialization and connection pooling."""

from __future__ import annotations

import logging
import re
import threading
from typing import Any, Self, cast

from src.integrations.google_sdk_wrappers import (
    SpannerDatabaseProtocol,
    as_spanner_database,
    execute_dml,
    execute_sql_rows,
)
from src.security.validators import validate_tenant_id

logger = logging.getLogger(__name__)

_DML_TABLE_PATTERN_BY_OPERATION: dict[str, re.Pattern[str]] = {
    "INSERT": re.compile(r"^\s*INSERT\s+INTO\s+`?([A-Za-z_][A-Za-z0-9_]*)`?", re.IGNORECASE),
    "UPDATE": re.compile(r"^\s*UPDATE\s+`?([A-Za-z_][A-Za-z0-9_]*)`?", re.IGNORECASE),
    "DELETE": re.compile(
        r"^\s*DELETE\s+FROM\s+`?([A-Za-z_][A-Za-z0-9_]*)`?",
        re.IGNORECASE,
    ),
    "TRUNCATE": re.compile(
        r"^\s*TRUNCATE\s+(?:TABLE\s+)?`?([A-Za-z_][A-Za-z0-9_]*)`?",
        re.IGNORECASE,
    ),
    "MERGE": re.compile(r"^\s*MERGE\s+INTO\s+`?([A-Za-z_][A-Za-z0-9_]*)`?", re.IGNORECASE),
}

_AUDIT_MUTATION_PATTERNS: dict[str, re.Pattern[str]] = {
    "UPDATE": re.compile(r"\bUPDATE\s+`?AUDIT_EVENTS`?\b", re.IGNORECASE),
    "DELETE": re.compile(r"\bDELETE\s+FROM\s+`?AUDIT_EVENTS`?\b", re.IGNORECASE),
    "MERGE": re.compile(r"\bMERGE\s+INTO\s+`?AUDIT_EVENTS`?\b", re.IGNORECASE),
    "TRUNCATE": re.compile(
        r"\bTRUNCATE(?:\s+TABLE)?\s+`?AUDIT_EVENTS`?\b",
        re.IGNORECASE,
    ),
}


class SpannerClient:
    """Singleton Spanner client for managing database connections."""

    _instance: SpannerClient | None = None
    _client: object | None = None
    _instance_ref: object | None = None
    _database: object | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> Self:
        """Ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cast("Self", cls._instance)

    @classmethod
    def initialize(
        cls,
        project_id: str,
        instance_id: str,
        database_id: str,
    ) -> SpannerClient:
        """Initialize the Spanner client and return the singleton instance.

        Args:
            project_id: GCP project ID
            instance_id: Spanner instance ID
            database_id: Spanner database ID

        Returns:
            SpannerClient singleton instance
        """
        instance = cls()
        with cls._lock:
            if cls._client is None:
                from google.cloud import spanner  # type: ignore[import-untyped]  # noqa: PLC0415

                raw_client: Any = spanner.Client(project=project_id)
                raw_instance: Any = raw_client.instance(instance_id)
                raw_database: Any = raw_instance.database(database_id)
                cls._client = raw_client
                cls._instance_ref = raw_instance
                cls._database = raw_database
        return instance

    @classmethod
    def get_client(cls) -> object:
        """Get the Spanner client. Raises error if not initialized."""
        if cls._client is None:
            msg = "SpannerClient not initialized. Call initialize() first."
            raise RuntimeError(msg)
        return cls._client

    @classmethod
    def get_database(cls) -> SpannerDatabaseProtocol:
        """Get the Spanner database. Raises error if not initialized."""
        if cls._database is None:
            msg = "SpannerClient not initialized. Call initialize() first."
            raise RuntimeError(msg)
        return as_spanner_database(cls._database)

    @classmethod
    def execute_sql(
        cls, sql: str, params: dict[str, object] | None = None
    ) -> list[tuple[object, ...]]:
        """Execute a SQL query and return results.

        Args:
            sql: SQL query string
            params: Query parameters (optional)

        Returns:
            List of result rows
        """
        database = cls.get_database()
        return execute_sql_rows(database, sql, params or {})

    @classmethod
    def execute_update(cls, sql: str, params: dict[str, object] | None = None) -> int:
        """Execute a DML update and return rows affected.

        Args:
            sql: DML query string
            params: Query parameters (optional)

        Returns:
            Number of rows affected
        """
        normalized_sql = cls._strip_leading_sql_comments(sql)
        cls._validate_audit_table_mutation(normalized_sql)

        mutation_target = cls._extract_dml_target(normalized_sql)
        if mutation_target is not None:
            operation, table_name = mutation_target
            cls._validate_audit_mutation_forbidden(table_name, operation)

        database = cls.get_database()
        return execute_dml(database, sql, params or {})

    @staticmethod
    def _extract_dml_target(sql: str) -> tuple[str, str] | None:
        """Extract the DML operation and target table from SQL.

        Args:
            sql: SQL statement text.

        Returns:
            tuple[str, str] | None: Operation and table name when parsable.
        """
        normalized_sql = sql.strip()
        if not normalized_sql:
            return None

        operation = normalized_sql.split(maxsplit=1)[0].upper()
        pattern = _DML_TABLE_PATTERN_BY_OPERATION.get(operation)
        if pattern is None:
            return None

        match = pattern.search(normalized_sql)
        if match is None:
            return None

        return operation, match.group(1)

    @staticmethod
    def _strip_leading_sql_comments(sql: str) -> str:
        """Remove leading SQL comments before policy inspection.

        Args:
            sql: Raw SQL statement text.

        Returns:
            str: SQL text with leading comments removed.
        """
        normalized_sql = sql.lstrip()

        while normalized_sql.startswith(("--", "/*")):
            if normalized_sql.startswith("--"):
                newline_index = normalized_sql.find("\n")
                if newline_index == -1:
                    return ""
                normalized_sql = normalized_sql[newline_index + 1 :].lstrip()
                continue

            comment_end_index = normalized_sql.find("*/")
            if comment_end_index == -1:
                return ""
            normalized_sql = normalized_sql[comment_end_index + 2 :].lstrip()

        return normalized_sql

    @classmethod
    def _validate_audit_table_mutation(cls, sql: str) -> None:
        """Reject wrapped or prefixed mutations against the audit table.

        Args:
            sql: SQL statement text with leading comments removed.
        """
        for operation, pattern in _AUDIT_MUTATION_PATTERNS.items():
            if pattern.search(sql):
                cls._validate_audit_mutation_forbidden("AUDIT_EVENTS", operation)

    @classmethod
    def close(cls) -> None:
        """Close the Spanner client."""
        if cls._client is not None:
            close_method = getattr(cls._client, "close", None)
            if callable(close_method):
                close_method()
            cls._client = None
            cls._instance_ref = None
            cls._database = None

    @staticmethod
    def validate_tenant_id(tenant_id: str | None) -> str:
        """Validate tenant_id is non-empty and properly formatted.

        Args:
            tenant_id: Tenant identifier to validate

        Returns:
            str: Validated tenant_id

        Raises:
            ValueError: If tenant_id is empty or invalid
        """
        return validate_tenant_id(tenant_id)

    @staticmethod
    def _validate_audit_mutation_forbidden(table_name: str, operation: str) -> None:
        """Enforce audit table immutability by rejecting mutations.

        Audit events are append-only. Updates and deletions are forbidden.

        Args:
            table_name: Target table name
            operation: Operation type (INSERT, UPDATE, DELETE)

        Raises:
            PermissionError: If attempting to mutate AUDIT_EVENTS
        """
        if table_name.upper() == "AUDIT_EVENTS" and operation.upper() != "INSERT":
            msg = f"Operation {operation} on {table_name} is forbidden. Audit events are immutable."
            logger.error("audit_mutation_forbidden %s", msg)
            raise PermissionError(msg)
