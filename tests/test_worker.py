from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.store import Store
from app.worker import run_once


@pytest.mark.anyio
async def test_worker_persists_result(tmp_path):
    db = Store(str(tmp_path / "jobs.db"))
    job_id, _ = db.enqueue("d", "o/r", 1, "sha")
    with patch("app.worker.review_job", new=AsyncMock(return_value=("completed", {"findings": []}))):
        assert await run_once(db)
    assert db.get(job_id)["status"] == "completed"
    assert not await run_once(db)


@pytest.mark.anyio
async def test_worker_retries_transient_failures(tmp_path):
    db = Store(str(tmp_path / "jobs.db"))
    job_id, _ = db.enqueue("d", "o/r", 1, "sha")
    with patch("app.worker.review_job", new=AsyncMock(side_effect=httpx.ConnectError("secret must not leak"))):
        await run_once(db)
    job = db.get(job_id)
    assert job["status"] == "queued"
    assert job["attempts"] == 1
    assert job["error"] == "ConnectError"
