# Evaluation methodology

Run the no-network harness check:

```sh
python -m evaluation.run --output reports/dry-run.json
```

It uses an empty-finding baseline; its zero recall is **not a model result**.
Run the actual model benchmark explicitly (uses Groq credits):

```sh
python -m evaluation.run --live --output reports/groq-v2.json
```

The versioned dataset contains 30 small Python/JavaScript cases: 20 seeded-defect
cases and 10 clean controls. Each has a rationale, acceptable defect locations
and category. The model sees only the diff, never the expected labels.

Reports include raw findings, expected labels, failures, latency, model/prompt
version, dataset SHA-256 and actual token usage. Matching is one-to-one by file, acceptable line
and category. Duplicate predictions count as false positives; failures retain
false negatives. Precision is null when no findings are predicted. Invalid line
locations are counted separately. Cost is not estimated from potentially stale
provider pricing; use report token counts and your billed rates.

**Location/category precision and recall are proxies, not semantic correctness.**
A comment can match the expected line yet explain the wrong issue. Manually
adjudicate every matched comment before quoting defect precision on a resume.
Small synthetic examples do not establish performance on real repositories.
Reports are private by default; do not commit reports containing private code.

To compare prompt/model versions, preserve separate report files and run the same
dataset with the same model settings. Include the dataset's Git commit in any
published result. Add real, independently labeled PR cases as the project grows.

## Recorded live run

`evaluation/results/groq-bugs-v2.json` records a real run using
`openai/gpt-oss-120b`: 30 cases, zero failed cases, zero invalid locations,
55.2% location/category precision and 80.0% recall. Median case latency was
1.85 seconds including any retries; 7,722 prompt tokens and 8,064 completion
tokens were reported. These are synthetic proxy metrics, not production quality
or human-adjudicated defect precision. Extra findings and category differences
reduce the score; inspect the complete report before drawing conclusions.

An earlier run encountered eight provider failures. The harness now retries
transient model errors with bounded backoff and workers persist provider retry
delays. A successful rerun does not guarantee future provider availability.
