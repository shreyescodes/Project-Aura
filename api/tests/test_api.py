from fastapi.testclient import TestClient

from aura_api.domain import MANAGED_TAG, ResourceUsage, Tier
from tests.conftest import API_KEY
from tests.fakes import FakeCloudGateway

PROBLEM = "application/problem+json"


class TestAuthentication:
    def test_missing_key_is_rejected(self, client: TestClient) -> None:
        response = client.get("/v1/tenants", headers={"X-API-Key": ""})

        assert response.status_code == 401
        assert response.headers["content-type"] == PROBLEM

    def test_wrong_key_is_rejected(self, client: TestClient) -> None:
        response = client.get("/v1/tenants", headers={"X-API-Key": "nope"})

        assert response.status_code == 401

    def test_any_configured_key_is_accepted(self, client: TestClient) -> None:
        assert client.get("/v1/tenants", headers={"X-API-Key": API_KEY}).status_code == 200
        assert client.get("/v1/tenants", headers={"X-API-Key": "rotated-key"}).status_code == 200

    def test_operational_endpoints_need_no_key(self, client: TestClient) -> None:
        response = client.get("/healthz", headers={"X-API-Key": ""})

        assert response.status_code == 200


class TestTenantLifecycle:
    def test_create_get_update_delete(self, client: TestClient, gateway: FakeCloudGateway) -> None:
        gateway.add_user("alice")

        created = client.post(
            "/v1/tenants", json={"name": "acme", "tier": "small", "members": ["alice"]}
        )
        assert created.status_code == 201
        assert created.headers["location"] == "/v1/tenants/acme"
        body = created.json()
        assert body["tier"] == "small"
        assert body["quotas"]["instances"] == 10
        assert body["network"]["cidr"] == "192.168.100.0/24"

        fetched = client.get("/v1/tenants/acme")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == body["id"]

        updated = client.patch("/v1/tenants/acme", json={"tier": "large"})
        assert updated.status_code == 200
        assert updated.json()["quotas"]["instances"] == 100

        assert client.delete("/v1/tenants/acme").status_code == 204
        assert client.get("/v1/tenants/acme").status_code == 404

    def test_list(self, client: TestClient, gateway: FakeCloudGateway) -> None:
        gateway.add_project("acme", [MANAGED_TAG, Tier.SMALL.tag])

        response = client.get("/v1/tenants")

        assert response.status_code == 200
        assert [t["name"] for t in response.json()] == ["acme"]

    def test_duplicate_is_a_conflict(self, client: TestClient, gateway: FakeCloudGateway) -> None:
        gateway.add_project("acme")

        response = client.post("/v1/tenants", json={"name": "acme"})

        assert response.status_code == 409
        assert response.headers["content-type"] == PROBLEM
        assert response.json()["title"] == "Conflict"

    def test_unknown_member_is_unprocessable(self, client: TestClient) -> None:
        response = client.post("/v1/tenants", json={"name": "acme", "members": ["ghost"]})

        assert response.status_code == 422
        assert "ghost" in response.json()["detail"]

    def test_delete_with_resources_is_a_conflict(
        self, client: TestClient, gateway: FakeCloudGateway
    ) -> None:
        project = gateway.add_project("acme", [MANAGED_TAG])
        gateway.usage[project.id] = ResourceUsage(servers=1, volumes=0)

        response = client.delete("/v1/tenants/acme")

        assert response.status_code == 409

    def test_cloud_failure_is_a_bad_gateway_after_rollback(
        self, client: TestClient, gateway: FakeCloudGateway
    ) -> None:
        gateway.fail_on.add("create_network")

        response = client.post("/v1/tenants", json={"name": "acme"})

        assert response.status_code == 502
        assert "rolled back" in response.json()["detail"]
        assert gateway.projects == {}


class TestValidation:
    def test_invalid_body_returns_problem_with_field_errors(self, client: TestClient) -> None:
        response = client.post(
            "/v1/tenants", json={"name": "Not Valid", "tier": "huge", "extra": 1}
        )

        assert response.status_code == 422
        assert response.headers["content-type"] == PROBLEM
        locations = {tuple(e["loc"]) for e in response.json()["errors"]}
        assert locations == {("body", "name"), ("body", "tier"), ("body", "extra")}

    def test_invalid_path_name_is_rejected(self, client: TestClient) -> None:
        response = client.get("/v1/tenants/UPPER")

        assert response.status_code == 422

    def test_unknown_route_returns_problem(self, client: TestClient) -> None:
        response = client.get("/v2/nothing")

        assert response.status_code == 404
        assert response.headers["content-type"] == PROBLEM


class TestOperations:
    def test_readiness_reflects_openstack_reachability(
        self, client: TestClient, gateway: FakeCloudGateway
    ) -> None:
        assert client.get("/readyz").status_code == 200

        gateway.reachable = False

        assert client.get("/readyz").status_code == 502

    def test_request_id_is_echoed_or_generated(self, client: TestClient) -> None:
        echoed = client.get("/healthz", headers={"X-Request-ID": "abc123"})
        generated = client.get("/healthz")

        assert echoed.headers["x-request-id"] == "abc123"
        assert len(generated.headers["x-request-id"]) == 32

    def test_metrics_use_route_templates(self, client: TestClient) -> None:
        client.get("/v1/tenants/some-tenant")

        metrics = client.get("/metrics").text

        assert 'route="/v1/tenants/{name}"' in metrics
        assert "some-tenant" not in metrics
