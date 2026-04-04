"""Integration tests for the /users endpoints."""

from app.models.user import User


class TestCreateUser:
    def test_create_valid(self, client):
        resp = client.post("/users", json={"username": "alice", "email": "alice@example.com"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["username"] == "alice"
        assert data["email"] == "alice@example.com"
        assert "id" in data

    def test_create_missing_fields(self, client):
        resp = client.post("/users", json={})
        assert resp.status_code == 422

    def test_create_invalid_email(self, client):
        resp = client.post("/users", json={"username": "bob", "email": "not-email"})
        assert resp.status_code == 400

    def test_create_duplicate_username(self, client):
        client.post("/users", json={"username": "dup", "email": "a@b.com"})
        resp = client.post("/users", json={"username": "dup", "email": "c@d.com"})
        # SQLite raises IntegrityError which our handler classifies
        assert resp.status_code in (400, 409, 500)

    def test_create_stores_in_db(self, client):
        client.post("/users", json={"username": "dbuser", "email": "db@example.com"})
        user = User.get_or_none(User.username == "dbuser")
        assert user is not None
        assert user.email == "db@example.com"


class TestGetUser:
    def test_get_existing(self, client):
        resp = client.post("/users", json={"username": "getme", "email": "g@e.com"})
        uid = resp.get_json()["id"]
        resp = client.get(f"/users/{uid}")
        assert resp.status_code == 200
        assert resp.get_json()["username"] == "getme"

    def test_get_nonexistent(self, client):
        resp = client.get("/users/99999")
        assert resp.status_code == 404

    def test_get_uses_cache_hit_without_db_lookup(self, client, monkeypatch):
        created = client.post("/users", json={"username": "cache-user", "email": "cache-user@example.com"})
        user_id = created.get_json()["id"]

        monkeypatch.setattr(
            "app.routes.users.cache_get_json",
            lambda key: {
                "id": user_id,
                "username": "cache-user",
                "email": "cache-user@example.com",
                "created_at": None,
            },
        )

        def _fail_db_lookup(*_args, **_kwargs):
            raise AssertionError("DB lookup should not run on cache hit")

        monkeypatch.setattr("app.routes.users.User.get_or_none", _fail_db_lookup)

        resp = client.get(f"/users/{user_id}")
        assert resp.status_code == 200
        assert resp.get_json()["username"] == "cache-user"

    def test_get_caches_db_result_on_miss(self, client, monkeypatch):
        created = client.post("/users", json={"username": "cache-miss-user", "email": "cache-miss@example.com"})
        user_id = created.get_json()["id"]

        recorded = {}

        monkeypatch.setattr("app.routes.users.cache_get_json", lambda key: None)

        def _record_set(key, value, ttl_seconds):
            recorded["key"] = key
            recorded["value"] = value
            recorded["ttl_seconds"] = ttl_seconds

        monkeypatch.setattr("app.routes.users.cache_set_json", _record_set)

        resp = client.get(f"/users/{user_id}")
        assert resp.status_code == 200
        assert recorded["key"] == f"user:{user_id}"
        assert recorded["value"]["id"] == user_id
        assert recorded["ttl_seconds"] > 0


class TestListUsers:
    def test_list_empty(self, client):
        resp = client.get("/users")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"] == []

    def test_list_with_users(self, client):
        client.post("/users", json={"username": "u1", "email": "u1@e.com"})
        client.post("/users", json={"username": "u2", "email": "u2@e.com"})
        resp = client.get("/users")
        assert len(resp.get_json()["data"]) == 2


class TestUpdateUser:
    def test_update_username(self, client):
        resp = client.post("/users", json={"username": "old", "email": "o@e.com"})
        uid = resp.get_json()["id"]
        resp = client.put(f"/users/{uid}", json={"username": "new"})
        assert resp.status_code == 200
        assert resp.get_json()["username"] == "new"

    def test_update_nonexistent(self, client):
        resp = client.put("/users/99999", json={"username": "x"})
        assert resp.status_code == 404

    def test_update_invalidates_user_cache_key(self, client, monkeypatch):
        created = client.post("/users", json={"username": "invalidate-put", "email": "inv-put@example.com"})
        user_id = created.get_json()["id"]

        deleted_keys = []
        monkeypatch.setattr("app.routes.users.cache_delete", lambda key: deleted_keys.append(key))

        resp = client.put(f"/users/{user_id}", json={"username": "updated-name"})
        assert resp.status_code == 200
        assert deleted_keys == [f"user:{user_id}"]


class TestDeleteUser:
    def test_delete_existing(self, client):
        resp = client.post("/users", json={"username": "del", "email": "d@e.com"})
        uid = resp.get_json()["id"]
        resp = client.delete(f"/users/{uid}")
        assert resp.status_code == 204

    def test_delete_nonexistent(self, client):
        resp = client.delete("/users/99999")
        assert resp.status_code == 204

    def test_delete_invalidates_user_cache_key(self, client, monkeypatch):
        created = client.post("/users", json={"username": "invalidate-del", "email": "inv-del@example.com"})
        user_id = created.get_json()["id"]

        deleted_keys = []
        monkeypatch.setattr("app.routes.users.cache_delete", lambda key: deleted_keys.append(key))

        resp = client.delete(f"/users/{user_id}")
        assert resp.status_code == 204
        assert deleted_keys == [f"user:{user_id}"]
