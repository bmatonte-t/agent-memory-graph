"""Integration tests for internal scheduler endpoints and job configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.api.main import app
from src.memory.cognitive_weighting import CloudSchedulerJob

if TYPE_CHECKING:
    import pytest

HTTP_OK = 200
DECAY_RATE = 0.05
DECAY_UPDATED_NODES = 7
PRUNE_THRESHOLD = 0.30
PRUNE_UPDATED_NODES = 4


class TestSchedulerInternalEndpoints:
    """Contract tests for internal Cloud Scheduler-triggered endpoints."""

    def test_decay_endpoint_invokes_temporal_decay(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Decay endpoint should delegate to CognitiveWeighting with request payload."""
        decay_mock = AsyncMock(return_value=DECAY_UPDATED_NODES)
        monkeypatch.setattr("src.api.main.CognitiveWeighting.decay_weights_temporal", decay_mock)

        client = TestClient(app)
        response = client.post("/internal/decay-weights", json={"decay_rate": DECAY_RATE})

        assert response.status_code == HTTP_OK
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["operation"] == "decay_weights"
        assert payload["updated_nodes"] == DECAY_UPDATED_NODES
        assert payload["decay_rate"] == DECAY_RATE
        decay_mock.assert_awaited_once_with(decay_rate=DECAY_RATE)

    def test_prune_endpoint_invokes_threshold_pruning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Prune endpoint should delegate to CognitiveWeighting with request payload."""
        prune_mock = AsyncMock(return_value=PRUNE_UPDATED_NODES)
        monkeypatch.setattr(
            "src.api.main.CognitiveWeighting.prune_weights_below_threshold",
            prune_mock,
        )

        client = TestClient(app)
        response = client.post("/internal/prune-weights", json={"threshold": PRUNE_THRESHOLD})

        assert response.status_code == HTTP_OK
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["operation"] == "prune_weights"
        assert payload["updated_nodes"] == PRUNE_UPDATED_NODES
        assert payload["threshold"] == PRUNE_THRESHOLD
        prune_mock.assert_awaited_once_with(threshold=PRUNE_THRESHOLD)


class TestSchedulerJobConfiguration:
    """Tests for scheduler config URI wiring against internal endpoints."""

    def test_job_config_uses_internal_weight_endpoints(self) -> None:
        """Scheduler config should target the internal decay/prune endpoints."""
        config = CloudSchedulerJob.get_job_config("https://example.run.app")

        decay_uri = config["decay_job"]["http_target"]["uri"]
        prune_uri = config["pruning_job"]["http_target"]["uri"]

        assert decay_uri == "https://example.run.app/internal/decay-weights"
        assert prune_uri == "https://example.run.app/internal/prune-weights"
