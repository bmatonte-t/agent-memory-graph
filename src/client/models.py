"""Session management for client connection lifecycle."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class ClientSession:
    """Encapsulates a client-to-server session lifecycle."""

    def __init__(self, session_id: str | None = None, agent_id: str | None = None) -> None:
        """Initialize a session.

        Args:
            session_id: Optional session ID; auto-generated if omitted.
            agent_id: Optional agent identifier for audit trails.
        """
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"
        self.agent_id = agent_id
        self.created_at = datetime.now(UTC)
        self.request_count = 0
        self.tokens_used = 0

    def increment_request(self, token_count: int = 0) -> None:
        """Record a request execution.

        Args:
            token_count: Tokens consumed in this request.
        """
        self.request_count += 1
        self.tokens_used += token_count

    def to_dict(self) -> dict[str, str | int]:
        """Export session metadata as dict."""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id or "unknown",
            "created_at": self.created_at.isoformat(),
            "request_count": self.request_count,
            "tokens_used": self.tokens_used,
        }
