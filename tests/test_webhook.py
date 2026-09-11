import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.utils import get_code_review, verify_signature


@pytest.fixture(autouse=True)
def environment(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "jobs.db"))


def payload():
    return {"action": "opened", "repository": {"full_name": "owner/repo"},
            "pull_request": {"number": 1, "head": {"sha": "a" * 40}}}


def send(client, data=None, delivery="delivery-1", event="pull_request"):
    body = json.dumps(data if data is not None else payload()).encode()
    signature = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    return client.post("/webhook", content=body, headers={"x-hub-signature-256": signature,
                       "x-github-event": event, "x-github-delivery": delivery})


def test_health_and_signatures():
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "healthy"}
    assert client.post("/webhook").status_code == 403
    assert not verify_signature(b"payload", "sha256=wrong")


def test_webhook_queues_and_deduplicates_without_external_calls(monkeypatch):
    client = TestClient(app)
    first = send(client)
    assert first.status_code == 202
    assert first.json()["status"] == "queued"
    for delivery in ("delivery-1", "delivery-2"):
        duplicate = send(client, delivery=delivery)
        assert duplicate.json() == {"status": "duplicate", "job_id": first.json()["job_id"]}
    monkeypatch.setenv("DASHBOARD_TOKEN", "admin")
    assert client.get("/api/jobs/"+first.json()["job_id"]).status_code == 401
    response = client.get("/api/jobs/"+first.json()["job_id"], headers={"authorization": "Bearer admin"})
    assert response.json()["status"] == "queued"


@pytest.mark.parametrize("data", [[], {"action":"opened"}, {**payload(), "repository": None}])
def test_malformed_payload_never_enqueues(data):
    assert send(TestClient(app), data).status_code in (400, 422)


def test_ignored_event_and_missing_delivery():
    assert send(TestClient(app), event="ping").json() == {"status": "ignored"}
    assert send(TestClient(app), delivery="").status_code == 400


@pytest.mark.anyio
async def test_model_output_fails_closed():
    from types import SimpleNamespace
    with patch("groq.AsyncGroq") as cls:
        cls.return_value.chat.completions.create = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='[{"file":"a.py","line":0,"comment":"bug"}]'))]))
        assert await get_code_review("diff") is None
