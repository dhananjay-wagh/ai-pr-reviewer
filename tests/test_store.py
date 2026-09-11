from app.store import Store


def test_persistence_and_exclusive_claim(tmp_path):
    path = str(tmp_path / "jobs.db")
    one, two = Store(path), Store(path)
    job_id, created = one.enqueue("delivery", "o/r", 1, "abc")
    assert created
    assert two.enqueue("delivery", "o/r", 1, "abc") == (job_id, False)
    assert two.enqueue("other-delivery", "o/r", 1, "abc") == (job_id, False)
    job = one.claim()
    assert job["id"] == job_id
    assert two.claim() is None
    one.finish(job, "completed", {"findings": []})
    assert two.get(job_id)["status"] == "completed"


def test_expired_lease_recovery_and_owner_fencing(tmp_path):
    db = Store(str(tmp_path / "jobs.db"))
    job_id, _ = db.enqueue("d", "o/r", 1, "abc")
    old = db.claim(lease_seconds=-1)
    new = db.claim()
    assert new["attempts"] == 2
    db.finish(old, "completed")
    assert db.get(job_id)["status"] == "running"
    db.finish(new, "failed")
    assert db.get(job_id)["status"] == "failed"


def test_jobs_for_same_pr_do_not_publish_concurrently(tmp_path):
    db = Store(str(tmp_path / "jobs.db"))
    db.enqueue("d1", "o/r", 1, "abc")
    db.enqueue("d2", "o/r", 1, "def")
    first = db.claim()
    assert db.claim() is None
    db.finish(first, "superseded")
    assert db.claim()["sha"] == "def"
