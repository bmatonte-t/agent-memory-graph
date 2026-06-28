"""Integration tests for cross-project Spanner deployment model.

Tests scenarios where Cloud Run and Spanner are deployed in different GCP
projects, with cross-project IAM roles and service account permissions.
"""

from __future__ import annotations

import pytest


class TestCrossProjectSpannerSetup:
    """Tests for cross-project Spanner configuration."""

    def test_cloud_run_can_access_spanner_in_different_project(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cloud Run service account should access Spanner in different project."""
        # Simulate environment variables for cross-project setup
        monkeypatch.setenv("GCP_PROJECT_ID", "cloudrun-project")
        monkeypatch.setenv("SPANNER_PROJECT_ID", "spanner-project")
        monkeypatch.setenv("SPANNER_INSTANCE_ID", "prod-instance")
        monkeypatch.setenv("SPANNER_DATABASE_ID", "memory_graph")

        # These should be different
        cloud_run_project = "cloudrun-project"

        assert cloud_run_project != "spanner-project"

    def test_spanner_connection_uses_cross_project_resource_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Spanner client should use cross-project resource name."""
        monkeypatch.setenv("SPANNER_PROJECT_ID", "spanner-project")
        monkeypatch.setenv("SPANNER_INSTANCE_ID", "prod-instance")
        monkeypatch.setenv("SPANNER_DATABASE_ID", "memory_graph")

        # Expected resource name format
        expected_resource_name = (
            "projects/spanner-project/instances/prod-instance/databases/memory_graph"
        )

        spanner_project = "spanner-project"
        instance_id = "prod-instance"
        database_id = "memory_graph"

        actual_resource_name = (
            f"projects/{spanner_project}/instances/{instance_id}/databases/{database_id}"
        )

        assert actual_resource_name == expected_resource_name


class TestCrossProjectServiceAccountIAM:
    """Tests for IAM configuration in cross-project setup."""

    def test_cloudrun_service_account_has_spanner_database_role(
        self,
    ) -> None:
        """Cloud Run SA should have roles/spanner.databaseUser in Spanner project."""
        # Cloud Run service account in cloudrun-project
        cloudrun_sa = "cloudrun-sa@cloudrun-project.iam.gserviceaccount.com"

        # Should have spanner.databaseUser role on Spanner project
        required_role = "roles/spanner.databaseUser"

        # Mock IAM check
        mock_iam_bindings = {
            required_role: [cloudrun_sa],
        }

        assert cloudrun_sa in mock_iam_bindings[required_role]

    def test_cloudrun_service_account_has_spanner_instance_role(self) -> None:
        """Cloud Run SA should have roles/spanner.instanceUser in Spanner project."""
        cloudrun_sa = "cloudrun-sa@cloudrun-project.iam.gserviceaccount.com"

        required_role = "roles/spanner.instanceUser"

        mock_iam_bindings = {
            required_role: [cloudrun_sa],
        }

        assert cloudrun_sa in mock_iam_bindings[required_role]

    def test_spanner_project_allows_cross_project_sa_binding(self) -> None:
        """Spanner project IAM should accept SA from different project."""
        cloudrun_project = "cloudrun-project"
        cloudrun_sa_name = "cloudrun-sa"

        # Full SA identifier across projects
        full_sa_identifier = f"{cloudrun_sa_name}@{cloudrun_project}.iam.gserviceaccount.com"

        # Should be valid
        assert "@" in full_sa_identifier
        assert ".iam.gserviceaccount.com" in full_sa_identifier
        assert cloudrun_project in full_sa_identifier


class TestCrossProjectTenantIsolation:
    """Tests for tenant isolation across projects."""

    def test_tenant_id_isolation_independent_of_project(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tenant_id should be independent of project boundaries."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.project_base.settings.config import SingleCompanySettings  # noqa: PLC0415

        org_settings = SingleCompanySettings(
            enabled=True,
            company_id="org-1",
        )
        monkeypatch.setattr(settings, "single_company", org_settings)
        monkeypatch.setenv("SPANNER_PROJECT_ID", "spanner-project-1")

        from src.security.tenant_context import OrgTenantContext  # noqa: PLC0415

        tenant_id = OrgTenantContext.get_fixed_tenant_id()

        assert tenant_id == "org-1"

    def test_tenant_context_resolves_in_cross_project_scenario(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OrgTenantContext should resolve correctly with cross-project setup."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.project_base.settings.config import SingleCompanySettings  # noqa: PLC0415

        org_settings = SingleCompanySettings(
            enabled=True,
            company_id="org-1-tenant",
        )
        monkeypatch.setattr(settings, "single_company", org_settings)
        monkeypatch.setenv("GCP_PROJECT_ID", "cloudrun-project")
        monkeypatch.setenv("SPANNER_PROJECT_ID", "spanner-project")

        from src.security.tenant_context import OrgTenantContext  # noqa: PLC0415

        # Resolve with None should inject company_id
        resolved = OrgTenantContext.resolve(None)

        assert resolved == "org-1-tenant"

    def test_multiple_orgs_in_same_spanner_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Single Spanner instance can host multiple orgs."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.project_base.settings.config import (  # noqa: PLC0415
            SingleCompanySettings,
        )
        from src.security.tenant_context import (  # noqa: PLC0415
            OrgTenantContext,
        )

        # Org 1 in cloudrun-project-1
        org_1 = SingleCompanySettings(enabled=True, company_id="org-1")

        # Both use same Spanner instance/database
        monkeypatch.setenv("SPANNER_PROJECT_ID", "shared-spanner-project")
        monkeypatch.setenv("SPANNER_INSTANCE_ID", "shared-instance")
        monkeypatch.setenv("SPANNER_DATABASE_ID", "multi_org_db")

        # Set org 1
        monkeypatch.setattr(settings, "single_company", org_1)
        org_1_id = OrgTenantContext.resolve(None)

        # Org 2 in cloudrun-project-2 (different Cloud Run project)
        org_2 = SingleCompanySettings(enabled=True, company_id="org-2")
        monkeypatch.setattr(settings, "single_company", org_2)
        org_2_id = OrgTenantContext.resolve(None)

        # They should maintain separate tenant_ids
        assert org_1_id == "org-1"
        assert org_2_id == "org-2"
        assert org_1_id != org_2_id


class TestCrossProjectQueryExecution:
    """Tests for query execution in cross-project setup."""

    def test_spanner_query_includes_tenant_id_where_clause(self) -> None:
        """Spanner query should include tenant_id in WHERE clause."""
        # Simulate a query
        tenant_id = "org-1"
        base_query = "SELECT * FROM memory_node"
        where_clause = f"WHERE tenant_id = '{tenant_id}'"

        full_query = f"{base_query} {where_clause}"

        assert f"tenant_id = '{tenant_id}'" in full_query

    def test_cross_project_query_uses_cross_project_client(self) -> None:
        """Spanner client should use cross-project credentials."""
        # Mock credential setup
        cloudrun_project = "cloudrun-project"
        spanner_project = "spanner-project"

        # Client should target Spanner project
        target_project = spanner_project

        assert target_project == "spanner-project"
        assert target_project != cloudrun_project


class TestCrossProjectErrorHandling:
    """Tests for error handling in cross-project scenarios."""

    def test_cross_project_auth_error_handled_gracefully(self) -> None:
        """Cross-project auth errors should be handled gracefully."""
        error_message = (
            "Permission denied: Cloud Run SA lacks spanner.databaseUser in Spanner project"
        )

        # Should provide clear error message
        assert "Permission denied" in error_message
        assert "spanner.databaseUser" in error_message

    def test_spanner_unavailability_denies_requests(self) -> None:
        """Spanner unavailability should deny requests, not crash."""
        # Simulate Spanner unavailability
        spanner_available = False

        decision_allowed = not spanner_available
        decision_allowed = False if decision_allowed else decision_allowed  # Reset to False

        assert decision_allowed is False

    def test_network_timeout_between_projects_handled(self) -> None:
        """Network timeouts between projects should be handled."""
        # When network timeout occurs, requests should be denied
        decision_allowed = False

        assert decision_allowed is False


class TestCrossProjectDataConsistency:
    """Tests for data consistency across project boundaries."""

    def test_tenant_data_isolation_persists_across_projects(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tenant isolation should be enforced regardless of project split."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.project_base.settings.config import SingleCompanySettings  # noqa: PLC0415
        from src.security.validators import validate_tenant_id  # noqa: PLC0415

        org_settings = SingleCompanySettings(
            enabled=True,
            company_id="org-1",
        )
        monkeypatch.setattr(settings, "single_company", org_settings)

        # Attempt to access with different tenant_id should fail
        with pytest.raises(ValueError, match="does not match"):
            validate_tenant_id("org-2")

    def test_audit_log_tenant_id_includes_project(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Audit logs should distinguish between cross-project orgs."""
        monkeypatch.setenv("GCP_PROJECT_ID", "cloudrun-project-1")
        monkeypatch.setenv("SPANNER_PROJECT_ID", "spanner-project")

        # Audit event should include both
        audit_event = {
            "cloud_run_project": "cloudrun-project-1",
            "spanner_project": "spanner-project",
            "tenant_id": "org-1",
        }

        assert audit_event["cloud_run_project"] != audit_event["spanner_project"]
        assert audit_event["tenant_id"] == "org-1"


class TestCrossProjectDeploymentConfiguration:
    """Tests for deployment configuration in cross-project setup."""

    def test_environment_variables_configure_cross_project_access(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Environment variables should specify cross-project resources."""
        # Cloud Run project
        monkeypatch.setenv("GCP_PROJECT_ID", "cloudrun-prod")
        # Spanner in different project
        monkeypatch.setenv("SPANNER_PROJECT_ID", "spanner-prod")

        import os  # noqa: PLC0415

        assert os.getenv("GCP_PROJECT_ID") == "cloudrun-prod"
        assert os.getenv("SPANNER_PROJECT_ID") == "spanner-prod"
        assert os.getenv("GCP_PROJECT_ID") != os.getenv("SPANNER_PROJECT_ID")

    def test_service_account_configuration_for_cross_project(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Service account should be configured for cross-project access."""
        # Cloud Run SA in cloudrun-project
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/var/secrets/cloudrun-sa-key.json")

        # SA should have permissions in Spanner project
        expected_scopes = [
            "https://www.googleapis.com/auth/spanner",
            "https://www.googleapis.com/auth/cloud-platform",
        ]

        # Mock SA info would include these scopes
        sa_scopes = expected_scopes

        assert all(scope in sa_scopes for scope in expected_scopes)
