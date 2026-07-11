"""Health endpoint tests."""


def test_live_health(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_health_with_database(client, monkeypatch):
    monkeypatch.setattr("app.api.health.check_db_connection", lambda: True)
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] is True


def test_ready_health_without_database(client, monkeypatch):
    monkeypatch.setattr("app.api.health.check_db_connection", lambda: False)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["database"] is False
