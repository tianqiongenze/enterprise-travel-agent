# Capacity & Cost Model (P2)

## Goal

Provide a reproducible planning model for:

- global active-active deployment
- 1M+ connected session planning envelope
- monthly infrastructure budget baseline

## Model Inputs

- `peak_connected`
- `active_ratio`
- `gateway_conn_per_pod`
- `runtime_active_per_pod`
- `safety_factor`
- `hours_per_month`
- `gateway_pod_cost_per_hour`
- `runtime_pod_cost_per_hour`
- `pulsar_cluster_cost_per_month`
- `vector_cluster_cost_per_month`

## Formulas

- `peak_active = peak_connected * active_ratio`
- `gateway_pods = ceil((peak_connected / gateway_conn_per_pod) * safety_factor)`
- `runtime_pods = ceil((peak_active / runtime_active_per_pod) * safety_factor)`
- `monthly_cost = gateway + runtime + pulsar + vector`

## Run

```bash
python stress/capacity_cost_model.py \
  --peak-connected 1000000 \
  --active-ratio 0.1 \
  --gateway-conn-per-pod 12000 \
  --runtime-active-per-pod 100 \
  --safety-factor 1.8
```

Outputs:

- `stress/capacity_cost_report.json`
- `stress/capacity_cost_report.md`

## Notes

- This model is for planning and budgeting, not final performance evidence.
- Production claim must include distributed benchmark, canary reports, and rollback drill evidence.

