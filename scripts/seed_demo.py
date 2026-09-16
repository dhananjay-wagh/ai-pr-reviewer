"""Seed clearly labeled synthetic UI data; never contacts GitHub or Groq."""

import argparse

from app.store import Store


def seed(path):
    db = Store(path)
    existing = db.recent()
    if existing:
        if all(job.get("result", {}).get("demo") for job in existing if job.get("result")) and all(
            job.get("result") for job in existing
        ):
            return db
        raise ValueError("Demo seeding requires an empty database; use a separate demo path")
    for index, (repo, findings, complete) in enumerate(
        [
            (
                "demo/payments-api",
                [
                    dict(
                        file="app/transfers.py",
                        line=34,
                        side="RIGHT",
                        severity="high",
                        category="bug",
                        comment="The debit is committed before the credit. If the second update fails, funds are lost. Use a single transaction.",
                    )
                ],
                True,
            ),
            ("demo/web-client", [], True),
            ("demo/data-pipeline", [], False),
        ]
    ):
        job_id, created = db.enqueue(f"demo-{index}", repo, index + 12, str(index + 1) * 40)
        if created:
            job = db.claim()
            db.finish(
                job,
                "completed",
                {
                    "demo": True,
                    "findings": findings,
                    "complete": complete,
                    "reviewed_files": ["app/transfers.py"] if findings else ["src/main.py"],
                    "ignored_files": [],
                    "skipped_files": []
                    if complete
                    else [{"file": "archive.bin", "reason": "binary patch"}],
                    "duration_seconds": 2.4 + index,
                    "prompt_tokens": 1100,
                    "completion_tokens": 180,
                    "model": "synthetic-demo",
                },
            )
    return db


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="data/demo.db")
    args = parser.parse_args()
    seed(args.database)
    print(
        f"Synthetic demo data seeded in {args.database}. Set DATABASE_PATH to this path to preview."
    )
