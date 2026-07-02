"""Core memory API implementations."""

import json
import logging
import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

from src.db.idempotency import IdempotencyContext
from src.db.retry import async_retry_with_backoff, get_retry_policy
from src.db.schema import SchemaConfig
from src.db.spanner_client import SpannerClient
from src.integrations.google_sdk_wrappers import (
    SpannerBatchProtocol,
    SpannerDatabaseProtocol,
    SpannerTransactionProtocol,
    execute_sql_rows,
)
from src.memory.exceptions import WeightUpdateFailedError
from src.models.schemas import (
    AuditResponse,
    ContextResponse,
    ContextTurn,
    EndSessionResponse,
    FactResponse,
    GraphExportEdge,
    GraphExportNode,
    GraphExportResponse,
    SessionKnowledgeExtractionResponse,
    SessionResponse,
)
from src.observability.logging import structured_log
from src.observability.metrics import record_authorization_denial
from src.project_base.settings import settings
from src.security.governance import AuthorizationScope  # noqa: TC001
from src.security.validators import (
    validate_entity_type,
    validate_optional_mapping,
    validate_relationship,
    validate_required_string,
    validate_tenant_id,
    validate_window_size,
)

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_CONFIDENCE_SCORE = 1.0
API_DERIVED_SOURCE_CONFIDENCE_SCORE = 0.7
RECENT_ACCESS_WINDOW_DAYS = 7
ACTIVE_STATUS_VALUES = {"active", "open", "enabled"}
VALID_SESSION_END_REASONS = {"completed", "timeout", "aborted"}
DEFAULT_EXTRACTION_DOMAIN = "general"
DERIVED_FROM_CONTEXT_RELATIONSHIP = "DERIVED_FROM_CONTEXT"
TWriteResult = TypeVar("TWriteResult")
_CONTEXT_CURSOR_SEPARATOR = "|"


def _is_match_query_unsupported(error: Exception) -> bool:
    """Return whether an error indicates graph MATCH is unsupported.

    Args:
        error: Exception raised while executing a query.

    Returns:
        bool: True when the backend does not support MATCH syntax.
    """
    message = str(error).lower()
    return "unexpected keyword match" in message


class MemoryAPI:
    """Core memory API for tripartite memory operations."""

    @staticmethod
    def _run_write_operation(
        database: SpannerDatabaseProtocol,
        operation: Callable[[SpannerBatchProtocol], TWriteResult],
    ) -> TWriteResult:
        """Run write operations with batch-first, transaction fallback semantics.

        Args:
            database: Spanner database object.
            operation: Callable that issues one or more execute_update statements.

        Returns:
            TWriteResult: Result returned by ``operation``.
        """
        try:
            with database.batch() as batch:
                execute_update = getattr(batch, "execute_update", None)
                if callable(execute_update):
                    return operation(batch)
        except AttributeError:
            logger.debug("Spanner batch execute_update unavailable; falling back to transaction")

        def _run_in_transaction(transaction: SpannerTransactionProtocol) -> TWriteResult:
            return operation(cast("SpannerBatchProtocol", transaction))

        return database.run_in_transaction(_run_in_transaction)

    @staticmethod
    def _record_authorization_decision(
        *,
        tenant_id: str,
        event_type: str,
        source_node_id: str,
        context: dict[str, Any],
    ) -> None:
        """Persist an authorization decision without re-entering policy checks."""
        tenant_id = validate_tenant_id(tenant_id)
        event_type = validate_required_string(event_type, field_name="event_type")
        source_node_id = validate_required_string(source_node_id, field_name="source_node_id")

        timestamp = datetime.now(UTC)
        database = SpannerClient.get_database()

        def _write(batch: SpannerBatchProtocol) -> None:
            MemoryAPI._insert_audit_event_in_batch(
                batch=batch,
                tenant_id=tenant_id,
                event_type=event_type,
                source_node_id=source_node_id,
                context=context,
                timestamp=timestamp,
            )

        MemoryAPI._run_write_operation(database, _write)

    @staticmethod
    def _authorize_operation(
        *,
        operation: str,
        tenant_id: str,
        authorization_scope: AuthorizationScope | None,
        node_id: str | None = None,
        label: str | None = None,
        memory_tier: str | None = None,
        relationship_type: str | None = None,
    ) -> None:
        """Enforce deny-by-default authorization and audit the decision."""
        policy = settings.governance.authorization
        if not policy.enabled:
            return

        allowed = policy.authorize(
            authorization_scope,
            node_id=node_id,
            label=label,
            memory_tier=memory_tier,
            relationship_type=relationship_type,
        )
        decision_context = {
            "operation": operation,
            "tenant_id": tenant_id,
            "node_id": node_id,
            "label": label,
            "memory_tier": memory_tier,
            "relationship_type": relationship_type,
            "agent_id": authorization_scope.agent_id if authorization_scope else None,
            "allowed_node_ids": authorization_scope.allowed_node_ids if authorization_scope else [],
            "allowed_labels": authorization_scope.allowed_labels if authorization_scope else [],
            "allowed_memory_tiers": (
                authorization_scope.allowed_memory_tiers if authorization_scope else []
            ),
            "allowed_relationship_types": (
                authorization_scope.allowed_relationship_types if authorization_scope else []
            ),
            "allowed": allowed,
        }

        try:
            MemoryAPI._record_authorization_decision(
                tenant_id=tenant_id,
                event_type="AUTHZ_ALLOW" if allowed else "AUTHZ_DENY",
                source_node_id=node_id or operation,
                context=decision_context,
            )
        except RuntimeError:
            structured_log(
                logger,
                logging.WARNING,
                "authorization_decision_record_failed",
                {
                    "tenant_id": tenant_id,
                    "operation": operation,
                },
            )

        if not allowed:
            resource_type = label or memory_tier or relationship_type or operation
            record_authorization_denial(tenant_id, resource_type)
            msg = f"authorization denied for {operation}"
            raise PermissionError(msg)

    @staticmethod
    def _enforce_audit_append_only(operation: str) -> None:
        """Validate that audit table mutations remain append-only.

        Args:
            operation: Mutation operation on audit table.

        Raises:
            PermissionError: If the requested operation violates immutability.
        """
        SpannerClient._validate_audit_mutation_forbidden("AUDIT_EVENTS", operation)  # noqa: SLF001  # type: ignore[private-unimported]

    @staticmethod
    def _serialize_json_attributes(attributes: dict[str, Any]) -> str:
        """Serialize attributes payload to JSON string.

        Args:
            attributes: Attribute mapping to persist.

        Returns:
            str: JSON-encoded payload.
        """
        return json.dumps(attributes, separators=(",", ":"), default=str)

    @staticmethod
    def _insert_audit_event_in_batch(
        *,
        batch: SpannerBatchProtocol,
        tenant_id: str,
        event_type: str,
        source_node_id: str,
        context: dict[str, Any] | None,
        timestamp: datetime,
    ) -> AuditResponse:
        """Insert an audit event inside an existing write batch.

        Writes to append-only AUDIT_EVENTS table with tenant isolation.

        Args:
            batch: Active Spanner batch.
            tenant_id: Tenant identifier for isolation.
            event_type: Audit event type.
            source_node_id: Source node identifier.
            context: Optional context payload.
            timestamp: Event timestamp.

        Returns:
            AuditResponse: Created audit event descriptor.

        Raises:
            ValueError: If tenant_id is empty or invalid.
        """
        tenant_id = validate_tenant_id(tenant_id)
        event_type = validate_required_string(event_type, field_name="event_type")
        source_node_id = validate_required_string(source_node_id, field_name="source_node_id")
        context = validate_optional_mapping(context, field_name="context") or None
        MemoryAPI._enforce_audit_append_only("INSERT")
        event_id = str(uuid.uuid4())
        event_attributes = {
            "event_type": event_type,
            "source_node_id": source_node_id,
            **(dict(context) if context else {}),
        }

        sql = """
            INSERT INTO AUDIT_EVENTS (
                EventId, TenantId, SourceNodeId, EventType,
                Attributes, CreatedAt
            ) VALUES (
                @event_id, @tenant_id, @source_node_id, @event_type,
                CAST(@attributes AS JSON), @now
            )
        """
        batch.execute_update(
            sql,
            {
                "event_id": event_id,
                "tenant_id": tenant_id,
                "source_node_id": source_node_id,
                "event_type": event_type,
                "now": timestamp,
                "attributes": MemoryAPI._serialize_json_attributes(event_attributes),
            },
        )

        return AuditResponse(
            event_id=event_id,
            event_type=event_type,
            timestamp=timestamp,
            tenant_id=tenant_id,
        )

    @staticmethod
    def _get_node_memory_tier(tenant_id: str, node_id: str) -> str | None:
        """Return memory tier for a node when it exists in the tenant.

        Args:
            tenant_id: Tenant identifier for isolation.
            node_id: Node identifier to inspect.

        Returns:
            str | None: Node memory tier when found in tenant, else None.

        Raises:
            ValueError: If tenant_id is empty or invalid.
            RuntimeError: If database read fails.
        """
        tenant_id = validate_tenant_id(tenant_id)
        node_id = validate_required_string(node_id, field_name="node_id")
        query = """
            SELECT MemoryTier
            FROM MemoryNode
            WHERE TenantId = @tenant_id AND NodeId = @node_id
            LIMIT 1
        """

        try:
            database = SpannerClient.get_database()
            rows = execute_sql_rows(
                database,
                query,
                {"tenant_id": tenant_id, "node_id": node_id},
            )
        except Exception as error:
            msg = f"Failed to lookup node tier: {error}"
            raise RuntimeError(msg) from error

        if not rows:
            return None

        tier_value = rows[0][0]
        return str(tier_value) if tier_value is not None else None

    @staticmethod
    def _has_audit_event(
        tenant_id: str,
        source_node_id: str,
        event_type: str,
    ) -> bool:
        """Check whether an audit event already exists for a source node.

        Args:
            tenant_id: Tenant identifier for isolation.
            source_node_id: Source node linked to the event.
            event_type: Event type to look up.

        Returns:
            bool: True when at least one event exists.

        Raises:
            RuntimeError: If database read fails.
        """
        tenant_id = validate_tenant_id(tenant_id)
        source_node_id = validate_required_string(source_node_id, field_name="source_node_id")
        event_type = validate_required_string(event_type, field_name="event_type")

        query = """
            SELECT EventId
            FROM AUDIT_EVENTS
            WHERE TenantId = @tenant_id
              AND SourceNodeId = @source_node_id
              AND EventType = @event_type
            LIMIT 1
        """

        try:
            database = SpannerClient.get_database()
            rows = execute_sql_rows(
                database,
                query,
                {
                    "tenant_id": tenant_id,
                    "source_node_id": source_node_id,
                    "event_type": event_type,
                },
            )
        except Exception as error:
            msg = f"Failed to lookup audit event: {error}"
            raise RuntimeError(msg) from error

        return bool(rows)

    @staticmethod
    def _mark_session_closed(
        tenant_id: str,
        session_id: str,
        end_reason: str,
        ended_at: datetime,
    ) -> bool:
        """Atomically mark a context session as closed.

        Args:
            tenant_id: Tenant identifier for isolation.
            session_id: Session node identifier.
            end_reason: Closure reason.
            ended_at: Closure timestamp.

        Returns:
            bool: True when state transitioned to closed, False when already closed.

        Raises:
            RuntimeError: If state transition write fails.
        """
        tenant_id = validate_tenant_id(tenant_id)
        session_id = validate_required_string(session_id, field_name="session_id")
        end_reason = validate_required_string(end_reason, field_name="end_reason")

        update_sql = """
            UPDATE MemoryNode
            SET SessionStatus = 'closed',
                SessionEndedAt = @ended_at,
                SessionEndReason = @end_reason,
                UpdatedAt = @ended_at
            WHERE TenantId = @tenant_id
              AND NodeId = @session_id
              AND MemoryTier = @tier
              AND (SessionStatus IS NULL OR SessionStatus != 'closed')
        """

        database = SpannerClient.get_database()

        def _transaction(transaction: SpannerTransactionProtocol) -> int:
            return transaction.execute_update(
                update_sql,
                {
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                    "tier": SchemaConfig.MEMORY_TIER_CONTEXT,
                    "ended_at": ended_at,
                    "end_reason": end_reason,
                },
            )

        try:
            updated_rows = database.run_in_transaction(_transaction)
        except Exception as error:
            msg = f"Failed to mark session as closed: {error}"
            raise RuntimeError(msg) from error

        return updated_rows > 0

    @staticmethod
    def _validate_end_reason(end_reason: str) -> str:
        """Validate and normalize session end reason.

        Args:
            end_reason: Session closure reason.

        Returns:
            str: Normalized closure reason.

        Raises:
            ValueError: If the reason is unsupported.
        """
        normalized_reason = validate_required_string(end_reason, field_name="end_reason").lower()
        if normalized_reason not in VALID_SESSION_END_REASONS:
            valid_reasons = ", ".join(sorted(VALID_SESSION_END_REASONS))
            msg = f"invalid end_reason. Must be one of: {valid_reasons}"
            raise ValueError(msg)
        return normalized_reason

    @staticmethod
    def _extract_turn_content(turn: ContextTurn) -> str:
        """Extract stable text content from a context turn payload.

        Args:
            turn: Context turn returned by retrieval APIs.

        Returns:
            str: Best-effort normalized content string.
        """
        raw_content = turn.content.strip()
        if not raw_content:
            return ""

        try:
            parsed_payload = json.loads(raw_content)
        except json.JSONDecodeError:
            return raw_content

        if isinstance(parsed_payload, dict):
            parsed_mapping = cast("Mapping[str, Any]", parsed_payload)
            candidate = parsed_mapping.get("content")
            if isinstance(candidate, str):
                return candidate.strip()

        return raw_content

    @staticmethod
    async def extract_session_knowledge(
        tenant_id: str,
        session_id: str,
        domain_hint: str | None = None,
        window_size: int = 50,
        authorization_scope: AuthorizationScope | None = None,
    ) -> SessionKnowledgeExtractionResponse:
        """Extract knowledge from session context and persist it into semantic memory.

        Args:
            tenant_id: Tenant identifier for isolation.
            session_id: Session identifier to extract from.
            domain_hint: Optional destination domain for extracted facts.
            window_size: Context turns to analyze.
            authorization_scope: Authorization scope for the request.

        Returns:
            SessionKnowledgeExtractionResponse: Extraction protocol summary.

        Raises:
            RuntimeError: If context retrieval fails.
        """
        tenant_id = validate_tenant_id(tenant_id)
        session_id = validate_required_string(session_id, field_name="session_id")
        window_size = validate_window_size(window_size)
        resolved_domain = (
            validate_required_string(domain_hint, field_name="domain_hint")
            if domain_hint is not None
            else DEFAULT_EXTRACTION_DOMAIN
        )
        extracted_at = datetime.now(UTC)

        await MemoryAPI.record_audit_event(
            tenant_id=tenant_id,
            event_type="SESSION_KNOWLEDGE_EXTRACTION_STARTED",
            source_node_id=session_id,
            context={"domain": resolved_domain, "window_size": window_size},
            authorization_scope=authorization_scope,
        )

        context_response = await MemoryAPI.retrieve_context_window(
            tenant_id=tenant_id,
            session_id=session_id,
            window_size=window_size,
            session_action_count=0,
            authorization_scope=authorization_scope,
        )

        extracted_facts = 0
        skipped_facts = 0
        failed_facts = 0

        for turn in context_response.turns:
            normalized_content = MemoryAPI._extract_turn_content(turn)
            if not normalized_content:
                skipped_facts += 1
                continue

            knowledge_entity_id = f"{session_id}:knowledge:{turn.turn_id}"
            existing_tier = MemoryAPI._get_node_memory_tier(
                tenant_id=tenant_id,
                node_id=knowledge_entity_id,
            )
            if existing_tier is not None:
                skipped_facts += 1
                continue

            try:
                await MemoryAPI.add_semantic_fact(
                    tenant_id=tenant_id,
                    entity_type="EVENT",
                    entity_id=knowledge_entity_id,
                    attributes={
                        "domain": resolved_domain,
                        "session_id": session_id,
                        "turn_id": turn.turn_id,
                        "role": turn.role,
                        "content": normalized_content,
                        "extraction_protocol": "session_close_v1",
                    },
                    relationship={
                        "source_id": session_id,
                        "type": DERIVED_FROM_CONTEXT_RELATIONSHIP,
                    },
                    session_id=None,
                    authorization_scope=authorization_scope,
                )
                extracted_facts += 1
            except RuntimeError:
                failed_facts += 1

        extraction_response = SessionKnowledgeExtractionResponse(
            session_id=session_id,
            tenant_id=tenant_id,
            domain=resolved_domain,
            processed_turns=len(context_response.turns),
            extracted_facts=extracted_facts,
            skipped_facts=skipped_facts,
            failed_facts=failed_facts,
            extracted_at=extracted_at,
        )

        await MemoryAPI.record_audit_event(
            tenant_id=tenant_id,
            event_type="SESSION_KNOWLEDGE_EXTRACTION_COMPLETED",
            source_node_id=session_id,
            context={
                "domain": extraction_response.domain,
                "processed_turns": extraction_response.processed_turns,
                "extracted_facts": extraction_response.extracted_facts,
                "skipped_facts": extraction_response.skipped_facts,
                "failed_facts": extraction_response.failed_facts,
            },
            authorization_scope=authorization_scope,
        )
        return extraction_response

    @staticmethod
    async def end_session(
        tenant_id: str,
        session_id: str,
        end_reason: str = "completed",
        domain_hint: str | None = None,
        window_size: int = 50,
        authorization_scope: AuthorizationScope | None = None,
    ) -> EndSessionResponse:
        """Close a session and trigger the session knowledge extraction protocol.

        Args:
            tenant_id: Tenant identifier for isolation.
            session_id: Session identifier to close.
            end_reason: Session closure reason.
            domain_hint: Optional target domain for extracted semantic facts.
            window_size: Number of context turns to process.
            authorization_scope: Authorization scope for the request.

        Returns:
            EndSessionResponse: Closure and extraction summary.
        """
        tenant_id = validate_tenant_id(tenant_id)
        session_id = validate_required_string(session_id, field_name="session_id")
        normalized_end_reason = MemoryAPI._validate_end_reason(end_reason)
        ended_at = datetime.now(UTC)

        MemoryAPI._authorize_operation(
            operation="end_session",
            tenant_id=tenant_id,
            authorization_scope=authorization_scope,
            node_id=session_id,
            label="Session",
            memory_tier=SchemaConfig.MEMORY_TIER_CONTEXT,
        )

        did_close = MemoryAPI._mark_session_closed(
            tenant_id=tenant_id,
            session_id=session_id,
            end_reason=normalized_end_reason,
            ended_at=ended_at,
        )
        if not did_close:
            return EndSessionResponse(
                session_id=session_id,
                tenant_id=tenant_id,
                status="closed",
                end_reason=normalized_end_reason,
                ended_at=ended_at,
                extraction_status="already_closed",
                extraction=SessionKnowledgeExtractionResponse(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    domain=domain_hint or DEFAULT_EXTRACTION_DOMAIN,
                    processed_turns=0,
                    extracted_facts=0,
                    skipped_facts=0,
                    failed_facts=0,
                    extracted_at=ended_at,
                ),
            )

        await MemoryAPI.record_audit_event(
            tenant_id=tenant_id,
            event_type="SESSION_CLOSED",
            source_node_id=session_id,
            context={
                "end_reason": normalized_end_reason,
                "domain_hint": domain_hint or DEFAULT_EXTRACTION_DOMAIN,
            },
            authorization_scope=authorization_scope,
        )

        extraction_status = "completed"
        extraction_response: SessionKnowledgeExtractionResponse

        try:
            extraction_response = await MemoryAPI.extract_session_knowledge(
                tenant_id=tenant_id,
                session_id=session_id,
                domain_hint=domain_hint,
                window_size=window_size,
                authorization_scope=authorization_scope,
            )
        except RuntimeError as error:
            extraction_status = "failed"
            extraction_response = SessionKnowledgeExtractionResponse(
                session_id=session_id,
                tenant_id=tenant_id,
                domain=domain_hint or DEFAULT_EXTRACTION_DOMAIN,
                processed_turns=0,
                extracted_facts=0,
                skipped_facts=0,
                failed_facts=0,
                extracted_at=ended_at,
            )
            await MemoryAPI.record_audit_event(
                tenant_id=tenant_id,
                event_type="SESSION_KNOWLEDGE_EXTRACTION_FAILED",
                source_node_id=session_id,
                context={"error": str(error)},
                authorization_scope=authorization_scope,
            )

        return EndSessionResponse(
            session_id=session_id,
            tenant_id=tenant_id,
            status="closed",
            end_reason=normalized_end_reason,
            ended_at=ended_at,
            extraction_status=extraction_status,
            extraction=extraction_response,
        )

    @staticmethod
    async def create_session(
        tenant_id: str,
        session_id: str,
        user_id: str,
        metadata: dict[str, Any] | None = None,
        authorization_scope: AuthorizationScope | None = None,
    ) -> SessionResponse:
        """Create a new session and initialize Context Graph.

        Args:
            tenant_id: Tenant identifier for isolation.
            session_id: Unique session identifier
            user_id: User ID associated with session
            metadata: Optional session metadata
            authorization_scope: Authorization scope for the request.

        Returns:
            SessionResponse with session details

        Raises:
            ValueError: If tenant_id, session_id, or user_id is empty or invalid
            RuntimeError: If database write fails after max retries
        """
        tenant_id = validate_tenant_id(tenant_id)
        session_id = validate_required_string(session_id, field_name="session_id")
        user_id = validate_required_string(user_id, field_name="user_id")
        metadata = validate_optional_mapping(metadata, field_name="metadata") or None

        MemoryAPI._authorize_operation(
            operation="create_session",
            tenant_id=tenant_id,
            authorization_scope=authorization_scope,
            node_id=session_id,
            label="Session",
            memory_tier=SchemaConfig.MEMORY_TIER_CONTEXT,
        )

        created_at = datetime.now(UTC)
        attributes = {"user_id": user_id, **(metadata or {})}

        retry_policy = get_retry_policy()
        try:
            await async_retry_with_backoff(
                MemoryAPI._do_create_session_batch,
                tenant_id,
                session_id,
                user_id,
                attributes,
                created_at,
                max_attempts=retry_policy.max_attempts,
                initial_backoff_seconds=retry_policy.initial_backoff_seconds,
                max_backoff_seconds=retry_policy.max_backoff_seconds,
            )
            structured_log(
                logger,
                logging.INFO,
                "create_session_completed",
                {
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                },
            )
        except Exception as e:
            structured_log(
                logger,
                logging.ERROR,
                "create_session_exhausted",
                {
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                    "attempts": retry_policy.max_attempts,
                },
            )
            msg = f"Failed to create session after {retry_policy.max_attempts} attempts: {e}"
            raise RuntimeError(msg) from e

        return SessionResponse(
            tenant_id=tenant_id,
            session_id=session_id,
            created_at=created_at,
            status="active",
        )

    @staticmethod
    async def _do_create_session_batch(
        tenant_id: str,
        session_id: str,
        user_id: str,
        attributes: dict[str, Any],
        created_at: datetime,
    ) -> None:
        """Execute idempotent session creation with batch write.

        Args:
            tenant_id: Tenant identifier.
            session_id: Session identifier.
            user_id: User identifier.
            attributes: Session attributes including user_id.
            created_at: Creation timestamp.

        Raises:
            ValueError: If tenant_id is None or empty — composite PK enforcement.
            Exception: If database write fails (may be retried by caller).
        """
        if not tenant_id or not tenant_id.strip():
            msg = "tenant_id is required for all MemoryNode writes"
            raise ValueError(msg)
        database = SpannerClient.get_database()
        node_sql = """
                INSERT INTO MemoryNode (
                    NodeId, TenantId, MemoryTier, Label, LogOddsWeight,
                    SessionActionCount, SessionStatus, LastAccessed,
                    Attributes, CreatedAt, UpdatedAt
                ) VALUES (
                    @node_id, @tenant_id, @tier, @label, @weight,
                    @action_count, @session_status, @now,
                    CAST(@attributes AS JSON), @now, @now
                )
            """

        audit_context = {"user_id": user_id}

        def _write(batch: SpannerBatchProtocol) -> None:
            batch.execute_update(
                node_sql,
                {
                    "node_id": session_id,
                    "tenant_id": tenant_id,
                    "tier": SchemaConfig.MEMORY_TIER_CONTEXT,
                    "label": "Session",
                    "weight": SchemaConfig.INITIAL_WEIGHT,
                    "action_count": 0,
                    "session_status": "active",
                    "now": created_at,
                    "attributes": MemoryAPI._serialize_json_attributes(attributes),
                },
            )

            MemoryAPI._insert_audit_event_in_batch(
                batch=batch,
                tenant_id=tenant_id,
                event_type="CREATE_SESSION",
                source_node_id=session_id,
                context=audit_context,
                timestamp=created_at,
            )

        with IdempotencyContext():
            MemoryAPI._run_write_operation(database, _write)

    @staticmethod
    async def add_semantic_fact(
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        attributes: dict[str, Any] | None = None,
        relationship: dict[str, str] | None = None,
        session_id: str | None = None,
        session_action_count: int | None = None,
        source_agent_id: str | None = None,
        source_query_id: str | None = None,
        authorization_scope: AuthorizationScope | None = None,
    ) -> FactResponse:
        """Ingest an entity into Semantic Graph with baseline cognitive weight.

        Args:
            tenant_id: Tenant identifier for isolation.
            entity_type: POLE+O entity type (PERSON, OBJECT, etc.)
            entity_id: Unique entity identifier
            attributes: Entity attributes as JSON
            relationship: Optional relationship to existing node (type, source_id)
            session_id: Session identifier used for durable action counting.
            session_action_count: Cumulative per-session action count.
            source_agent_id: Optional agent identifier for source attribution.
            source_query_id: Optional query identifier for source attribution.
            authorization_scope: Authorization scope for the request.

        Returns:
            FactResponse with entity details

        Raises:
            ValueError: If tenant_id is empty, entity_type is invalid, or entity_id is empty
            RuntimeError: If database write fails
        """
        tenant_id = validate_tenant_id(tenant_id)
        entity_type = validate_entity_type(
            entity_type,
            allowed_entity_types=SchemaConfig.VALID_ENTITY_TYPES,
        )
        entity_id = validate_required_string(entity_id, field_name="entity_id")
        attributes = validate_optional_mapping(attributes, field_name="attributes") or None
        relationship = validate_relationship(relationship)

        detected_contradictions = MemoryAPI._detect_contradictions(
            tenant_id=tenant_id,
            entity_id=entity_id,
            entity_type=entity_type,
            attributes=attributes,
        )
        source_confidence_score = (
            API_DERIVED_SOURCE_CONFIDENCE_SCORE
            if source_agent_id is not None or source_query_id is not None
            else DEFAULT_SOURCE_CONFIDENCE_SCORE
        )

        MemoryAPI._authorize_operation(
            operation="add_semantic_fact",
            tenant_id=tenant_id,
            authorization_scope=authorization_scope,
            node_id=entity_id,
            label=entity_type,
            memory_tier=SchemaConfig.MEMORY_TIER_SEMANTIC,
        )
        if relationship and relationship.get("source_id"):
            source_tier = MemoryAPI._get_node_memory_tier(
                tenant_id,
                relationship["source_id"],
            )
            MemoryAPI._authorize_operation(
                operation="add_semantic_fact.relationship",
                tenant_id=tenant_id,
                authorization_scope=authorization_scope,
                node_id=relationship["source_id"],
                relationship_type=relationship.get("type"),
                memory_tier=source_tier,
            )
            if source_tier == SchemaConfig.MEMORY_TIER_AUDIT:
                msg = "relationship source cannot be an AUDIT tier node"
                raise ValueError(msg)
            if source_tier is None:
                msg = f"source node {relationship['source_id']} not found in tenant"
                raise ValueError(msg)

        created_at = datetime.now(UTC)
        node_attributes = {
            "entity_type": entity_type,
            **(attributes or {}),
        }

        retry_policy = get_retry_policy()
        try:
            await async_retry_with_backoff(
                MemoryAPI._do_add_semantic_fact_batch,
                tenant_id,
                entity_id,
                entity_type,
                node_attributes,
                relationship,
                created_at,
                max_attempts=retry_policy.max_attempts,
                initial_backoff_seconds=retry_policy.initial_backoff_seconds,
                max_backoff_seconds=retry_policy.max_backoff_seconds,
            )
            structured_log(
                logger,
                logging.INFO,
                "add_semantic_fact_completed",
                {
                    "tenant_id": tenant_id,
                    "entity_id": entity_id,
                    "entity_type": entity_type,
                },
            )
        except Exception as e:
            structured_log(
                logger,
                logging.ERROR,
                "add_semantic_fact_exhausted",
                {
                    "tenant_id": tenant_id,
                    "entity_id": entity_id,
                    "attempts": retry_policy.max_attempts,
                },
            )
            msg = f"Failed to add semantic fact after {retry_policy.max_attempts} attempts: {e}"
            raise RuntimeError(msg) from e

        if session_action_count is None and session_id is not None:
            session_action_count = MemoryAPI._increment_session_action_count(
                tenant_id,
                session_id,
            )

        # Update weight on successful creation
        await MemoryAPI._update_weight_on_successful_use(
            tenant_id,
            [entity_id],
            session_action_count=session_action_count,
        )

        return FactResponse(
            tenant_id=tenant_id,
            entity_id=entity_id,
            entity_type=entity_type,
            node_path=f"/{entity_type}/{entity_id}",
            weight=SchemaConfig.INITIAL_WEIGHT,
            created_at=created_at,
            source_confidence_score=source_confidence_score,
            detected_contradictions=detected_contradictions,
            source_agent_id=source_agent_id,
            source_query_id=source_query_id,
        )

    @staticmethod
    async def _do_add_semantic_fact_batch(
        tenant_id: str,
        entity_id: str,
        entity_type: str,
        node_attributes: dict[str, Any],
        relationship: dict[str, str] | None,
        created_at: datetime,
    ) -> None:
        """Execute idempotent semantic fact addition with batch write.

        Args:
            tenant_id: Tenant identifier.
            entity_id: Entity identifier.
            entity_type: Entity type.
            node_attributes: Node attributes.
            relationship: Optional relationship definition.
            created_at: Creation timestamp.

        Raises:
            ValueError: If tenant_id is None or empty — composite PK enforcement.
            Exception: If database write fails (may be retried by caller).
        """
        if not tenant_id or not tenant_id.strip():
            msg = "tenant_id is required for all MemoryNode writes"
            raise ValueError(msg)
        database = SpannerClient.get_database()
        node_sql = """
                INSERT INTO MemoryNode (
                    NodeId, TenantId, MemoryTier, Label, LogOddsWeight,
                    LastAccessed, Attributes, CreatedAt, UpdatedAt
                ) VALUES (
                    @node_id, @tenant_id, @tier, @label, @weight,
                    @now, CAST(@attributes AS JSON), @now, @now
                )
            """

        def _write(batch: SpannerBatchProtocol) -> None:
            batch.execute_update(
                node_sql,
                {
                    "node_id": entity_id,
                    "tenant_id": tenant_id,
                    "tier": SchemaConfig.MEMORY_TIER_SEMANTIC,
                    "label": entity_type,
                    "weight": SchemaConfig.INITIAL_WEIGHT,
                    "now": created_at,
                    "attributes": MemoryAPI._serialize_json_attributes(node_attributes),
                },
            )

            # Create relationship if provided
            if relationship:
                source_id = relationship.get("source_id")
                rel_type = relationship.get("type", "REFERENCES")
                if source_id:
                    edge_id = str(uuid.uuid4())
                    edge_sql = """
                        INSERT INTO MemoryEdge (
                            SourceNodeId, TenantId, EdgeId, DestNodeId, RelType,
                            LogOddsWeight, LastAccessed, CreatedAt, UpdatedAt
                        ) VALUES (
                            @source_id, @tenant_id, @edge_id, @dest_id, @rel_type,
                            @weight, @now, @now, @now
                        )
                    """
                    batch.execute_update(
                        edge_sql,
                        {
                            "source_id": source_id,
                            "tenant_id": tenant_id,
                            "edge_id": edge_id,
                            "dest_id": entity_id,
                            "rel_type": rel_type,
                            "weight": SchemaConfig.INITIAL_WEIGHT,
                            "now": created_at,
                        },
                    )

            MemoryAPI._insert_audit_event_in_batch(
                batch=batch,
                tenant_id=tenant_id,
                event_type="ADD_SEMANTIC_FACT",
                source_node_id=entity_id,
                context={"entity_type": entity_type, "relationship": relationship},
                timestamp=created_at,
            )

        with IdempotencyContext():
            MemoryAPI._run_write_operation(database, _write)

    @staticmethod
    def _detect_contradictions(
        tenant_id: str,
        entity_id: str,
        entity_type: str,
        attributes: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Detect lightweight contradiction signals from entity attributes.

        Args:
            tenant_id: Tenant identifier for the ingest operation.
            entity_id: Entity identifier being evaluated.
            entity_type: Entity type being evaluated.
            attributes: Attributes supplied at ingest time.

        Returns:
            A list of contradiction dictionaries suitable for FactResponse.
        """
        if not attributes:
            return []

        contradictions: list[dict[str, Any]] = []

        conflicting_node_ids = attributes.get("conflicts_with")
        if isinstance(conflicting_node_ids, str):
            conflicting_node_ids = [conflicting_node_ids]
        if isinstance(conflicting_node_ids, (list, tuple, set)):
            normalized_conflicts: list[str] = []
            for raw_node_id in cast("list[object]", list(conflicting_node_ids)):  # type: ignore[arg-type]
                normalized_node_id = str(raw_node_id).strip()
                if normalized_node_id:
                    normalized_conflicts.append(normalized_node_id)
            if normalized_conflicts:
                contradictions.append(
                    {
                        "severity": "high",
                        "detected_by": "explicit_conflicts_with_marker",
                        "reason": (
                            "Attribute conflicts_with explicitly lists conflicting "
                            f"node ids for {entity_type} {entity_id} in tenant {tenant_id}."
                        ),
                        "conflicting_node_ids": normalized_conflicts,
                    }
                )

        is_deprecated = bool(attributes.get("is_deprecated"))
        last_access = attributes.get("last_access")
        if is_deprecated and isinstance(last_access, str):
            try:
                normalized_last_access = last_access.replace("Z", "+00:00")
                last_accessed_at = datetime.fromisoformat(normalized_last_access)
            except ValueError:
                last_accessed_at = None

            if last_accessed_at is not None and (
                datetime.now(tz=UTC) - last_accessed_at <= timedelta(days=RECENT_ACCESS_WINDOW_DAYS)
            ):
                contradictions.append(
                    {
                        "severity": "medium",
                        "detected_by": "value_incompatibility",
                        "reason": (
                            f"Deprecated {entity_type} {entity_id} was recently "
                            f"accessed within {RECENT_ACCESS_WINDOW_DAYS} days."
                        ),
                        "conflicting_node_ids": [entity_id],
                    }
                )

        is_active = attributes.get("is_active")
        status = attributes.get("status")
        if (
            is_active is False
            and isinstance(status, str)
            and status.strip().lower() in ACTIVE_STATUS_VALUES
        ):
            contradictions.append(
                {
                    "severity": "high",
                    "detected_by": "value_incompatibility",
                    "reason": (
                        f"is_active=False conflicts with status='{status}' for "
                        f"{entity_type} {entity_id}."
                    ),
                    "conflicting_node_ids": [entity_id],
                }
            )

        return contradictions

    @staticmethod
    async def record_audit_event(
        tenant_id: str,
        event_type: str,
        source_node_id: str,
        context: dict[str, Any] | None = None,
        authorization_scope: AuthorizationScope | None = None,
    ) -> AuditResponse:
        """Record an immutable audit event in Audit Graph.

        Args:
            tenant_id: Tenant identifier for isolation.
            event_type: Type of audit event
            source_node_id: Node that triggered the event
            context: Event context information
            authorization_scope: Authorization scope for the request.

        Returns:
            AuditResponse with event details

        Raises:
            ValueError: If tenant_id, event_type, or source_node_id is empty or invalid
            RuntimeError: If database write fails after max retries
        """
        tenant_id = validate_tenant_id(tenant_id)
        event_type = validate_required_string(event_type, field_name="event_type")
        source_node_id = validate_required_string(source_node_id, field_name="source_node_id")
        context = validate_optional_mapping(context, field_name="context") or None

        MemoryAPI._authorize_operation(
            operation="record_audit_event",
            tenant_id=tenant_id,
            authorization_scope=authorization_scope,
            node_id=source_node_id,
            label="AUDIT_EVENT",
            memory_tier=SchemaConfig.MEMORY_TIER_AUDIT,
        )

        timestamp = datetime.now(UTC)
        retry_policy = get_retry_policy()

        try:
            audit_response = await async_retry_with_backoff(
                MemoryAPI._do_record_audit_event_batch,
                tenant_id,
                event_type,
                source_node_id,
                context,
                timestamp,
                max_attempts=retry_policy.max_attempts,
                initial_backoff_seconds=retry_policy.initial_backoff_seconds,
                max_backoff_seconds=retry_policy.max_backoff_seconds,
            )
            structured_log(
                logger,
                logging.INFO,
                "record_audit_event_completed",
                {
                    "tenant_id": tenant_id,
                    "event_type": event_type,
                    "source_node_id": source_node_id,
                },
            )
        except Exception as e:
            structured_log(
                logger,
                logging.ERROR,
                "record_audit_event_exhausted",
                {
                    "tenant_id": tenant_id,
                    "event_type": event_type,
                    "source_node_id": source_node_id,
                    "attempts": retry_policy.max_attempts,
                },
            )
            msg = f"Failed to record audit event after {retry_policy.max_attempts} attempts: {e}"
            raise RuntimeError(msg) from e
        else:
            return audit_response

    @staticmethod
    async def _do_record_audit_event_batch(
        tenant_id: str,
        event_type: str,
        source_node_id: str,
        context: dict[str, Any] | None,
        timestamp: datetime,
    ) -> AuditResponse:
        """Execute idempotent audit event recording with batch write.

        Args:
            tenant_id: Tenant identifier.
            event_type: Event type.
            source_node_id: Source node identifier.
            context: Event context.
            timestamp: Event timestamp.

        Returns:
            AuditResponse with event details.

        Raises:
            Exception: If database write fails (may be retried by caller).
        """
        database = SpannerClient.get_database()

        def _write(batch: SpannerBatchProtocol) -> AuditResponse:
            return MemoryAPI._insert_audit_event_in_batch(
                batch=batch,
                tenant_id=tenant_id,
                event_type=event_type,
                source_node_id=source_node_id,
                context=context,
                timestamp=timestamp,
            )

        with IdempotencyContext():
            return MemoryAPI._run_write_operation(database, _write)

    @staticmethod
    def _encode_context_cursor(created_at: datetime, turn_id: str) -> str:
        """Encode a context pagination cursor.

        Args:
            created_at: Turn creation timestamp.
            turn_id: Stable turn identifier.

        Returns:
            str: Encoded cursor value.
        """
        return f"{created_at.isoformat()}{_CONTEXT_CURSOR_SEPARATOR}{turn_id}"

    @staticmethod
    def _decode_context_cursor(cursor: str) -> tuple[datetime, str]:
        """Decode a context pagination cursor.

        Args:
            cursor: Encoded cursor string.

        Returns:
            tuple[datetime, str]: Cursor timestamp and turn identifier.

        Raises:
            ValueError: If cursor format is invalid.
        """
        normalized_cursor = validate_required_string(cursor, field_name="cursor")
        if _CONTEXT_CURSOR_SEPARATOR not in normalized_cursor:
            msg = "cursor must use '<iso_datetime>|<turn_id>' format"
            raise ValueError(msg)

        created_at_raw, turn_id = normalized_cursor.split(_CONTEXT_CURSOR_SEPARATOR, maxsplit=1)
        validated_turn_id = validate_required_string(turn_id, field_name="cursor_turn_id")
        try:
            parsed_created_at = datetime.fromisoformat(created_at_raw)
        except ValueError as error:
            msg = "cursor datetime must be a valid ISO-8601 value"
            raise ValueError(msg) from error

        if parsed_created_at.tzinfo is None:
            parsed_created_at = parsed_created_at.replace(tzinfo=UTC)

        return parsed_created_at, validated_turn_id

    @staticmethod
    async def retrieve_context_window(
        tenant_id: str,
        session_id: str,
        window_size: int = 10,
        cursor: str | None = None,
        session_action_count: int | None = None,
        authorization_scope: AuthorizationScope | None = None,
    ) -> ContextResponse:
        """Retrieve recent session history via GQL with edge metadata.

        Args:
            tenant_id: Tenant identifier for isolation.
            session_id: Session identifier
            window_size: Number of turns to retrieve (1-100)
            cursor: Opaque cursor from previous context page.
            session_action_count: Cumulative per-session action count.
            authorization_scope: Authorization scope for the request.

        Returns:
            ContextResponse with context turns

        Raises:
            ValueError: If tenant_id is empty, session_id is empty, or window_size is invalid
            RuntimeError: If database query fails
        """
        tenant_id = validate_tenant_id(tenant_id)
        session_id = validate_required_string(session_id, field_name="session_id")
        window_size = validate_window_size(window_size)
        cursor_created_at: datetime | None = None
        cursor_turn_id: str | None = None
        if cursor is not None:
            cursor_created_at, cursor_turn_id = MemoryAPI._decode_context_cursor(cursor)

        limit_plus_one = window_size + 1

        MemoryAPI._authorize_operation(
            operation="retrieve_context_window",
            tenant_id=tenant_id,
            authorization_scope=authorization_scope,
            node_id=session_id,
            label="Session",
            memory_tier=SchemaConfig.MEMORY_TIER_CONTEXT,
        )

        retrieved_at = datetime.now(UTC)

        # GQL query to retrieve context window with tenant isolation
        # Pattern: (Session)-[HAS_TURN]->(Turn)
        # Ordered by creation timestamp DESC, limited by window_size
        gql_query = """
            MATCH p = (s:Node)-[e]->(t:Node)
            WHERE s.TenantId = @tenant_id
              AND s.NodeId = @session_id
              AND s.MemoryTier = 'CONTEXT'
              AND t.MemoryTier = 'CONTEXT'
                            AND (
                                @cursor_created_at IS NULL
                                OR t.CreatedAt < @cursor_created_at
                                OR (t.CreatedAt = @cursor_created_at AND t.NodeId < @cursor_turn_id)
                            )
            RETURN t.NodeId, t.Label, t.Attributes, t.LogOddsWeight, t.CreatedAt, e.RelType
                        ORDER BY t.CreatedAt DESC, t.NodeId DESC
                        LIMIT @limit_plus_one
        """

        sql_fallback_query = """
            SELECT
                t.NodeId,
                t.Label,
                t.Attributes,
                t.LogOddsWeight,
                t.CreatedAt,
                e.RelType
            FROM MemoryNode AS s
            JOIN MemoryEdge AS e
                ON e.SourceNodeId = s.NodeId
                AND e.TenantId = @tenant_id
            JOIN MemoryNode AS t
                ON t.NodeId = e.DestNodeId
                AND t.TenantId = @tenant_id
            WHERE s.TenantId = @tenant_id
              AND s.NodeId = @session_id
              AND s.MemoryTier = 'CONTEXT'
              AND t.MemoryTier = 'CONTEXT'
                            AND (
                                @cursor_created_at IS NULL
                                OR t.CreatedAt < @cursor_created_at
                                OR (t.CreatedAt = @cursor_created_at AND t.NodeId < @cursor_turn_id)
                            )
                        ORDER BY t.CreatedAt DESC, t.NodeId DESC
                        LIMIT @limit_plus_one
        """

        try:
            database = SpannerClient.get_database()
            turns: list[ContextTurn] = []
            total_weight_sum = 0.0

            query_params = {
                "tenant_id": tenant_id,
                "session_id": session_id,
                "window_size": window_size,
                "cursor_created_at": cursor_created_at,
                "cursor_turn_id": cursor_turn_id,
                "limit_plus_one": limit_plus_one,
            }
            try:
                results = execute_sql_rows(database, gql_query, query_params)
            except Exception as error:
                if not _is_match_query_unsupported(error):
                    raise
                structured_log(
                    logger,
                    logging.INFO,
                    "retrieve_context_window_match_unsupported",
                    {
                        "tenant_id": tenant_id,
                        "session_id": session_id,
                    },
                )
                results = execute_sql_rows(database, sql_fallback_query, query_params)

            materialized_rows = list(results)
            has_more = len(materialized_rows) > window_size
            rows_to_return = materialized_rows[:window_size]

            for row in rows_to_return:
                turn_id, label, attributes, weight, created_at, _rel_type = row
                turn_id_str = str(turn_id)
                role = str(label)
                normalized_created_at = (
                    created_at if isinstance(created_at, datetime) else retrieved_at
                )
                turn = ContextTurn(
                    tenant_id=tenant_id,
                    turn_id=turn_id_str,
                    node_id=turn_id_str,
                    role=role,
                    content=str(attributes),
                    weight=(
                        float(weight)
                        if isinstance(weight, (int, float))
                        else SchemaConfig.INITIAL_WEIGHT
                    ),
                    created_at=normalized_created_at,
                )
                turns.append(turn)
                total_weight_sum += turn.weight

            next_cursor: str | None = None
            if has_more and turns:
                last_turn = turns[-1]
                next_cursor = MemoryAPI._encode_context_cursor(
                    created_at=last_turn.created_at,
                    turn_id=last_turn.turn_id,
                )

            # Log retrieval to audit
            await MemoryAPI.record_audit_event(
                tenant_id,
                "RETRIEVE_CONTEXT_WINDOW",
                session_id,
                {"window_size": window_size, "turns_retrieved": len(turns)},
                authorization_scope=authorization_scope,
            )

            # Update weights on successful retrieval
            turn_ids = [turn.turn_id for turn in turns]
            if turn_ids:
                if session_action_count is None:
                    session_action_count = MemoryAPI._increment_session_action_count(
                        tenant_id,
                        session_id,
                    )
                await MemoryAPI._update_weight_on_successful_use(
                    tenant_id,
                    turn_ids,
                    memory_tier=SchemaConfig.MEMORY_TIER_CONTEXT,
                    session_action_count=session_action_count,
                )

            return ContextResponse(
                tenant_id=tenant_id,
                session_id=session_id,
                turns=turns,
                next_cursor=next_cursor,
                has_more=has_more,
                total_weight_sum=total_weight_sum,
                retrieved_at=retrieved_at,
            )
        except Exception as e:
            msg = f"Failed to retrieve context window: {e}"
            raise RuntimeError(msg) from e

    @staticmethod
    def _coerce_json_object(raw_value: object) -> dict[str, Any]:
        """Normalize SQL JSON fields into dictionaries.

        Args:
            raw_value: Raw value returned by Spanner for JSON columns.

        Returns:
            dict[str, Any]: Parsed JSON object or empty dictionary.
        """
        if isinstance(raw_value, dict):
            return dict(cast("dict[str, Any]", raw_value))
        if isinstance(raw_value, str):
            try:
                parsed = json.loads(raw_value)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, dict):
                return dict(cast("dict[str, Any]", parsed))
        return {}

    @staticmethod
    async def export_graph_snapshot(
        tenant_id: str,
        limit: int = 1000,
        authorization_scope: AuthorizationScope | None = None,
    ) -> GraphExportResponse:
        """Export a tenant-scoped graph snapshot as JSON-LD entries.

        Args:
            tenant_id: Tenant identifier for isolation.
            limit: Maximum number of nodes and edges to export per tier.
            authorization_scope: Authorization scope for the request.

        Returns:
            GraphExportResponse: JSON-LD graph snapshot envelope.

        Raises:
            ValueError: If tenant or limit are invalid.
            RuntimeError: If database reads fail.
        """
        tenant_id = validate_tenant_id(tenant_id)
        if limit < 1:
            msg = "limit must be greater than 0"
            raise ValueError(msg)

        MemoryAPI._authorize_operation(
            operation="export_graph_snapshot",
            tenant_id=tenant_id,
            authorization_scope=authorization_scope,
            node_id=tenant_id,
            label="GraphSnapshot",
            memory_tier=SchemaConfig.MEMORY_TIER_SEMANTIC,
        )

        node_query = """
            SELECT NodeId, Label, MemoryTier, LogOddsWeight, Attributes
            FROM MemoryNode
            WHERE TenantId = @tenant_id
            ORDER BY CreatedAt DESC, NodeId DESC
            LIMIT @limit
        """
        edge_query = """
            SELECT EdgeId, SourceNodeId, DestNodeId, RelType, LogOddsWeight, Attributes
            FROM MemoryEdge
            WHERE TenantId = @tenant_id
            ORDER BY CreatedAt DESC, EdgeId DESC
            LIMIT @limit
        """

        try:
            database = SpannerClient.get_database()
            params = {
                "tenant_id": tenant_id,
                "limit": limit,
            }
            node_rows = execute_sql_rows(database, node_query, params)
            edge_rows = execute_sql_rows(database, edge_query, params)
        except Exception as error:
            msg = f"Failed to export graph snapshot: {error}"
            raise RuntimeError(msg) from error

        exported_nodes: list[GraphExportNode] = []
        exported_edges: list[GraphExportEdge] = []

        for row in node_rows:
            node_id, label, memory_tier, weight, attributes = row
            exported_nodes.append(
                GraphExportNode(
                    id=f"node:{node_id}",
                    type=str(label) if label is not None else "Node",
                    tenant_id=tenant_id,
                    memory_tier=str(memory_tier) if memory_tier is not None else "UNKNOWN",
                    label=str(label) if label is not None else "Node",
                    weight=float(weight) if isinstance(weight, (float, int)) else 0.0,
                    attributes=MemoryAPI._coerce_json_object(attributes),
                )
            )

        for row in edge_rows:
            edge_id, source_node_id, destination_node_id, rel_type, weight, attributes = row
            exported_edges.append(
                GraphExportEdge(
                    id=f"edge:{edge_id}",
                    tenant_id=tenant_id,
                    relationship_type=str(rel_type) if rel_type is not None else "RELATED_TO",
                    source_node_id=str(source_node_id),
                    destination_node_id=str(destination_node_id),
                    weight=float(weight) if isinstance(weight, (float, int)) else 0.0,
                    attributes=MemoryAPI._coerce_json_object(attributes),
                )
            )

        await MemoryAPI.record_audit_event(
            tenant_id=tenant_id,
            event_type="GRAPH_EXPORT",
            source_node_id=tenant_id,
            context={
                "limit": limit,
                "node_count": len(exported_nodes),
                "edge_count": len(exported_edges),
            },
            authorization_scope=authorization_scope,
        )

        return GraphExportResponse(
            context={
                "@vocab": "https://agent-memory-graph.local/vocab#",
                "tenant_id": "https://agent-memory-graph.local/schema/tenant_id",
                "memory_tier": "https://agent-memory-graph.local/schema/memory_tier",
                "relationship_type": "https://agent-memory-graph.local/schema/relationship_type",
            },
            graph=[*exported_nodes, *exported_edges],
            tenant_id=tenant_id,
            node_count=len(exported_nodes),
            edge_count=len(exported_edges),
            exported_at=datetime.now(UTC),
        )

    @staticmethod
    async def _do_weight_update_batch(
        tenant_id: str,
        node_ids: list[str],
        memory_tier: str,
        bayes_factor_ln: float,
    ) -> None:
        """Execute weight update batch operation (retryable).

        This is a separate method to isolate the database operation for retry logic.

        Args:
            tenant_id: Tenant identifier.
            node_ids: Node IDs to update.
            memory_tier: Memory tier for the update.
            bayes_factor_ln: Log-odds delta (ln(BF)).

        Raises:
            ValueError: If tenant_id is None or empty — composite PK enforcement.
            Exception: Any exception from Spanner (to be retried).
        """
        if not tenant_id or not tenant_id.strip():
            msg = "tenant_id is required for all MemoryNode writes"
            raise ValueError(msg)
        sql = """
            UPDATE MemoryNode
            SET LogOddsWeight = LogOddsWeight + @delta,
                LastAccessed = CURRENT_TIMESTAMP(),
                UpdatedAt = CURRENT_TIMESTAMP()
            WHERE TenantId = @tenant_id
              AND NodeId IN UNNEST(@node_ids)
              AND MemoryTier = @tier
        """

        database = SpannerClient.get_database()

        def _write(batch: SpannerBatchProtocol) -> None:
            batch.execute_update(
                sql,
                {
                    "tenant_id": tenant_id,
                    "delta": bayes_factor_ln,
                    "node_ids": node_ids,
                    "tier": memory_tier,
                },
            )

        MemoryAPI._run_write_operation(database, _write)

    @staticmethod
    async def _update_weight_on_successful_use(
        tenant_id: str,
        node_ids: list[str],
        memory_tier: str = SchemaConfig.MEMORY_TIER_SEMANTIC,
        session_action_count: int | None = None,
    ) -> None:
        """Update cognitive weights on successful use (confirmation bias).

        Internal method: increments LogOddsWeight by ln(BF) where BF=1.25.

        Args:
            tenant_id: Tenant identifier for isolation.
            node_ids: List of node IDs to update
            memory_tier: Target tier for update.
            session_action_count: Cumulative per-session action count.

        Raises:
            ValueError: If tenant_id is empty, memory_tier is invalid, or tier is immutable.
            WeightUpdateFailed: If update fails after retries.
        """
        tenant_id = validate_tenant_id(tenant_id)
        if not node_ids:
            return

        node_ids = [validate_required_string(node_id, field_name="node_id") for node_id in node_ids]

        if memory_tier not in SchemaConfig.VALID_MEMORY_TIERS:
            msg = f"invalid memory_tier. Must be one of: {SchemaConfig.VALID_MEMORY_TIERS}"
            raise ValueError(msg)

        if memory_tier == SchemaConfig.MEMORY_TIER_AUDIT:
            try:
                MemoryAPI._enforce_audit_append_only("UPDATE")
            except PermissionError:
                # Keep MemoryAPI contract stable while still enforcing append-only checks.
                structured_log(
                    logger,
                    logging.WARNING,
                    "audit_immutability_guard_triggered",
                    {
                        "memory_tier": memory_tier,
                    },
                )
            msg = "audit tier is append-only and cannot be updated"
            raise ValueError(msg)

        weighting_policy = settings.governance.weighting

        # Skip weighting entirely if disabled
        if not weighting_policy.enabled:
            logger.debug("weighting_disabled tenant_id=%s memory_tier=%s", tenant_id, memory_tier)
            return

        # Skip weighting if action count below threshold (when enabled)
        if session_action_count is not None and not weighting_policy.should_trigger(
            session_action_count
        ):
            structured_log(
                logger,
                logging.INFO,
                "weight_update_skipped",
                {
                    "tenant_id": tenant_id,
                    "memory_tier": memory_tier,
                    "action_count": session_action_count,
                    "threshold": weighting_policy.action_count_threshold,
                },
            )
            return

        # Bayesian log-odds update: ln(1.25) ≈ 0.223
        bayes_factor_ln = math.log(SchemaConfig.BAYES_FACTOR_SUCCESS)
        retry_policy = get_retry_policy()

        try:
            # Execute with retry logic
            await async_retry_with_backoff(
                MemoryAPI._do_weight_update_batch,
                tenant_id,
                node_ids,
                memory_tier,
                bayes_factor_ln,
                max_attempts=retry_policy.max_attempts,
                initial_backoff_seconds=retry_policy.initial_backoff_seconds,
                max_backoff_seconds=retry_policy.max_backoff_seconds,
            )
            structured_log(
                logger,
                logging.INFO,
                "weight_update_completed",
                {
                    "tenant_id": tenant_id,
                    "node_count": len(node_ids),
                    "memory_tier": memory_tier,
                },
            )
        except Exception as e:
            structured_log(
                logger,
                logging.ERROR,
                "weight_update_exhausted",
                {
                    "tenant_id": tenant_id,
                    "node_count": len(node_ids),
                    "memory_tier": memory_tier,
                    "attempts": retry_policy.max_attempts,
                },
            )
            raise WeightUpdateFailedError(
                tenant_id=tenant_id,
                node_ids=node_ids,
                attempts=retry_policy.max_attempts,
                last_error=e,
            ) from e

    @staticmethod
    def _increment_session_action_count(tenant_id: str, session_id: str) -> int:
        """Atomically increment and return the cumulative per-session action counter.

        Uses a single atomic SQL UPDATE (SET count = count + 1) with no prior SELECT
        read. This eliminates the read-modify-write race condition where two concurrent
        callers could both read 0, both write 1, and silently drop one increment.

        Raises:
            ValueError: If tenant_id is None or empty — composite PK enforcement.
            RuntimeError: If the database update fails.
        """
        if not tenant_id or not tenant_id.strip():
            msg = "tenant_id is required for all MemoryNode writes"
            raise ValueError(msg)
        tenant_id = validate_tenant_id(tenant_id)
        session_id = validate_required_string(session_id, field_name="session_id")

        update_sql = """
            UPDATE MemoryNode
            SET SessionActionCount = SessionActionCount + 1,
                UpdatedAt = CURRENT_TIMESTAMP()
            WHERE TenantId = @tenant_id
              AND NodeId = @session_id
              AND MemoryTier = @tier
        """

        database = SpannerClient.get_database()

        def _transaction(transaction: SpannerTransactionProtocol) -> int:
            """Execute single atomic UPDATE for action counter — no read required.

            Args:
                transaction: Active Spanner transaction.

            Returns:
                Row count updated (1 on success, 0 if session not found).
            """
            # Atomic increment — no SELECT read, no race condition possible.
            return transaction.execute_update(
                update_sql,
                {
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                    "tier": SchemaConfig.MEMORY_TIER_CONTEXT,
                },
            )

        try:
            return database.run_in_transaction(_transaction)
        except Exception as error:
            msg = f"Failed to increment session action count: {error}"
            raise RuntimeError(msg) from error
