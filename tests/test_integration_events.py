"""Integration tests for the /events endpoints."""

from app.models.url import Url
from app.models.user import User


class TestCreateEvent:
    def _setup_user_and_url(self):
        user = User.create(username="evtuser", email="evt@e.com")
        url = Url.create(
            user_id=user.id,
            short_code="evt123",
            original_url="https://example.com",
        )
        return user, url

    def test_create_valid(self, client):
        user, url = self._setup_user_and_url()
        resp = client.post("/events", json={
            "url_id": url.id,
            "user_id": user.id,
            "event_type": "click",
            "timestamp": "2024-06-01T12:00:00Z",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["event_type"] == "click"

    def test_create_missing_fields(self, client):
        resp = client.post("/events", json={})
        assert resp.status_code == 422

    def test_create_invalid_user_id(self, client):
        """Events referencing non-existent users should fail."""
        resp = client.post("/events", json={
            "url_id": 1,
            "user_id": 99999,
            "event_type": "click",
            "timestamp": "2024-06-01T12:00:00Z",
        })
        assert resp.status_code == 400

    def test_create_invalid_url_id(self, client):
        user, _ = self._setup_user_and_url()
        resp = client.post("/events", json={
            "url_id": 99999,
            "user_id": user.id,
            "event_type": "click",
        })
        assert resp.status_code == 400

    def test_create_without_timestamp_with_object_details(self, client):
        user, url = self._setup_user_and_url()
        resp = client.post(
            "/events",
            json={
                "url_id": url.id,
                "user_id": user.id,
                "event_type": "click",
                "details": {"referrer": "https://google.com"},
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["event_type"] == "click"
        assert data["details"]["referrer"] == "https://google.com"


class TestListEvents:
    def test_list_empty(self, client):
        resp = client.get("/events")
        assert resp.status_code == 200
        assert resp.get_json()["data"] == []


class TestBulkEvents:
    def test_bulk_route_removed(self, client):
        resp = client.post("/events/bulk", json={})
        assert resp.status_code == 404
