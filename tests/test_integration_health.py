"""Integration tests for the /health endpoint."""


class TestHealth:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        data = resp.get_json()
        assert data["status"] == "ok"
