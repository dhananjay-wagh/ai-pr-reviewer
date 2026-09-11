"""Run separately: python -m app.worker."""
import asyncio
import logging
import os
import signal
import time

import httpx

from app.github import GitHub, GitHubError
from app.reviews import validate_locations
from app.store import Store
from app.utils import get_code_review

log = logging.getLogger("reviewer.worker")


async def review_job(job):
    github = GitHub(os.environ["GITHUB_TOKEN"])
    if await github.head(job["repo"], job["number"]) != job["sha"]:
        return "superseded", {}
    diff = await github.diff(job["repo"], job["number"])
    if len(diff) > 8000:
        raise ValueError("Diff exceeds review limit; no approval issued")
    findings = await get_code_review(diff) if diff else []
    if findings is None:
        raise ValueError("Model review failed validation or generation")
    validate_locations(findings, diff)
    summary = f"## AI review\n\n{len(findings)} findings. Full diff reviewed."
    published = await github.publish(job["repo"], job["number"], job["sha"], findings, summary)
    return ("completed" if published else "superseded"), {"findings": findings}


async def run_once(db: Store):
    job = db.claim()
    if not job:
        return False
    started = time.monotonic()
    async def renew():
        while True:
            await asyncio.sleep(30)
            if not db.heartbeat(job):
                raise RuntimeError("Lost job lease")
    task = asyncio.create_task(review_job(job))
    heartbeat = asyncio.create_task(renew())
    try:
        done, _ = await asyncio.wait((task, heartbeat), timeout=600, return_when=asyncio.FIRST_COMPLETED)
        if heartbeat in done:
            heartbeat.result()
        if task not in done:
            raise TimeoutError("Review job exceeded deadline")
        status, result = task.result()
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        db.finish(job, status, result=result)
        log.info("job_finished id=%s status=%s duration=%.3f", job["id"], status, time.monotonic()-started)
    except Exception as exc:
        retry = isinstance(exc, (httpx.TransportError, TimeoutError)) or isinstance(exc, GitHubError) and exc.retryable
        db.finish(job, "failed", error=type(exc).__name__, retry=retry)
        log.warning("job_failed id=%s error=%s retry=%s", job["id"], type(exc).__name__, retry)
    finally:
        task.cancel()
        heartbeat.cancel()
        await asyncio.gather(task, heartbeat, return_exceptions=True)
    return True


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))
    db = Store(os.getenv("DATABASE_PATH", "data/reviewer.db"))
    while not stop.is_set():
        if not await run_once(db):
            try:
                await asyncio.wait_for(stop.wait(), timeout=1)
            except TimeoutError:
                pass


if __name__ == "__main__":
    asyncio.run(main())
