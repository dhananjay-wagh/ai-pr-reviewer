# Five-minute demo

## Offline, no credentials needed for model/GitHub

1. Follow the development install instructions.
2. Run `python -m scripts.seed_demo --database data/demo.db`.
3. Point `DATABASE_PATH` to `data/demo.db` and set a temporary dashboard token.
4. Start the API and open `/dashboard`.
5. Show the payments example, its synthetic finding and reviewed commit.
6. Show the partial pipeline example and explain skipped files.
7. Disconnect to demonstrate the protected-data boundary.

All rows are labeled DEMO. This demonstrates the UI, not live GitHub integration.

## Automated engineering demo

Run `python -m pytest tests/test_pipeline.py tests/test_retries.py -v` to show
the signed delivery, durable processing, malformed location rejection, failed
publication handling and checkpoint reuse. No external messages are posted.

Open `evaluation/results/groq-bugs-v2.json` and explain one correct finding and
one false positive. The report records an actual Groq run on synthetic cases.

## Live GitHub acceptance checklist

After configuring your own HTTPS host and GitHub App installation:

1. Merge `.ai-reviewer.json` into a demo repository's base branch.
2. Open a small PR containing a clear bug. Verify a 202 webhook delivery, one
   completed job, an inline finding, a summary and an `ai:findings` label.
3. Redeliver the same event. Verify the returned job ID is unchanged and no
   duplicate comment appears.
4. Fix the bug with a new commit. Verify a new job and updated summary. Review
   `ai:clear` as an advisory result, not human approval.
5. Introduce an intentionally oversized file. Verify skipped coverage and
   `ai:partial`; inspect its reason in Review desk.
6. Push a newer commit while a job runs. Verify the older job becomes superseded
   when it observes the changed head.

Record actual outcomes and public PR links after running these steps. Do not
substitute the synthetic screenshots for live acceptance evidence.
