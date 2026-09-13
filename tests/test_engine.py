import base64
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.config import ReviewConfig, load_config
from app.engine import analyze, summary
from app.github import GitHubError
from app.model import ModelResult


def test_policy_validates_budget_and_filters():
    with pytest.raises(ValueError):
        ReviewConfig(max_files=1000)
    assert not ReviewConfig().includes("vendor/a.py")
    assert not ReviewConfig().accepts({"severity": "low", "category": "bug"})


@pytest.mark.anyio
async def test_config_reads_base_commit_and_rejects_bad_config():
    github = AsyncMock()
    github.request.return_value = {"size": 2, "encoding": "base64", "content": base64.b64encode(b"{}").decode()}
    await load_config(github, "o/r", "base-sha")
    assert github.request.call_args.kwargs["params"] == {"ref": "base-sha"}
    github.request.return_value["content"] = base64.b64encode(b'{"max_files":1000}').decode()
    with pytest.raises(ValueError):
        await load_config(github, "o/r", "base")


@pytest.mark.anyio
async def test_bounded_file_review_reports_missing_coverage():
    github = AsyncMock()
    github.request.return_value = {"head": {"sha": "abc"}, "base": {"sha": "base"}, "changed_files": 3}
    github.pages.return_value = [
        {"filename": "a.py", "patch": "@@ -0,0 +1 @@\n+bug()", "additions": 1, "deletions": 0},
        {"filename": "image.png", "additions": 0, "deletions": 0},
        {"filename": "vendor/a.py", "additions": 0, "deletions": 0}]
    finding = dict(file="a.py", line=1, side="RIGHT", severity="high", category="bug", comment="Crash")
    with patch("app.engine.load_config", new=AsyncMock(return_value=ReviewConfig())), patch("app.engine.generate", new=AsyncMock(return_value=ModelResult([finding], 10, 5, .1, "test"))):
        result = await analyze(github, "o/r", 1, "abc")
    assert result["findings"] == [finding]
    assert not result["complete"]
    assert result["ignored_files"] == ["vendor/a.py"]
    assert result["prompt_tokens"] == 10
    assert "Partial" in summary(result)


@pytest.mark.anyio
async def test_truncated_patch_and_budget_never_receive_clear_result():
    github = AsyncMock()
    github.request.return_value = {"head": {"sha": "abc"}, "base": {"sha": "base"}, "changed_files": 1}
    github.pages.return_value = [{"filename": "a.py", "patch": "@@ -0,0 +1 @@\n+bug()", "additions": 20, "deletions": 0}]
    with patch("app.engine.load_config", new=AsyncMock(return_value=ReviewConfig())), patch("app.engine.generate", new=AsyncMock()) as generate:
        result = await analyze(github, "o/r", 1, "abc")
    assert not result["complete"]
    generate.assert_not_called()
