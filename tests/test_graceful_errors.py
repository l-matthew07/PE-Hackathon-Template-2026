"""Tests for graceful error handling — Gold tier.

The app must return clean JSON errors for all bad inputs, never crash
or return HTML stack traces.
"""


class TestGracefulErrors:
    def test_unknown_route_returns_json(self, client):
        resp = client.get("/this/route/does/not/exist")
        assert resp.status_code == 404
        assert resp.content_type.startswith("application/json")

    def test_post_garbage_json_shorten(self, client):
        resp = client.post(
            "/shorten",
            data="{{invalid json",
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_post_array_instead_of_object(self, client):
        resp = client.post("/shorten", json=[1, 2, 3])
        assert resp.status_code == 422

    def test_post_null_body(self, client):
        resp = client.post("/shorten", json=None)
        assert resp.status_code == 422

    def test_shorten_empty_url_returns_400(self, client):
        resp = client.post("/shorten", json={"original_url": ""})
        assert resp.status_code == 400
        assert resp.content_type.startswith("application/json")

    def test_users_invalid_id_type(self, client):
        resp = client.get("/users/not-a-number")
        assert resp.status_code in (404, 422)

    def test_urls_invalid_id_type(self, client):
        resp = client.get("/urls/abc")
        assert resp.status_code in (404, 422)

    def test_method_not_allowed(self, client):
        resp = client.patch("/health")
        assert resp.status_code == 405

    def test_error_shape_consistent(self, client):
        """All error responses should have {error: {code, message}} shape."""
        resp = client.get("/users/99999")
        data = resp.get_json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]

    def test_url_not_found_error_shape(self, client):
        resp = client.get("/urls/99999")
        data = resp.get_json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]

    def test_shorten_validation_error_shape(self, client):
        resp = client.post("/shorten", json={"original_url": ""})
        data = resp.get_json()
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"
