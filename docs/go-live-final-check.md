# Go-Live Final Check Script

## Overview

`deploy/scripts/go_live_final_check.py` runs a one-shot pre-release acceptance suite and emits:

- `stress/go_live_final_report.json`

It validates canary decision artifacts, event-consumer thresholds, Python test suite, capacity/cost artifacts, and Java compile health.

## Quick Run

```bash
python deploy/scripts/go_live_final_check.py --project-root . --report-out stress/go_live_final_report.json
```

## Output

The JSON report includes:

- `summary.overall` (`PASS` or `FAIL`)
- `passCount`, `failCount`, `skipCount`
- per-check details (status, duration, artifacts)

## Notes

- If canary action is `rollback`, overall will fail.
- If Maven is unavailable, Java compile check is marked `SKIP`.
- Event thresholds are configurable:
  - `--max-event-lag`
  - `--max-event-dlq`

