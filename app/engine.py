"""Review whole file patches within a bounded, explicitly reported scope."""

from app.config import load_config
from app.model import generate
from app.reviews import validate_locations


async def analyze(github, repo, number, sha):
    pr = await github.request("GET", f"/repos/{repo}/pulls/{number}")
    if pr["head"]["sha"] != sha:
        return None
    config = await load_config(github, repo, pr["base"]["sha"])
    files = await github.pages(f"/repos/{repo}/pulls/{number}/files")
    result = {
        "findings": [],
        "reviewed_files": [],
        "ignored_files": [],
        "skipped_files": [],
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "model_calls": 0,
        "config": config.model_dump(),
        "complete": pr["changed_files"] == len(files),
    }
    used = 0
    for file in files:
        path = file["filename"]
        if not config.includes(path):
            result["ignored_files"].append(path)
            continue
        patch = file.get("patch")
        reason = None
        old_path = file.get("previous_filename", path)
        if any(char in path + old_path for char in '\n\r"'):
            reason = "unsupported filename"
        elif not patch:
            reason = "binary, empty or unavailable patch"
        elif len(patch) > config.max_file_chars or used + len(patch) > config.max_total_chars:
            reason = "size budget"
        elif len(result["reviewed_files"]) >= config.max_files:
            reason = "file budget"
        elif (
            sum(line.startswith("+") for line in patch.splitlines()) != file["additions"]
            or sum(line.startswith("-") for line in patch.splitlines()) != file["deletions"]
        ):
            reason = "incomplete patch"
        if reason:
            result["skipped_files"].append({"file": path, "reason": reason})
            result["complete"] = False
            continue
        diff = f"diff --git a/{old_path} b/{path}\n--- a/{old_path}\n+++ b/{path}\n{patch}"
        response = await generate(diff)
        validate_locations(response.findings, diff)
        result["findings"].extend(item for item in response.findings if config.accepts(item))
        if len(result["findings"]) > 50:
            raise ValueError("Finding publication budget exceeded")
        result["reviewed_files"].append(path)
        result["model_calls"] += 1
        result["prompt_tokens"] += response.prompt_tokens
        result["completion_tokens"] += response.completion_tokens
        result["model"] = response.model
        result["prompt_version"] = response.prompt_version
        used += len(patch)
    return result


def summary(result):
    scope = (
        "Complete within configured scope"
        if result["complete"]
        else "Partial review — unreviewed changes remain"
    )
    return (
        f"## AI review\n\n**{scope}**\n\n"
        f"Findings: {len(result['findings'])} · Files reviewed: {len(result['reviewed_files'])} · "
        f"Ignored by policy: {len(result['ignored_files'])} · Skipped: {len(result['skipped_files'])}\n\n"
        f"Minimum severity: {result['config']['min_severity']}. "
        f"Categories: {', '.join(result['config']['categories'])}.\n\n"
        "This review does not constitute approval or a security audit."
    )
