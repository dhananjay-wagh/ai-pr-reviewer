"""Signed webhook through real queue, engine and GitHub transport (no network)."""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.github import GitHub
from app.main import app
from app.model import ModelResult
from app.store import Store
from app.worker import run_once


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [None, "bad_location", "comment_rejected"])
async def test_signed_delivery_to_published_review(monkeypatch, tmp_path, failure):
    path = str(tmp_path / "jobs.db")
    monkeypatch.setenv("DATABASE_PATH", path)
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("ALLOWED_REPOSITORIES", raising=False)
    sha = "a" * 40
    writes = []

    def handler(request):
        endpoint = request.url.path
        if request.method != "GET":
            writes.append((endpoint, json.loads(request.content) if request.content else None))
        if endpoint.endswith("/pulls/1"):
            return httpx.Response(
                200, json={"head": {"sha": sha}, "base": {"sha": "b" * 40}, "changed_files": 1}
            )
        if endpoint.endswith("/.ai-reviewer.json"):
            return httpx.Response(404, json={})
        if endpoint.endswith("/files"):
            return httpx.Response(
                200,
                json=[
                    {
                        "filename": "a.py",
                        "patch": "@@ -0,0 +1 @@\n+bug()",
                        "additions": 1,
                        "deletions": 0,
                    }
                ],
            )
        if request.method == "GET":
            return httpx.Response(200, json=[])
        if failure == "comment_rejected" and endpoint.endswith("/pulls/1/comments"):
            return httpx.Response(422, json={})
        return httpx.Response(201, json={})

    body = json.dumps(
        {
            "action": "opened",
            "repository": {"full_name": "o/r"},
            "pull_request": {"number": 1, "head": {"sha": sha}},
        }
    ).encode()
    signature = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    finding = dict(
        file="a.py",
        line=99 if failure == "bad_location" else 1,
        side="RIGHT",
        severity="high",
        category="bug",
        comment="Concrete defect",
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.github.com"
    ) as transport:
        github = GitHub("mock", transport, bot_login="reviewer[bot]")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as api:
            response = await api.post(
                "/webhook",
                content=body,
                headers={
                    "x-github-event": "pull_request",
                    "x-github-delivery": "delivery",
                    "x-hub-signature-256": signature,
                },
            )
        assert response.status_code == 202
        assert writes == []
        db = Store(path)
        with (
            patch("app.worker.github_for_job", new=AsyncMock(return_value=github)),
            patch(
                "app.engine.generate",
                new=AsyncMock(return_value=ModelResult([finding], 10, 5, 0.1, "mock")),
            ),
        ):
            await run_once(db)
        job = db.get(response.json()["job_id"])
    assert job["status"] == ("failed" if failure else "completed")
    if failure:
        assert not any(endpoint.endswith("/labels") for endpoint, _ in writes)
    else:
        assert job["result"]["findings"] == [finding]
        assert any(body.get("labels") == ["ai:findings"] for _, body in writes)
