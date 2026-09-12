"""GitHub transport and retry-safe, bot-owned review publication."""
import asyncio
import hashlib
import json
import os

import httpx


class GitHubError(RuntimeError):
    def __init__(self, status: int, operation: str):
        super().__init__(f"GitHub {operation} failed ({status})")
        self.status = status
        self.retryable = status in (408, 429) or status >= 500


class GitHub:
    def __init__(self, token: str, client: httpx.AsyncClient | None = None, bot_login: str | None = None):
        self.token = token
        self.client = client
        self.bot_login = bot_login

    async def request(self, method: str, path: str, **kwargs):
        async with httpx.AsyncClient(base_url="https://api.github.com", timeout=20) as default:
            client = self.client or default
            for attempt in range(3):
                try:
                    response = await client.request(method, path, headers={
                        "Authorization": f"Bearer {self.token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    }, **kwargs)
                except httpx.TransportError:
                    if method not in ("GET", "PUT", "DELETE") or attempt == 2:
                        raise
                    await asyncio.sleep(2 ** attempt)
                    continue
                limited = response.status_code == 403 and (
                    response.headers.get("x-ratelimit-remaining") == "0"
                    or "retry-after" in response.headers
                )
                if response.status_code < 400:
                    return response.json() if response.content else None
                error = GitHubError(response.status_code, method)
                error.retryable |= limited
                if not error.retryable or method not in ("GET", "PUT", "DELETE") or attempt == 2:
                    raise error
                try:
                    delay = min(30, max(1, float(response.headers.get("retry-after", 2 ** attempt))))
                except ValueError:
                    delay = 2 ** attempt
                await asyncio.sleep(delay)

    async def pages(self, path: str):
        items = []
        for page in range(1, 101):
            batch = await self.request("GET", path, params={"per_page": 100, "page": page})
            items.extend(batch)
            if len(batch) < 100:
                return items
        raise RuntimeError("GitHub pagination limit exceeded")

    async def head(self, repo: str, number: int) -> str:
        pr = await self.request("GET", f"/repos/{repo}/pulls/{number}")
        return pr["head"]["sha"]

    async def diff(self, repo: str, number: int) -> str:
        # File patches preserve GitHub's canonical paths and paginate large PRs.
        files = await self.pages(f"/repos/{repo}/pulls/{number}/files")
        chunks = []
        for file in files:
            path = file["filename"]
            old = file.get("previous_filename", path)
            if "patch" not in file:
                raise ValueError(f"Missing patch for {path}; full review unavailable")
            chunks.append(f"diff --git a/{old} b/{path}\n--- a/{old}\n+++ b/{path}\n{file['patch']}")
        return "\n".join(chunks)

    async def actor(self) -> str:
        if self.bot_login:
            return self.bot_login
        if os.getenv("GITHUB_BOT_LOGIN"):
            return os.environ["GITHUB_BOT_LOGIN"]
        return (await self.request("GET", "/user"))["login"]

    async def publish(self, repo: str, number: int, sha: str, findings: list[dict], summary: str):
        if await self.head(repo, number) != sha:
            return False
        actor = await self.actor()
        base = f"/repos/{repo}"
        comments_path = f"{base}/pulls/{number}/comments"
        existing = await self.pages(comments_path)
        for finding in findings:
            digest = hashlib.sha256(json.dumps([sha, finding], sort_keys=True).encode()).hexdigest()
            marker = f"<!-- ai-reviewer:finding:{digest} -->"
            if any(marker in c["body"] and c["user"]["login"] == actor for c in existing):
                continue
            if await self.head(repo, number) != sha:
                return False
            await self.request("POST", comments_path, json={
                "commit_id": sha, "path": finding["file"], "line": finding["line"],
                "side": finding.get("side", "RIGHT"),
                "body": f"{marker}\n**{finding['severity'].upper()} · {finding['category']}**\n\n{finding['comment']}",
            })
        if await self.head(repo, number) != sha:
            return False
        marker = "<!-- ai-reviewer:summary -->"
        summaries = await self.pages(f"{base}/issues/{number}/comments")
        own = next((c for c in summaries if marker in c["body"] and c["user"]["login"] == actor), None)
        body = f"{marker}\n{summary}\n\nReviewed commit `{sha}`. AI feedback requires human verification."
        if own:
            await self.request("PATCH", f"{base}/issues/comments/{own['id']}", json={"body": body})
        else:
            await self.request("POST", f"{base}/issues/{number}/comments", json={"body": body})
        if await self.head(repo, number) != sha:
            return False
        label = "ai:findings" if findings else "ai:clear"
        opposite = "ai:clear" if findings else "ai:findings"
        labels = await self.pages(f"{base}/labels")
        if not any(item["name"] == label for item in labels):
            try:
                await self.request("POST", f"{base}/labels", json={"name": label, "color": "d4c5f9"})
            except GitHubError as exc:
                if exc.status != 422:  # another worker may have created it
                    raise
        current = await self.pages(f"{base}/issues/{number}/labels")
        if any(item["name"] == opposite for item in current):
            await self.request("DELETE", f"{base}/issues/{number}/labels/{opposite}")
        await self.request("POST", f"{base}/issues/{number}/labels", json={"labels": [label]})
        return True
