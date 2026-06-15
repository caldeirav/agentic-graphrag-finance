# Benchmark Reproduction

Paper benchmark reproduction uses the **custom-judge v2.0.0** bundle and **`paper-v1.0`** release lock.

**Canonical guide:** [research-reproduction.md](research-reproduction.md)

```bash
uv run agent-query repro run-all \
  --manifest releases/paper-v1.0/manifest.yaml \
  --output reports/repro-paper-v1.0 \
  --defer-judge --no-resume
```

The committed baseline (`releases/paper-v1.0/expected_checksums.json`) matches the lock reproduction run stored locally at `reports/repro-paper-v1.0/`.

Legacy `sec-benchmark` / `evaluation.cli` notes below are for ad-hoc single-snapshot experiments only—not the paper tables.

```bash
USE_MOCK_LLM=0 USE_MOCK_JUDGE=0 uv run python -m evaluation.cli \
  --suite pilot \
  --snapshot-id <snapshot_id> \
  --issuer-id <cik> \
  --datasets finder,finagentbench,financebench \
  --max-items 100
```
