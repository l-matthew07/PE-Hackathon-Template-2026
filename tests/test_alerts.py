"""Tests for the /alerts endpoints."""


def test_create_alert(client):
    resp = client.post("/alerts", json={"alert_name": "HighErrorRate", "severity": "warning", "summary": "Error rate above 10%"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["alert_name"] == "HighErrorRate"
    assert data["severity"] == "warning"
    assert data["status"] == "firing"
    assert data["summary"] == "Error rate above 10%"
    assert data["fired_at"] is not None
    assert data["acknowledged_at"] is None
    assert data["resolved_at"] is None


def test_create_alert_defaults(client):
    resp = client.post("/alerts", json={"alert_name": "TestAlert"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["severity"] == "warning"
    assert data["status"] == "firing"


def test_create_alert_missing_name(client):
    resp = client.post("/alerts", json={"severity": "critical"})
    assert resp.status_code == 422 or resp.status_code == 400


def test_list_alerts(client):
    client.post("/alerts", json={"alert_name": "Alert1", "severity": "critical"})
    client.post("/alerts", json={"alert_name": "Alert2", "severity": "warning"})
    resp = client.get("/alerts")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 2


def test_list_alerts_filter_status(client):
    client.post("/alerts", json={"alert_name": "Alert1"})
    client.post("/alerts", json={"alert_name": "Alert2"})
    resp = client.get("/alerts?status=firing")
    assert resp.status_code == 200
    for alert in resp.get_json()["data"]:
        assert alert["status"] == "firing"


def test_list_alerts_filter_severity(client):
    client.post("/alerts", json={"alert_name": "A1", "severity": "critical"})
    client.post("/alerts", json={"alert_name": "A2", "severity": "warning"})
    resp = client.get("/alerts?severity=critical")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 1
    assert data[0]["severity"] == "critical"


def test_get_alert(client):
    create = client.post("/alerts", json={"alert_name": "TestAlert"})
    alert_id = create.get_json()["id"]
    resp = client.get(f"/alerts/{alert_id}")
    assert resp.status_code == 200
    assert resp.get_json()["alert_name"] == "TestAlert"


def test_get_alert_not_found(client):
    resp = client.get("/alerts/99999")
    assert resp.status_code == 404


def test_acknowledge_alert(client):
    create = client.post("/alerts", json={"alert_name": "TestAlert"})
    alert_id = create.get_json()["id"]
    resp = client.put(f"/alerts/{alert_id}", json={"status": "acknowledged", "acknowledged_by": "alice"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "acknowledged"
    assert data["acknowledged_at"] is not None
    assert data["acknowledged_by"] == "alice"


def test_resolve_alert(client):
    create = client.post("/alerts", json={"alert_name": "TestAlert"})
    alert_id = create.get_json()["id"]
    resp = client.put(f"/alerts/{alert_id}", json={"status": "resolved"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "resolved"
    assert data["resolved_at"] is not None


def test_add_notes(client):
    create = client.post("/alerts", json={"alert_name": "TestAlert"})
    alert_id = create.get_json()["id"]
    client.put(f"/alerts/{alert_id}", json={"notes": "Investigating DNS issue"})
    client.put(f"/alerts/{alert_id}", json={"notes": "Found root cause"})
    resp = client.get(f"/alerts/{alert_id}")
    data = resp.get_json()
    assert "Investigating DNS issue" in data["notes"]
    assert "Found root cause" in data["notes"]


def test_invalid_status(client):
    create = client.post("/alerts", json={"alert_name": "TestAlert"})
    alert_id = create.get_json()["id"]
    resp = client.put(f"/alerts/{alert_id}", json={"status": "invalid"})
    assert resp.status_code == 400


def test_update_not_found(client):
    resp = client.put("/alerts/99999", json={"status": "resolved"})
    assert resp.status_code == 404
