# P3 Evidence Assets for PPT

## Purpose

Generate ready-to-use visual evidence assets for optimization, load test, deployment, and canary gate.

## Generator

- Script: `deploy/scripts/generate_p3_evidence_assets.py`

## Output Directory

- `assets/public_ppt_v2/p3_evidence/`

## Generated Files

- `optimization_score_snapshot.svg`
- `deployment_global_active_active_snapshot.svg`
- `loadtest_snapshot.svg`
- `canary_gate_snapshot.svg`
- `README.md` (asset index)

## Run

```bash
python deploy/scripts/generate_p3_evidence_assets.py
```

These files are intended for direct use in future PPT generation scripts.

