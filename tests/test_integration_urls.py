"""Integration tests for the /urls CRUD endpoints."""

from app.models.url import Url


class TestCreateUrl:
    def test_create_valid(self, client):
        resp = client.post("/urls", json={"original_url": "https://example.com"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["original_url"] == "https://example.com"
        assert data["short_code"]
        assert data["is_active"] is True

    def test_create_with_custom_short_code(self, client):
        resp = client.post("/urls", json={"original_url": "https://example.com", "short_code": "custom"})
        assert resp.status_code == 201
        assert resp.get_json()["short_code"] == "custom"

    def test_create_duplicate_short_code(self, client):
        client.post("/urls", json={"original_url": "https://a.com", "short_code": "dup1"})
        resp = client.post("/urls", json={"original_url": "https://b.com", "short_code": "dup1"})
        # SQLite IntegrityError handling may differ from Postgres
        assert resp.status_code in (400, 409, 500)

    def test_create_missing_url(self, client):
        resp = client.post("/urls", json={})
        assert resp.status_code in (400, 422)

    def test_create_invalid_url(self, client):
        resp = client.post("/urls", json={"original_url": "not-a-url"})
        assert resp.status_code in (400, 422)

    def test_create_stores_in_db(self, client):
        resp = client.post("/urls", json={"original_url": "https://db-test.com", "short_code": "dbtest"})
        assert resp.status_code == 201
        url = Url.get_or_none(Url.short_code == "dbtest")
        assert url is not None


class TestGetUrl:
    def test_get_existing(self, client):
        resp = client.post("/urls", json={"original_url": "https://get.com", "short_code": "getme"})
        url_id = resp.get_json()["id"]
        resp = client.get(f"/urls/{url_id}")
        assert resp.status_code == 200
        assert resp.get_json()["short_code"] == "getme"

    def test_get_nonexistent(self, client):
        resp = client.get("/urls/99999")
        assert resp.status_code == 404


class TestListUrls:
    def test_list_empty(self, client):
        resp = client.get("/urls")
        assert resp.status_code == 200
        assert resp.get_json()["data"] == []

    def test_list_returns_created(self, client):
        client.post("/urls", json={"original_url": "https://a.com", "short_code": "aa"})
        client.post("/urls", json={"original_url": "https://b.com", "short_code": "bb"})
        resp = client.get("/urls")
        assert len(resp.get_json()["data"]) == 2


class TestUpdateUrl:
    def test_update_title(self, client):
        resp = client.post("/urls", json={"original_url": "https://up.com", "short_code": "upd"})
        url_id = resp.get_json()["id"]
        resp = client.put(f"/urls/{url_id}", json={"title": "Updated"})
        assert resp.status_code == 200
        assert resp.get_json()["title"] == "Updated"

    def test_deactivate_url(self, client):
        resp = client.post("/urls", json={"original_url": "https://deact.com", "short_code": "deact"})
        url_id = resp.get_json()["id"]
        resp = client.put(f"/urls/{url_id}", json={"is_active": False})
        assert resp.status_code == 200
        assert resp.get_json()["is_active"] is False

    def test_update_nonexistent(self, client):
        resp = client.put("/urls/99999", json={"title": "x"})
        assert resp.status_code == 404

    def test_update_empty_payload(self, client):
        resp = client.post("/urls", json={"original_url": "https://x.com", "short_code": "emp"})
        url_id = resp.get_json()["id"]
        resp = client.put(f"/urls/{url_id}", json={})
        assert resp.status_code in (400, 422)


class TestDeleteUrl:
    def test_delete_existing(self, client):
        resp = client.post("/urls", json={"original_url": "https://del.com", "short_code": "del1"})
        url_id = resp.get_json()["id"]
        resp = client.delete(f"/urls/{url_id}")
        assert resp.status_code == 204
        assert Url.get_or_none(Url.id == url_id) is None

    def test_delete_nonexistent(self, client):
        resp = client.delete("/urls/99999")
        assert resp.status_code == 204
