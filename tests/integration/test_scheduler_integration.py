"""Integration tests for internal scheduler endpoints and job configuration."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import CognitiveWeighting, app
from src.memory.cognitive_weighting import CloudSchedulerJob

HTTP_OK = 200
DECAY_RATE = 0.05
DECAY_UPDATED_NODES = 7
PRUNE_THRESHOLD = 0.30
PRUNE_UPDATED_NODES = 4
SCHEDULER_HEADERS = {
    "X-CloudScheduler-JobName": "amg-decay-weights-daily",
    "X-CloudScheduler-ScheduleTime": "2026-07-01T02:00:00Z",
}


class TestSchedulerInternalEndpoints:
    """Contract tests for internal Cloud Scheduler-triggered endpoints."""

    def test_decay_endpoint_invokes_temporal_decay(self) -> None:
        """Decay endpoint should delegate to CognitiveWeighting with request payload."""
        original_decay = CognitiveWeighting.decay_weights_temporal
        observed_decay_rates: list[float] = []

        async def _decay_stub(*, decay_rate: float) -> int:
            observed_decay_rates.append(decay_rate)
            return DECAY_UPDATED_NODES

        CognitiveWeighting.decay_weights_temporal = _decay_stub

        try:
            client = TestClient(app)
            response = client.post("/internal/decay-weights", json={"decay_rate": DECAY_RATE})

            assert response.status_code == HTTP_OK
            payload = response.json()
            assert payload["status"] == "ok"
            assert payload["operation"] == "decay_weights"
            assert payload["updated_nodes"] == DECAY_UPDATED_NODES
            assert payload["decay_rate"] == DECAY_RATE
            assert observed_decay_rates == [DECAY_RATE]
        finally:
            CognitiveWeighting.decay_weights_temporal = original_decay

    def test_prune_endpoint_invokes_threshold_pruning(self) -> None:
        """Prune endpoint should delegate to CognitiveWeighting with request payload."""
        original_prune = CognitiveWeighting.prune_weights_below_threshold
        observed_thresholds: list[float] = []

        async def _prune_stub(*, threshold: float) -> int:
            observed_thresholds.append(threshold)
            return PRUNE_UPDATED_NODES

        CognitiveWeighting.prune_weights_below_threshold = _prune_stub

        try:
            client = TestClient(app)
            response = client.post("/internal/prune-weights", json={"threshold": PRUNE_THRESHOLD})

            assert response.status_code == HTTP_OK
            payload = response.json()
            assert payload["status"] == "ok"
            assert payload["operation"] == "prune_weights"
            assert payload["updated_nodes"] == PRUNE_UPDATED_NODES
            assert payload["threshold"] == PRUNE_THRESHOLD
            assert observed_thresholds == [PRUNE_THRESHOLD]
        finally:
            CognitiveWeighting.prune_weights_below_threshold = original_prune

    def test_decay_endpoint_accepts_cloud_scheduler_headers(self) -> None:
        """Decay endpoint should preserve behavior when invoked by Cloud Scheduler headers."""
        original_decay = CognitiveWeighting.decay_weights_temporal

        async def _decay_stub(*, decay_rate: float) -> int:
            return DECAY_UPDATED_NODES

        CognitiveWeighting.decay_weights_temporal = _decay_stub

        try:
            client = TestClient(app)
            response = client.post(
                "/internal/decay-weights",
                json={"decay_rate": DECAY_RATE},
                headers=SCHEDULER_HEADERS,
            )

            assert response.status_code == HTTP_OK
            payload = response.json()
            assert payload["status"] == "ok"
            assert payload["operation"] == "decay_weights"
            assert payload["updated_nodes"] == DECAY_UPDATED_NODES
        finally:
            CognitiveWeighting.decay_weights_temporal = original_decay


class TestSchedulerJobConfiguration:
    """Tests for scheduler config URI wiring against internal endpoints."""

    def test_job_config_uses_internal_weight_endpoints(self) -> None:
        """Scheduler config should target the internal decay/prune endpoints."""
        config = CloudSchedulerJob.get_job_config("https://example.run.app")

        decay_uri = config["decay_job"]["http_target"]["uri"]
        prune_uri = config["pruning_job"]["http_target"]["uri"]

        assert decay_uri == "https://example.run.app/internal/decay-weights"
        assert prune_uri == "https://example.run.app/internal/prune-weights"
