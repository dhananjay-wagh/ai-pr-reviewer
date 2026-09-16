"""Run separately: python -m app.worker."""

import asyncio
import logging
import os
import signal
import time

import httpx

from app.auth import github_for_job
from app.engine import analyze, summary
from app.github import GitHubError
from app.model import ModelError
from app.store import Store

log = logging.getLogger("reviewer.worker")


async def review_job(job):
    github = await github_for_job(job)
    result = await analyze(github, job["repo"], job["number"], job["sha"])
    if result is None:
        return "superseded", {}
    published = await github.publish(
        job["repo"],
        job["number"],
        job["sha"],
        result["findings"],
        summary(result),
        complete=result["complete"],
    )
    return ("completed" if published else "superseded"), result


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
        done, _ = await asyncio.wait(
            (task, heartbeat), timeout=600, return_when=asyncio.FIRST_COMPLETED
        )
        if heartbeat in done:
            heartbeat.result()
        if task not in done:
            raise TimeoutError("Review job exceeded deadline")
        status, result = task.result()
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        db.finish(job, status, result=result)
        log.info(
            "job_finished id=%s status=%s duration=%.3f",
            job["id"],
            status,
            time.monotonic() - started,
        )
    except Exception as exc:
        retry = (
            isinstance(exc, (httpx.TransportError, TimeoutError))
            or isinstance(exc, (GitHubError, ModelError))
            and exc.retryable
        )
        category = exc.reason if isinstance(exc, ModelError) else type(exc).__name__
        db.finish(
            job, "failed", error=category, retry=retry, retry_delay=getattr(exc, "retry_after", 0)
        )
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
