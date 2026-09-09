import json
import hmac
import hashlib
from unittest.mock import patch, AsyncMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.utils import verify_signature, get_code_review


client = TestClient(app)
TEST_SECRET = "test-secret"


def make_signature(body: bytes, secret: str = TEST_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", TEST_SECRET)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_valid_signature():
    payload = b"hello world"
    sig = make_signature(payload)
    assert verify_signature(payload, sig) is True


def test_invalid_signature():
    payload = b"hello world"
    assert verify_signature(payload, "sha256=invalidhash") is False
    assert verify_signature(payload, "") is False


def test_webhook_ignores_non_pull_request_events():
    response = client.post("/webhook", headers={"x-github-event": "ping"})
    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}


def test_webhook_missing_signature():
    response = client.post("/webhook", headers={"x-github-event": "pull_request"})
    assert response.status_code == 403
    assert response.json() == {"detail": "missing signature"}


def test_webhook_invalid_signature():
    payload = json.dumps({"action": "opened"}).encode()
    response = client.post(
        "/webhook",
        headers={
            "x-github-event": "pull_request",
            "x-hub-signature-256": "sha256=wrong",
        },
        content=payload,
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "invalid signature"}


def test_webhook_invalid_json():
    payload = b"not-a-json"
    sig = make_signature(payload)
    response = client.post(
        "/webhook",
        headers={
            "x-github-event": "pull_request",
            "x-hub-signature-256": sig,
        },
        content=payload,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid JSON payload"}


def test_webhook_ignored_action():
    payload = json.dumps({"action": "closed"}).encode()
    sig = make_signature(payload)
    response = client.post(
        "/webhook",
        headers={
            "x-github-event": "pull_request",
            "x-hub-signature-256": sig,
        },
        content=payload,
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}


def test_webhook_missing_pr_fields():
    payload = json.dumps({"action": "opened"}).encode()
    sig = make_signature(payload)
    response = client.post(
        "/webhook",
        headers={
            "x-github-event": "pull_request",
            "x-hub-signature-256": sig,
        },
        content=payload,
    )
    assert response.status_code == 200
    assert response.json() == {"status": "missing pull request data"}


@patch("app.main.fetch_pr_diff", new_callable=AsyncMock)
def test_webhook_failed_diff_retrieval(mock_fetch_diff):
    mock_fetch_diff.return_value = None

    payload = json.dumps({
        "action": "opened",
        "repository": {"full_name": "owner/repo"},
        "pull_request": {"number": 42, "head": {"sha": "abc1234"}},
    }).encode()
    sig = make_signature(payload)

    response = client.post(
        "/webhook",
        headers={
            "x-github-event": "pull_request",
            "x-hub-signature-256": sig,
        },
        content=payload,
    )
    assert response.status_code == 200
    assert response.json() == {"status": "failed to retrieve diff"}


@patch("app.main.fetch_pr_diff", new_callable=AsyncMock)
def test_webhook_empty_diff(mock_fetch_diff):
    mock_fetch_diff.return_value = ""

    payload = json.dumps({
        "action": "opened",
        "repository": {"full_name": "owner/repo"},
        "pull_request": {"number": 42, "head": {"sha": "abc1234"}},
    }).encode()
    sig = make_signature(payload)

    response = client.post(
        "/webhook",
        headers={
            "x-github-event": "pull_request",
            "x-hub-signature-256": sig,
        },
        content=payload,
    )
    assert response.status_code == 200
    assert response.json() == {"status": "no diff"}


@patch("app.main.add_labels", new_callable=AsyncMock)
@patch("app.main.post_inline_comment", new_callable=AsyncMock)
@patch("app.main.get_code_review", new_callable=AsyncMock)
@patch("app.main.fetch_pr_diff", new_callable=AsyncMock)
def test_webhook_full_flow_with_reviews(mock_diff, mock_review, mock_comment, mock_labels):
    mock_diff.return_value = "diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py\n@@ -0,0 +1 @@\n+x = 1"
    mock_review.return_value = [
        {"file": "file.py", "line": 1, "comment": "Consider better variable name."}
    ]
    mock_comment.return_value = 201
    mock_labels.return_value = 200

    payload = json.dumps({
        "action": "opened",
        "repository": {"full_name": "owner/repo"},
        "pull_request": {"number": 10, "head": {"sha": "commit123"}},
    }).encode()
    sig = make_signature(payload)

    response = client.post(
        "/webhook",
        headers={
            "x-github-event": "pull_request",
            "x-hub-signature-256": sig,
        },
        content=payload,
    )
    assert response.status_code == 200
    assert response.json() == {"status": "received"}

    mock_comment.assert_called_once_with(
        "owner/repo", 10, "commit123", "file.py", 1, "Consider better variable name.", "RIGHT"
    )
    mock_labels.assert_called_once_with("owner/repo", 10, "needs changes")


@patch("app.main.add_labels", new_callable=AsyncMock)
@patch("app.main.post_inline_comment", new_callable=AsyncMock)
@patch("app.main.get_code_review", new_callable=AsyncMock)
@patch("app.main.fetch_pr_diff", new_callable=AsyncMock)
def test_webhook_full_flow_approved(mock_diff, mock_review, mock_comment, mock_labels):
    mock_diff.return_value = "diff --git a/file.py b/file.py\n+x = 1"
    mock_review.return_value = []
    mock_labels.return_value = 200

    payload = json.dumps({
        "action": "opened",
        "repository": {"full_name": "owner/repo"},
        "pull_request": {"number": 10, "head": {"sha": "commit123"}},
    }).encode()
    sig = make_signature(payload)

    response = client.post(
        "/webhook",
        headers={
            "x-github-event": "pull_request",
            "x-hub-signature-256": sig,
        },
        content=payload,
    )
    assert response.status_code == 200
    assert response.json() == {"status": "received"}

    mock_comment.assert_not_called()
    mock_labels.assert_called_once_with("owner/repo", 10, "approved")


@pytest.mark.anyio
async def test_get_code_review_strips_markdown():
    mock_content = "```json\n[{\"file\": \"main.py\", \"line\": 5, \"comment\": \"Fix indentation\"}]\n```"

    with patch("groq.AsyncGroq") as mock_groq_cls:
        mock_instance = mock_groq_cls.return_value
        mock_chat = AsyncMock()
        mock_choice = AsyncMock()
        mock_choice.message.content = mock_content
        mock_resp = AsyncMock()
        mock_resp.choices = [mock_choice]
        mock_chat.completions.create.return_value = mock_resp
        mock_instance.chat = mock_chat

        result = await get_code_review("diff content")
        assert result[0]["file"] == "main.py"
        assert result[0]["line"] == 5


@pytest.mark.anyio
async def test_get_code_review_rejects_invalid_items():
    mock_content = json.dumps([
        {"file": "a.py", "line": 1, "comment": "Valid"},
        {"file": "", "line": 1, "comment": "Missing file"},
        {"file": "b.py", "line": 0, "comment": "Invalid line"},
        {"file": "c.py", "line": 2, "comment": ""},
        "not a dict"
    ])

    with patch("groq.AsyncGroq") as mock_groq_cls:
        mock_instance = mock_groq_cls.return_value
        mock_chat = AsyncMock()
        mock_choice = AsyncMock()
        mock_choice.message.content = mock_content
        mock_resp = AsyncMock()
        mock_resp.choices = [mock_choice]
        mock_chat.completions.create.return_value = mock_resp
        mock_instance.chat = mock_chat

        result = await get_code_review("diff content")
        assert result is None
