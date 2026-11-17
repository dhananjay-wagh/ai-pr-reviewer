"""SQLite durable queue; API and workers share a local disk volume."""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                  id TEXT PRIMARY KEY, repo TEXT NOT NULL, number INTEGER NOT NULL,
                  sha TEXT NOT NULL, installation INTEGER, status TEXT NOT NULL,
                  attempts INTEGER NOT NULL DEFAULT 0, available REAL NOT NULL,
                  lease_until REAL NOT NULL DEFAULT 0, owner TEXT,
                  created REAL NOT NULL, updated REAL NOT NULL,
                  result TEXT, error TEXT, UNIQUE(repo, number, sha));
                CREATE TABLE IF NOT EXISTS deliveries (
                  id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id));
                CREATE INDEX IF NOT EXISTS jobs_ready ON jobs(status, available);
                CREATE TABLE IF NOT EXISTS retry_audit (
                  job_id TEXT NOT NULL, requested_at REAL NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def enqueue(self, delivery, repo, number, sha, installation=None):
        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            seen = db.execute("SELECT job_id FROM deliveries WHERE id=?", (delivery,)).fetchone()
            if seen:
                return seen[0], False
            existing = db.execute(
                "SELECT id FROM jobs WHERE repo=? AND number=? AND sha=?", (repo, number, sha)
            ).fetchone()
            job_id = existing[0] if existing else uuid.uuid4().hex
            if not existing:
                db.execute(
                    "INSERT INTO jobs (id,repo,number,sha,installation,status,available,created,updated) VALUES (?,?,?,?,?,'queued',?,?,?)",
                    (job_id, repo, number, sha, installation, now, now, now),
                )
            db.execute("INSERT INTO deliveries VALUES (?,?)", (delivery, job_id))
            return job_id, not bool(existing)

    def claim(self, lease_seconds=120):
        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE jobs SET status='failed',error='worker lease expired',updated=? WHERE status='running' AND lease_until<? AND attempts>=3",
                (now, now),
            )
            row = db.execute(
                """SELECT * FROM jobs j WHERE
                ((status='queued' AND available<=?) OR (status='running' AND lease_until<?))
                AND attempts<3 AND NOT EXISTS (
                  SELECT 1 FROM jobs other WHERE other.repo=j.repo AND other.number=j.number
                  AND other.id!=j.id AND other.status='running' AND other.lease_until>=?)
                ORDER BY created LIMIT 1""",
                (now, now, now),
            ).fetchone()
            if not row:
                return None
            owner = uuid.uuid4().hex
            db.execute(
                "UPDATE jobs SET status='running', attempts=attempts+1, owner=?,lease_until=?,updated=? WHERE id=?",
                (owner, now + lease_seconds, now, row["id"]),
            )
            return dict(db.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone())

    def heartbeat(self, job):
        with self.connect() as db:
            return (
                db.execute(
                    "UPDATE jobs SET lease_until=? WHERE id=? AND owner=? AND status='running'",
                    (time.time() + 120, job["id"], job["owner"]),
                ).rowcount
                == 1
            )

    def checkpoint(self, job, result):
        """Persist validated analysis before any GitHub writes."""
        with self.connect() as db:
            changed = db.execute(
                "UPDATE jobs SET result=?,updated=? WHERE id=? AND owner=? AND status='running'",
                (json.dumps(result), time.time(), job["id"], job["owner"]),
            ).rowcount
        if not changed:
            raise RuntimeError("Lost job lease before publication")

    def retry_failed(self, job_id):
        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE jobs SET status='queued',attempts=0,error=NULL,available=?,updated=?,owner=NULL,lease_until=0 WHERE id=? AND status='failed'",
                (now, now, job_id),
            ).rowcount
            if changed:
                db.execute("INSERT INTO retry_audit VALUES (?,?)", (job_id, now))
            return bool(changed)

    def finish(self, job, status, result=None, error=None, retry=False, retry_delay=0):
        now = time.time()
        if retry and job["attempts"] < 3:
            status = "queued"
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET status=?, result=COALESCE(?,result), error=?, updated=?, available=?, lease_until=0 WHERE id=? AND owner=? AND status='running'",
                (
                    status,
                    json.dumps(result) if result is not None else None,
                    error,
                    now,
                    now + max(retry_delay, 2 ** job["attempts"]),
                    job["id"],
                    job["owner"],
                ),
            )

    def get(self, job_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return self.public(row) if row else None

    def recent(self, limit=50, before=None):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM jobs WHERE (? IS NULL OR created<?) ORDER BY created DESC,id DESC LIMIT ?",
                (before, before, limit),
            ).fetchall()
            return [self.public(row) for row in rows]

    def metrics(self):
        with self.connect() as db:
            counts = {
                row["status"]: row["n"]
                for row in db.execute("SELECT status,COUNT(*) AS n FROM jobs GROUP BY status")
            }
            rows = db.execute(
                "SELECT result FROM jobs WHERE status='completed' AND result IS NOT NULL ORDER BY updated DESC LIMIT 100"
            ).fetchall()
        results = [json.loads(row["result"]) for row in rows]
        import statistics

        durations = [r["duration_seconds"] for r in results if "duration_seconds" in r]
        return {
            "jobs_by_status": counts,
            "sample_size": len(results),
            "median_review_seconds": statistics.median(durations) if durations else None,
            "prompt_tokens": sum(r.get("prompt_tokens", 0) for r in results),
            "completion_tokens": sum(r.get("completion_tokens", 0) for r in results),
            "partial_reviews": sum(not r.get("complete", True) for r in results),
        }

    @staticmethod
    def public(row):
        value = dict(row)
        value.pop("owner", None)
        value.pop("installation", None)
        value["result"] = json.loads(value["result"]) if value["result"] else None
        return value
