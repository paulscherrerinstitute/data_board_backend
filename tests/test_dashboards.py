import json
import os


def load_example():
    path = os.path.join(os.path.dirname(__file__), "example_dashboard.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_dashboard(client, payload):
    resp = client.post("/dashboard/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    return data["id"], data


def test_create_dashboard(client):
    payload = load_example()
    dash_id, data = create_dashboard(client, payload)
    assert data == {"id": dash_id, **payload}


def test_create_dashboard_validation_error(client):
    resp = client.post("/dashboard/", json={})
    assert resp.status_code == 422


def test_create_dashboard_size_error(client, monkeypatch):
    from shared_resources import dashboard_service

    monkeypatch.setattr(dashboard_service, "DASHBOARD_MAX_SINGLE_BYTES", 1)
    payload = load_example()
    resp = client.post("/dashboard/", json=payload)
    assert resp.status_code == 413


def test_get_dashboard_not_found(client):
    resp = client.get("/dashboard/nonexistent")
    assert resp.status_code == 404


def test_get_dashboard(client):
    payload = load_example()
    dash_id, _ = create_dashboard(client, payload)
    resp = client.get(f"/dashboard/{dash_id}")
    assert resp.status_code == 200
    assert resp.json() == {"id": dash_id, **payload}


def test_update_dashboard(client):
    payload = load_example()
    dash_id, _ = create_dashboard(client, payload)
    new = payload.copy()
    new["dashboard"]["widgets"][0]["plotSettings"]["plotTitle"] = "Updated"
    resp = client.patch(f"/dashboard/{dash_id}", json=new)
    assert resp.status_code == 200
    assert resp.json()["dashboard"]["widgets"][0]["plotSettings"]["plotTitle"] == "Updated"


def test_update_dashboard_not_found(client):
    payload = load_example()
    resp = client.patch("/dashboard/nonexistent", json=payload)
    assert resp.status_code == 404


def test_update_dashboard_protected(client):
    payload = load_example()
    dash_id, _ = create_dashboard(client, payload)
    resp = client.post(f"/maintenance/dashboard/{dash_id}/protect")
    assert resp.status_code == 200
    resp = client.patch(f"/dashboard/{dash_id}", json=payload)
    assert resp.status_code == 403


def test_delete_dashboard(client):
    payload = load_example()
    dash_id, _ = create_dashboard(client, payload)
    resp = client.delete(f"/dashboard/{dash_id}")
    assert resp.status_code == 200
    resp = client.get(f"/dashboard/{dash_id}")
    assert resp.status_code == 404


def test_delete_dashboard_not_found(client):
    resp = client.delete("/dashboard/nonexistent")
    assert resp.status_code == 404


def test_delete_dashboard_protected(client):
    payload = load_example()
    dash_id, _ = create_dashboard(client, payload)
    client.post(f"/maintenance/dashboard/{dash_id}/protect")
    resp = client.delete(f"/dashboard/{dash_id}")
    assert resp.status_code == 403


def test_get_full_record_not_found(client):
    resp = client.get("/maintenance/dashboard/nonexistent")
    assert resp.status_code == 404


def test_get_full_record(client):
    payload = load_example()
    dash_id, _ = create_dashboard(client, payload)
    resp = client.get(f"/maintenance/dashboard/{dash_id}")
    assert resp.status_code == 200
    rec = resp.json()
    assert rec["_id"] == dash_id
    assert rec["dashboard"] == payload


def test_whitelist_and_unwhitelist(client):
    payload = load_example()
    dash_id, _ = create_dashboard(client, payload)
    r1 = client.post(f"/maintenance/dashboard/{dash_id}/whitelist")
    assert r1.status_code == 200
    r2 = client.delete(f"/maintenance/dashboard/{dash_id}/whitelist")
    assert r2.status_code == 200


def test_protect_and_unprotect(client):
    payload = load_example()
    dash_id, _ = create_dashboard(client, payload)
    r1 = client.post(f"/maintenance/dashboard/{dash_id}/protect")
    assert r1.status_code == 200
    r2 = client.delete(f"/maintenance/dashboard/{dash_id}/protect")
    assert r2.status_code == 200


def test_eviction_deletes_normal_dashboard(client, monkeypatch):
    payload = load_example()
    dash_id, _ = create_dashboard(client, payload)

    from shared_resources import dashboard_service

    monkeypatch.setattr(dashboard_service, "DASHBOARD_MAX_TOTAL_STORAGE_BYTES", 1)
    monkeypatch.setattr(dashboard_service, "DASHBOARD_EVICTION_THRESHOLD", 0.0)
    monkeypatch.setattr(dashboard_service, "DASHBOARD_TARGET_UTILIZATION", 0.0)

    client.patch(f"/dashboard/{dash_id}", json=payload)

    assert client.get(f"/dashboard/{dash_id}").status_code == 404


def test_eviction_respects_whitelist(client, monkeypatch):
    payload = load_example()
    dash_id, _ = create_dashboard(client, payload)
    client.post(f"/maintenance/dashboard/{dash_id}/whitelist")

    from shared_resources import dashboard_service

    monkeypatch.setattr(dashboard_service, "DASHBOARD_MAX_TOTAL_STORAGE_BYTES", 1)
    monkeypatch.setattr(dashboard_service, "DASHBOARD_EVICTION_THRESHOLD", 0.0)
    monkeypatch.setattr(dashboard_service, "DASHBOARD_TARGET_UTILIZATION", 0.0)
    client.patch(f"/dashboard/{dash_id}", json=payload)

    assert client.get(f"/dashboard/{dash_id}").status_code == 200


def test_eviction_respects_protection_as_whitelist(client, monkeypatch):
    payload = load_example()
    dash_id, _ = create_dashboard(client, payload)
    client.post(f"/maintenance/dashboard/{dash_id}/protect")

    from shared_resources import dashboard_service

    monkeypatch.setattr(dashboard_service, "DASHBOARD_MAX_TOTAL_STORAGE_BYTES", 1)
    monkeypatch.setattr(dashboard_service, "DASHBOARD_EVICTION_THRESHOLD", 0.0)
    monkeypatch.setattr(dashboard_service, "DASHBOARD_TARGET_UTILIZATION", 0.0)
    client.patch(f"/dashboard/{dash_id}", json=payload)

    assert client.get(f"/dashboard/{dash_id}").status_code == 200


def test_unprotect_allows_delete(client):
    payload = load_example()
    dash_id, _ = create_dashboard(client, payload)
    client.post(f"/maintenance/dashboard/{dash_id}/protect")
    client.delete(f"/maintenance/dashboard/{dash_id}/protect")
    resp = client.delete(f"/dashboard/{dash_id}")
    assert resp.status_code == 200
    assert client.get(f"/dashboard/{dash_id}").status_code == 404
