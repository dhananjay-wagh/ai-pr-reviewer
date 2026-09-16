import pytest
from fastapi.testclient import TestClient

from app.main import app
from scripts.seed_demo import seed


def test_dashboard_does_not_expose_private_data_without_auth(monkeypatch, tmp_path):
    path = str(tmp_path / "jobs.db")
    seed(path)
    monkeypatch.setenv("DATABASE_PATH", path)
    monkeypatch.setenv("DASHBOARD_TOKEN", "test-dashboard")
    client = TestClient(app)
    page = client.get("/dashboard")
    assert page.status_code == 200
    assert "demo/payments-api" not in page.text
    assert "script-src 'self'" in page.headers["content-security-policy"]
    for path in ("/api/jobs", "/api/metrics"):
        assert client.get(path).status_code == 401
    headers = {"authorization": "Bearer test-dashboard"}
    jobs = client.get("/api/jobs", headers=headers)
    assert len(jobs.json()["jobs"]) == 3
    assert jobs.headers["cache-control"] == "no-store"
    assert all("owner" not in job and "installation" not in job for job in jobs.json()["jobs"])
    metrics = client.get("/api/metrics", headers=headers).json()
    assert metrics["jobs_by_status"]["completed"] == 3
    assert metrics["partial_reviews"] == 1
    assert client.get("/api/jobs?limit=101", headers=headers).status_code == 422


def test_demo_seed_is_idempotent(tmp_path):
    path = str(tmp_path / "jobs.db")
    seed(path)
    db = seed(path)
    assert len(db.recent()) == 3


def test_demo_seed_refuses_existing_real_jobs(tmp_path):
    from app.store import Store

    path = str(tmp_path / "jobs.db")
    db = Store(path)
    job_id, _ = db.enqueue("real", "owner/repo", 1, "abc")
    with pytest.raises(ValueError, match="empty database"):
        seed(path)
    assert db.get(job_id)["status"] == "queued"
