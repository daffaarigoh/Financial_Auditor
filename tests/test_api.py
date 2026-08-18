import io
from mcp_tools.db_handler import insert_audit_record


def test_get_root_serves_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "html" in response.headers.get("content-type", "")


def test_get_history_empty(client):
    response = client.get("/api/history")
    assert response.status_code == 200
    data = response.json()
    assert "records" in data
    assert "counts" in data
    assert data["counts"]["total"] == 0


def test_get_history_with_records(client):
    insert_audit_record({
        "file_name": "sample.pdf",
        "status": "VALID",
        "vendor_name": "PT Test",
        "total_amount": 50000.0,
    })
    response = client.get("/api/history")
    assert response.status_code == 200
    data = response.json()
    assert len(data["records"]) == 1
    assert data["records"][0]["vendor_name"] == "PT Test"
    assert data["counts"]["total"] == 1


def test_delete_history(client):
    insert_audit_record({"file_name": "temp.pdf", "status": "VALID"})
    
    del_response = client.delete("/api/history")
    assert del_response.status_code == 200
    assert del_response.json()["success"] is True

    get_response = client.get("/api/history")
    assert len(get_response.json()["records"]) == 0


def test_upload_endpoint_starts_job(client, monkeypatch):
    # Mock background pipeline thread so it doesn't call real LLM
    monkeypatch.setattr("server._run_pipeline", lambda job_id, fn, fp: None)

    fake_file = io.BytesIO(b"fake invoice content")
    response = client.post(
        "/api/audit",
        files={"file": ("test_invoice.png", fake_file, "image/png")}
    )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert "file_name" in data
    assert data["file_name"] == "test_invoice.png"
