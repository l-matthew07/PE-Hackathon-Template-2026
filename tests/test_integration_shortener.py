"""Integration tests for the URL shortener endpoints."""

from app.models.url import Url


class TestShortenUrl:
    def test_shorten_valid_url(self, client):
        resp = client.post("/shorten", json={"original_url": "https://example.com"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["original_url"] == "https://example.com"
        assert data["short_code"]
        assert data["short_url"].endswith(data["short_code"])

    def test_shorten_with_title(self, client):
        resp = client.post("/shorten", json={"original_url": "https://example.com", "title": "Example"})
        assert resp.status_code == 201

    def test_shorten_missing_url(self, client):
        resp = client.post("/shorten", json={})
        assert resp.status_code == 422

    def test_shorten_empty_url(self, client):
        resp = client.post("/shorten", json={"original_url": ""})
        assert resp.status_code == 400

    def test_shorten_invalid_scheme(self, client):
        resp = client.post("/shorten", json={"original_url": "ftp://example.com"})
        assert resp.status_code == 400

    def test_shorten_plain_text(self, client):
        resp = client.post("/shorten", json={"original_url": "not a url at all"})
        assert resp.status_code == 400

    def test_shorten_no_json_body(self, client):
        resp = client.post("/shorten", data="not json", content_type="text/plain")
        assert resp.status_code == 422

    def test_shorten_creates_db_record(self, client):
        resp = client.post("/shorten", json={"original_url": "https://example.com/db-check"})
        assert resp.status_code == 201
        code = resp.get_json()["short_code"]
        url = Url.get_or_none(Url.short_code == code)
        assert url is not None
        assert url.original_url == "https://example.com/db-check"

    def test_shorten_returns_json_error(self, client):
        """Errors must be JSON, not HTML stack traces (graceful failure)."""
        resp = client.post("/shorten", json={"original_url": ""})
        assert resp.content_type.startswith("application/json")


class TestResolveShortUrl:
    def _create_url(self, client, original="https://example.com"):
        resp = client.post("/shorten", json={"original_url": original})
        return resp.get_json()["short_code"]

    def test_resolve_valid_code(self, client):
        code = self._create_url(client)
        resp = client.get(f"/{code}", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://example.com"

    def test_resolve_nonexistent_code(self, client):
        resp = client.get("/nonexistent999", follow_redirects=False)
        assert resp.status_code == 404

    def test_resolve_inactive_url(self, client):
        """Inactive URLs should return 404."""
        code = self._create_url(client, "https://example.com/inactive")
        url = Url.get(Url.short_code == code)
        url.is_active = False
        url.save()
        resp = client.get(f"/{code}", follow_redirects=False)
        assert resp.status_code == 404

    def test_404_returns_json(self, client):
        """404 must be a clean JSON error, not an HTML page."""
        resp = client.get("/does_not_exist_xyz")
        assert resp.content_type.startswith("application/json")
