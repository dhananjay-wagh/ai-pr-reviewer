import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.github import GitHub, GitHubError


@pytest.mark.anyio
async def test_transient_get_retries_but_comment_post_does_not():
    calls = []
    def handler(request):
        calls.append(request.method)
        return httpx.Response(503, json={})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.com") as client:
        github = GitHub("test", client)
        with patch("app.github.asyncio.sleep", new=AsyncMock()):
            with pytest.raises(GitHubError):
                await github.request("GET", "/test")
            assert calls == ["GET"] * 3
            calls.clear()
            with pytest.raises(GitHubError):
                await github.request("POST", "/test", json={})
            assert calls == ["POST"]


@pytest.mark.anyio
async def test_publish_deduplicates_and_updates_only_bot_summary(monkeypatch):
    monkeypatch.setenv("GITHUB_BOT_LOGIN", "bot")
    comments = []
    summaries = [{"id": 2, "body": "<!-- ai-reviewer:summary -->", "user": {"login": "human"}}]
    labels = []
    writes = []
    def handler(request):
        path = request.url.path
        body = json.loads(request.content) if request.content else None
        if request.method != "GET":
            writes.append((request.method, path))
        if path.endswith("/pulls/1"):
            return httpx.Response(200, json={"head": {"sha": "abc"}})
        if path.endswith("/pulls/1/comments"):
            if request.method == "POST":
                comments.append({**body, "user": {"login": "bot"}})
            return httpx.Response(200, json=comments)
        if path.endswith("/issues/1/comments"):
            if request.method == "POST":
                summaries.append({**body, "id": 3, "user": {"login": "bot"}})
            return httpx.Response(200, json=summaries)
        if path.endswith("/labels"):
            if request.method == "POST" and "name" in body:
                labels.append(body)
            return httpx.Response(200, json=labels)
        return httpx.Response(200, json={})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.com") as client:
        github = GitHub("test", client)
        finding = dict(file="a.py", line=1, severity="high", category="bug", comment="Fix")
        for _ in range(2):
            assert await github.publish("owner/repo", 1, "abc", [finding], "Summary")
        assert len(comments) == 1
        assert len(summaries) == 2
        assert ("PATCH", "/repos/owner/repo/issues/comments/3") in writes
        assert not any(path.endswith("/comments/2") for _, path in writes)


@pytest.mark.anyio
async def test_stale_commit_never_publishes():
    github = GitHub("test")
    github.head = AsyncMock(return_value="newer")
    github.request = AsyncMock()
    assert not await github.publish("o/r", 1, "old", [], "summary")
    github.request.assert_not_called()
