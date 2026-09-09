"""Typed model output and unified-diff location validation."""
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    file: str = Field(min_length=1, max_length=500, pattern=r"\S")
    line: int = Field(gt=0)
    side: Literal["LEFT", "RIGHT"] = "RIGHT"
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    category: Literal["bug", "security", "performance", "maintainability"] = "bug"
    comment: str = Field(min_length=1, max_length=4000, pattern=r"\S")


def parse_findings(content: str) -> list[dict]:
    text = content.strip()
    if text.startswith("```") and text.endswith("```"):
        text = "\n".join(text.splitlines()[1:-1])
    # Reject the whole response: malformed output must never mean no findings.
    items = TypeAdapter(list[Finding]).validate_python(json.loads(text))
    if len(items) > 50:
        raise ValueError("Too many findings")
    return [item.model_dump() for item in items]


def diff_locations(diff: str) -> set[tuple[str, int, str]]:
    """Return commentable old/new lines, excluding metadata and hunk gaps."""
    locations = set()
    old_path = new_path = None
    old = new = 0
    active = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            active = False
            old_path = new_path = None
        elif not active and line.startswith("--- "):
            old_path = line[4:].removeprefix("a/")
        elif not active and line.startswith("+++ "):
            new_path = line[4:].removeprefix("b/")
        elif match := re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line):
            old, new = map(int, match.groups())
            active = True
        elif active and line.startswith("+"):
            locations.add((new_path, new, "RIGHT"))
            new += 1
        elif active and line.startswith("-"):
            # GitHub uses the new path for renamed files, old path for deletion.
            path = new_path if new_path != "/dev/null" else old_path
            locations.add((path, old, "LEFT"))
            old += 1
        elif active and line.startswith(" "):
            locations.add((new_path, new, "RIGHT"))
            old += 1
            new += 1
    return locations


def validate_locations(findings: list[dict], diff: str) -> None:
    locations = diff_locations(diff)
    for finding in findings:
        if (finding["file"], finding["line"], finding.get("side", "RIGHT")) not in locations:
            raise ValueError("Finding references a line outside the reviewed diff")
