from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import Store
from app.worker import run_once


@pytest.mark.anyio
async def test_publish_retry_reuses_checkpoint_without_second_model_call(tmp_path):
    db = Store(str(tmp_path / "jobs.db"))
    job_id, _ = db.enqueue("d", "o/r", 1, "abc")
    result = {
        "findings": [],
        "complete": True,
        "reviewed_files": [],
        "ignored_files": [],
        "skipped_files": [],
        "config": {"min_severity": "medium", "categories": ["bug"]},
    }
    github = AsyncMock()
    github.publish.side_effect = httpx.ConnectError("ambiguous write")
    with (
        patch("app.worker.github_for_job", new=AsyncMock(return_value=github)),
        patch("app.worker.analyze", new=AsyncMock(return_value=result)) as analyze,
    ):
        await run_once(db)
        assert db.get(job_id)["result"]["complete"]
        with db.connect() as connection:
            connection.execute("UPDATE jobs SET available=0 WHERE id=?", (job_id,))
        github.publish.side_effect = None
        github.publish.return_value = True
        await run_once(db)
        analyze.assert_awaited_once()
    assert db.get(job_id)["status"] == "completed"


def test_retry_api_requires_auth_and_failed_state(monkeypatch, tmp_path):
    path = str(tmp_path / "jobs.db")
    monkeypatch.setenv("DATABASE_PATH", path)
    monkeypatch.setenv("DASHBOARD_TOKEN", "test")
    db = Store(path)
    job_id, _ = db.enqueue("d", "o/r", 1, "abc")
    job = db.claim()
    db.finish(job, "failed")
    client = TestClient(app)
    url = f"/api/jobs/{job_id}/retry"
    assert client.post(url).status_code == 401
    headers = {"authorization": "Bearer test"}
    assert client.post(url, headers=headers).status_code == 202
    assert client.post(url, headers=headers).status_code == 409
    with db.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM retry_audit").fetchone()[0] == 1


def test_obsolete_owner_cannot_checkpoint(tmp_path):
    db = Store(str(tmp_path / "jobs.db"))
    db.enqueue("d", "o/r", 1, "abc")
    old = db.claim(lease_seconds=-1)
    new = db.claim()
    with pytest.raises(RuntimeError, match="lease"):
        db.checkpoint(old, {"findings": []})
    db.checkpoint(new, {"findings": []})
