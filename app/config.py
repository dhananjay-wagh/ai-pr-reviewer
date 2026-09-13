"""Repository policy is loaded only from the PR's trusted base commit."""
import base64
from fnmatch import fnmatchcase
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.github import GitHubError

SEVERITY = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class ReviewConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    ignore: list[str] = Field(default_factory=lambda: ["*.lock", "vendor/*", "dist/*"], max_length=100)
    min_severity: Literal["low", "medium", "high", "critical"] = "medium"
    categories: list[Literal["bug", "security", "performance", "maintainability"]] = Field(
        default_factory=lambda: ["bug", "security", "performance"], max_length=4)
    max_files: int = Field(default=20, ge=1, le=50)
    max_file_chars: int = Field(default=12000, ge=500, le=20000)
    max_total_chars: int = Field(default=60000, ge=500, le=200000)

    def includes(self, path):
        return not any(fnmatchcase(path, pattern) for pattern in self.ignore)

    def accepts(self, finding):
        return (SEVERITY[finding["severity"]] >= SEVERITY[self.min_severity]
                and finding["category"] in self.categories)


async def load_config(github, repo, base_sha):
    try:
        response = await github.request("GET", f"/repos/{repo}/contents/.ai-reviewer.json", params={"ref": base_sha})
    except GitHubError as exc:
        if exc.status == 404:
            return ReviewConfig()
        raise
    if response.get("size", 0) > 16000 or response.get("encoding") != "base64":
        raise ValueError("Invalid repository config size or encoding")
    content = base64.b64decode(response["content"])
    if len(content) > 16000:
        raise ValueError("Repository config too large")
    return ReviewConfig.model_validate_json(content)
