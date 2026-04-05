"""Integration tests for the /urls CRUD endpoints."""

import io

from app.models.url import Url
from app.routes.urls import urls_service


class TestCreateUrl:
    def test_create_valid(self, client):
        resp = client.post("/urls", json={"original_url": "https://example.com"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["original_url"] == "https://example.com"
        assert data["short_code"]
        assert len(data["short_code"]) == 8
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

    def test_create_duplicate_original_url_without_short_code_reuses_mapping(self, client):
        first = client.post("/urls", json={"original_url": "https://dup-url.com"})
        second = client.post("/urls", json={"original_url": "https://dup-url.com"})

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.get_json()["short_code"] == second.get_json()["short_code"]
        assert Url.select().where(Url.original_url == "https://dup-url.com").count() == 1

    def test_create_retries_when_generated_code_already_exists(self, client, monkeypatch):
        Url.create(original_url="https://already-used.com", short_code="cccccccc")

        generated_codes = iter(["cccccccc", "dddddddd"])
        monkeypatch.setattr(urls_service, "_generate_code", lambda: next(generated_codes))

        resp = client.post("/urls", json={"original_url": "https://urls-retry.com"})
        assert resp.status_code == 201
        assert resp.get_json()["short_code"] == "dddddddd"


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

    def test_get_uses_cache_hit_without_db_lookup(self, client, monkeypatch):
        created = client.post("/urls", json={"original_url": "https://cached-url.com", "short_code": "cachehit"})
        url_id = created.get_json()["id"]

        monkeypatch.setattr(
            "app.routes.urls.cache_get_json",
            lambda key: {
                "id": url_id,
                "user_id": None,
                "short_code": "cachehit",
                "original_url": "https://cached-url.com",
                "title": None,
                "is_active": True,
                "created_at": None,
                "updated_at": None,
            },
        )

        def _fail_db_lookup(*_args, **_kwargs):
            raise AssertionError("DB lookup should not run on cache hit")

        monkeypatch.setattr("app.routes.urls.Url.get_or_none", _fail_db_lookup)

        resp = client.get(f"/urls/{url_id}")
        assert resp.status_code == 200
        assert resp.get_json()["short_code"] == "cachehit"

    def test_get_caches_db_result_on_miss(self, client, monkeypatch):
        created = client.post("/urls", json={"original_url": "https://cache-miss.com", "short_code": "cachems"})
        url_id = created.get_json()["id"]

        recorded = {}

        monkeypatch.setattr("app.routes.urls.cache_get_json", lambda key: None)

        def _record_set(key, value, ttl_seconds):
            recorded["key"] = key
            recorded["value"] = value
            recorded["ttl_seconds"] = ttl_seconds

        monkeypatch.setattr("app.routes.urls.cache_set_json", _record_set)

        resp = client.get(f"/urls/{url_id}")
        assert resp.status_code == 200
        assert recorded["key"] == f"url:{url_id}"
        assert recorded["value"]["id"] == url_id
        assert recorded["ttl_seconds"] > 0


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

    def test_update_invalidates_url_cache_key(self, client, monkeypatch):
        created = client.post("/urls", json={"original_url": "https://invalidate-put.com", "short_code": "invput"})
        url_id = created.get_json()["id"]

        deleted_keys = []
        monkeypatch.setattr("app.routes.urls.cache_delete", lambda key: deleted_keys.append(key))

        resp = client.put(f"/urls/{url_id}", json={"title": "Updated"})
        assert resp.status_code == 200
        assert deleted_keys == [f"url:{url_id}"]


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

    def test_delete_invalidates_url_cache_key(self, client, monkeypatch):
        created = client.post("/urls", json={"original_url": "https://invalidate-del.com", "short_code": "invdel"})
        url_id = created.get_json()["id"]

        deleted_keys = []
        monkeypatch.setattr("app.routes.urls.cache_delete", lambda key: deleted_keys.append(key))

        resp = client.delete(f"/urls/{url_id}")
        assert resp.status_code == 204
        assert deleted_keys == [f"url:{url_id}"]


class TestResolveShortCode:
    def test_resolve_existing_short_code_redirects(self, client):
        created = client.post("/urls", json={"original_url": "https://resolve-me.com", "short_code": "resolve1"})
        assert created.status_code == 201

        resp = client.get("/resolve1", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://resolve-me.com"

    def test_resolve_inactive_short_code_returns_404(self, client):
        created = client.post("/urls", json={"original_url": "https://inactive-me.com", "short_code": "inactive1"})
        url_id = created.get_json()["id"]
        client.put(f"/urls/{url_id}", json={"is_active": False})

        resp = client.get("/inactive1", follow_redirects=False)
        assert resp.status_code == 404


class TestBulkUrls:
    def test_bulk_import_urls_csv_by_filename_json(self, client):
        resp = client.post("/urls/bulk", json={"file": "urls.csv"})
        assert resp.status_code == 201
        payload = resp.get_json()
        assert payload["imported"] > 0

    def test_bulk_import_urls_csv_upload(self, client):
        csv_bytes = (
            b"short_code,original_url,title,is_active\n"
            b"bulk001,https://bulk-upload-1.example.com,Upload 1,True\n"
            b"bulk002,https://bulk-upload-2.example.com,Upload 2,False\n"
        )
        resp = client.post(
            "/urls/bulk",
            data={"file": (io.BytesIO(csv_bytes), "urls.csv")},
            content_type="multipart/form-data",
        )

        assert resp.status_code == 201
        payload = resp.get_json()
        assert payload["imported"] == 2
