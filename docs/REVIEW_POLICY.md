# Review scope and configuration

Put `.ai-reviewer.json` in the repository's default/base branch. Changes to it in
a pull request take effect only after merge. Defaults and a working example are
in the root config file. Unknown fields, invalid enums and excessive budgets
fail the job; they cannot silently disable validation.

- `ignore`: case-sensitive glob patterns matched against repository paths.
  `*` also matches `/` (Python fnmatch semantics).
- `min_severity`: low, medium (default), high, critical.
- `categories`: bug, security, performance, maintainability.
- `max_files`: 1–50 files per job, default 20.
- `max_file_chars`: 500–20000 patch characters per model call, default 12000.
- `max_total_chars`: 500–200000 patch characters per job, default 60000.

Each eligible file is sent as a whole patch; no patch is silently truncated.
Binary, unavailable, truncated or oversized patches are reported as skipped.
If GitHub returns fewer files than the PR's changed-file count, coverage is
partial. Findings must reference an actual commentable location in that patch.
Model output truncated by its token limit is rejected, not interpreted as clean.

Summary comments state configured severity/category scope. `ai:clear` means no
qualifying findings within a completely reviewed configured scope, not human
approval. Incomplete coverage always gets `ai:partial`. The job retains reviewed,
ignored and skipped files plus reasons and actual token usage.

Model input is treated as untrusted data. Prompt instructions reduce injection
risk; they do not prove resistance. Findings require human verification. No code
from a PR is executed by this service.
