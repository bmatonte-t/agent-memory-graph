"""Typed wrappers for external Google SDK calls.

These wrappers isolate dynamic SDK boundaries so that static type checking
remains predictable in application modules.
"""

# ruff: noqa: D102,PLC0415,TC003,TRY004
# pyright: reportUnknownVariableType=false,reportUnknownMemberType=false,reportUnknownArgumentType=false

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol, SupportsInt, TypeVar, cast

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SpannerOperationProtocol(Protocol):
    """Protocol for async DDL operation handles."""

    def result(self) -> object: ...


class SpannerSnapshotProtocol(Protocol):
    """Protocol for snapshot read operations used by the project."""

    def execute_sql(
        self,
        sql: str,
        params: Mapping[str, object] | None = None,
    ) -> Iterable[Sequence[object]]: ...


class SpannerBatchProtocol(Protocol):
    """Protocol for Spanner batch mutation operations."""

    def execute_update(self, sql: str, params: Mapping[str, object]) -> int: ...


class SpannerTransactionProtocol(Protocol):
    """Protocol for transaction callback operations."""

    def execute_sql(
        self,
        sql: str,
        params: Mapping[str, object] | None = None,
    ) -> Iterable[Sequence[object]]: ...

    def execute_update(self, sql: str, params: Mapping[str, object]) -> int: ...


class SpannerDatabaseProtocol(Protocol):
    """Protocol for the Spanner database methods used by this codebase."""

    def snapshot(self) -> AbstractContextManager[SpannerSnapshotProtocol]: ...

    def batch(self) -> AbstractContextManager[SpannerBatchProtocol]: ...

    def update_ddl(self, ddl_statements: list[str]) -> SpannerOperationProtocol: ...

    def run_in_transaction(self, callback: Callable[[SpannerTransactionProtocol], T]) -> T: ...


@dataclass(frozen=True)
class SchedulerJobResult:
    """Typed result from scheduler job creation."""

    name: str


def as_spanner_database(database: object) -> SpannerDatabaseProtocol:
    """Cast raw database object to typed protocol at the boundary.

    Args:
        database: Raw SDK database object.

    Returns:
        SpannerDatabaseProtocol: Typed view of the database object.
    """
    return cast("SpannerDatabaseProtocol", database)


def execute_sql_rows(
    database: SpannerDatabaseProtocol,
    sql: str,
    params: Mapping[str, object] | None = None,
) -> list[tuple[object, ...]]:
    """Execute SQL and normalize rows to concrete tuples.

    Args:
        database: Spanner database protocol.
        sql: SQL or GQL statement.
        params: Optional query parameters.

    Returns:
        list[tuple[object, ...]]: Fully materialized row tuples.
    """
    with database.snapshot() as snapshot:
        return execute_sql_rows_from_snapshot(snapshot, sql, params)


def execute_sql_rows_from_snapshot(
    snapshot: SpannerSnapshotProtocol,
    sql: str,
    params: Mapping[str, object] | None = None,
) -> list[tuple[object, ...]]:
    """Execute SQL against a snapshot and normalize row types.

    Args:
        snapshot: Spanner snapshot protocol.
        sql: SQL or GQL statement.
        params: Optional query parameters.

    Returns:
        list[tuple[object, ...]]: Fully materialized row tuples.
    """
    rows = snapshot.execute_sql(sql, params)
    return [tuple(row) for row in rows]


def execute_sql_rows_in_transaction(
    transaction: SpannerTransactionProtocol,
    sql: str,
    params: Mapping[str, object] | None = None,
) -> list[tuple[object, ...]]:
    """Execute SQL in a transaction callback with normalized rows.

    Args:
        transaction: Spanner transaction protocol.
        sql: SQL statement.
        params: Optional query parameters.

    Returns:
        list[tuple[object, ...]]: Fully materialized row tuples.
    """
    rows = transaction.execute_sql(sql, params)
    return [tuple(row) for row in rows]


def execute_dml(
    database: SpannerDatabaseProtocol,
    sql: str,
    params: Mapping[str, object],
) -> int:
    """Execute a DML statement with batch-first, transaction fallback semantics.

    Some emulator/runtime combinations expose ``batch`` objects without
    ``execute_update``. In those cases we transparently fall back to a transaction
    callback so DML still executes.

    Args:
        database: Spanner database protocol.
        sql: DML statement.
        params: Bound parameters for the statement.

    Returns:
        int: Number of affected rows when provided by the backend.
    """
    try:
        with database.batch() as batch:
            execute_update = getattr(batch, "execute_update", None)
            if callable(execute_update):
                rows_affected = execute_update(sql, params)
                return int(cast("SupportsInt", rows_affected))
    except AttributeError:
        logger.debug("Spanner batch execute_update unavailable; falling back to transaction")

    def _run(transaction: SpannerTransactionProtocol) -> int:
        rows_affected = transaction.execute_update(sql, params)
        return int(cast("SupportsInt", rows_affected))

    return int(database.run_in_transaction(_run))


def create_cloud_scheduler_http_job(
    *,
    project_id: str,
    location: str,
    job_name: str,
    description: str,
    schedule: str,
    target_uri: str,
    body_json: bytes,
) -> SchedulerJobResult:
    """Create a Cloud Scheduler HTTP job and return a typed result.

    Args:
        project_id: GCP project id.
        location: Cloud Scheduler location.
        job_name: Scheduler job resource suffix.
        description: Job description text.
        schedule: Cron schedule.
        target_uri: HTTPS endpoint URI.
        body_json: JSON payload encoded as bytes.

    Returns:
        SchedulerJobResult: Created job result with name.

    Raises:
        RuntimeError: If scheduler SDK is unavailable or job creation fails.
    """
    try:
        from google.cloud import scheduler_v1  # type: ignore[import-untyped]
        from google.cloud.scheduler_v1.types import (  # type: ignore[import-untyped]
            HttpTarget,
            Job,
        )
    except ImportError as error:
        msg = (
            "google-cloud-scheduler not installed. Install with: pip install google-cloud-scheduler"
        )
        raise RuntimeError(msg) from error

    try:
        client = scheduler_v1.CloudSchedulerClient()
        parent = client.common_location_path(project_id, location)
        job = Job(
            name=f"{parent}/jobs/{job_name}",
            description=description,
            schedule=schedule,
            time_zone="UTC",
            http_target=HttpTarget(
                uri=target_uri,
                http_method="POST",
                headers={"Content-Type": "application/json"},
                body=body_json,
            ),
            attempt_config={
                "max_retries": 2,
                "max_backoff_duration": {"seconds": 3600},
                "min_backoff_duration": {"seconds": 60},
            },
        )
        response = client.create_job(request={"parent": parent, "job": job})
    except Exception as error:
        msg = f"failed to create Cloud Scheduler job: {error}"
        raise RuntimeError(msg) from error

    return SchedulerJobResult(name=str(response.name))


def generate_generative_ai_text(model_name: str, prompt: str) -> str:
    """Generate text using google.generativeai with typed output.

    Args:
        model_name: Generative model name.
        prompt: Prompt text sent to the model.

    Returns:
        str: Generated response text.

    Raises:
        RuntimeError: If SDK is unavailable or response payload is invalid.
    """
    try:
        from google.generativeai import GenerativeModel  # type: ignore[import-untyped]
    except ImportError as error:
        msg = "google-generativeai is required for this operation"
        raise RuntimeError(msg) from error

    try:
        model = GenerativeModel(model_name)
        response = model.generate_content(prompt)
    except Exception as error:
        msg = f"generative model invocation failed: {error}"
        raise RuntimeError(msg) from error

    response_text = getattr(response, "text", None)
    if not isinstance(response_text, str):
        msg = "generative model returned an invalid response payload"
        raise RuntimeError(msg)

    return response_text


def install_cloud_logging_handler(project_id: str | None, log_level: str) -> object:
    """Create and configure the default Cloud Logging handler.

    Args:
        project_id: Optional GCP project id.
        log_level: Handler log level.

    Returns:
        object: Configured Cloud Logging handler instance.

    Raises:
        RuntimeError: If SDK is unavailable or handler cannot be built.
    """
    try:
        import google.cloud.logging  # type: ignore[import-untyped]
    except ImportError as error:
        msg = "google-cloud-logging is required for cloud logging integration"
        raise RuntimeError(msg) from error

    try:
        client_kwargs: dict[str, object] = {}
        if project_id:
            client_kwargs["project"] = project_id
        client = google.cloud.logging.Client(**client_kwargs)
        handler = client.get_default_handler()
        handler.setLevel(log_level)
    except Exception as error:
        msg = f"failed to create cloud logging handler: {error}"
        raise RuntimeError(msg) from error

    return handler
