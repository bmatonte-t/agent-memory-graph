"""Spanner client initialization and connection pooling."""

from __future__ import annotations

from typing import Self

from google.cloud import spanner


class SpannerClient:
    """Singleton Spanner client for managing database connections."""

    _instance: SpannerClient | None = None
    _client: spanner.Client | None = None
    _instance_ref: spanner.Instance | None = None
    _database: spanner.Database | None = None

    def __new__(cls) -> Self:
        """Ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

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
        if cls._client is None:
            cls._client = spanner.Client(project=project_id)
            cls._instance_ref = cls._client.instance(instance_id)
            cls._database = cls._instance_ref.database(database_id)
        return instance

    @classmethod
    def get_client(cls) -> spanner.Client:
        """Get the Spanner client. Raises error if not initialized."""
        if cls._client is None:
            msg = "SpannerClient not initialized. Call initialize() first."
            raise RuntimeError(msg)
        return cls._client

    @classmethod
    def get_database(cls) -> spanner.Database:
        """Get the Spanner database. Raises error if not initialized."""
        if cls._database is None:
            msg = "SpannerClient not initialized. Call initialize() first."
            raise RuntimeError(msg)
        return cls._database

    @classmethod
    def execute_sql(cls, sql: str, params: dict | None = None) -> list:
        """Execute a SQL query and return results.

        Args:
            sql: SQL query string
            params: Query parameters (optional)

        Returns:
            List of result rows
        """
        database = cls.get_database()
        with database.snapshot() as snapshot:
            results = snapshot.execute_sql(sql, params or {})
            return list(results)

    @classmethod
    def execute_update(cls, sql: str, params: dict | None = None) -> int:
        """Execute a DML update and return rows affected.

        Args:
            sql: DML query string
            params: Query parameters (optional)

        Returns:
            Number of rows affected
        """
        database = cls.get_database()
        with database.batch() as batch:
            return batch.execute_update(sql, params or {})

    @classmethod
    def close(cls) -> None:
        """Close the Spanner client."""
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            cls._instance_ref = None
            cls._database = None
