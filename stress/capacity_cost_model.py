"""Module provides service components and helpers."""

import argparse
import json
from dataclasses import dataclass, asdict


@dataclass
class CapacityInput:
    peak_connected: int
    active_ratio: float
    gateway_conn_per_pod: int
    runtime_active_per_pod: int
    safety_factor: float
    hours_per_month: int
    gateway_pod_cost_per_hour: float
    runtime_pod_cost_per_hour: float
    pulsar_cluster_cost_per_month: float
    vector_cluster_cost_per_month: float


@dataclass
class CapacityOutput:
    peak_active: int
    gateway_pods: int
    runtime_pods: int
    gateway_monthly_cost: float
    runtime_monthly_cost: float
    platform_monthly_cost: float
    total_monthly_cost: float
    recommended_partitions: int
    runtime_per_partition: int


def ceil_div(value: float) -> int:
    if value <= 0:
        return 0
    iv = int(value)
    return iv if iv == value else iv + 1


def estimate(input_data: CapacityInput) -> CapacityOutput:
    peak_active = int(input_data.peak_connected * input_data.active_ratio)
    gateway_pods = ceil_div((input_data.peak_connected / input_data.gateway_conn_per_pod) * input_data.safety_factor)
    runtime_pods = ceil_div((peak_active / input_data.runtime_active_per_pod) * input_data.safety_factor)

    gateway_monthly = gateway_pods * input_data.gateway_pod_cost_per_hour * input_data.hours_per_month
    runtime_monthly = runtime_pods * input_data.runtime_pod_cost_per_hour * input_data.hours_per_month
    platform_monthly = input_data.pulsar_cluster_cost_per_month + input_data.vector_cluster_cost_per_month
    recommended_partitions = max(3, ceil_div(peak_active / 8000))
    runtime_per_partition = ceil_div(runtime_pods / recommended_partitions)

    return CapacityOutput(
        peak_active=peak_active,
        gateway_pods=gateway_pods,
        runtime_pods=runtime_pods,
        gateway_monthly_cost=round(gateway_monthly, 2),
        runtime_monthly_cost=round(runtime_monthly, 2),
        platform_monthly_cost=round(platform_monthly, 2),
        total_monthly_cost=round(gateway_monthly + runtime_monthly + platform_monthly, 2),
        recommended_partitions=recommended_partitions,
        runtime_per_partition=runtime_per_partition,
    )


def to_markdown(input_data: CapacityInput, output: CapacityOutput) -> str:
    lines = [
        '# Capacity & Cost Estimation',
        '',
        '## Inputs',
        '',
        '| Key | Value |',
        '|---|---:|',
    ]
    for key, value in asdict(input_data).items():
        lines.append(f'| {key} | {value} |')

    lines.extend([
        '',
        '## Output',
        '',
        '| Metric | Value |',
        '|---|---:|',
    ])
    for key, value in asdict(output).items():
        lines.append(f'| {key} | {value} |')

    lines.extend([
        '',
        '## Notes',
        '',
        '- This is planning estimation, not production evidence.',
        '- Final claim must include distributed benchmark and canary reports.',
    ])
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description='Capacity and cost estimator for global active-active deployment')
    parser.add_argument('--peak-connected', type=int, default=1_000_000)
    parser.add_argument('--active-ratio', type=float, default=0.10)
    parser.add_argument('--gateway-conn-per-pod', type=int, default=12000)
    parser.add_argument('--runtime-active-per-pod', type=int, default=100)
    parser.add_argument('--safety-factor', type=float, default=1.8)
    parser.add_argument('--hours-per-month', type=int, default=730)
    parser.add_argument('--gateway-pod-cost-per-hour', type=float, default=0.08)
    parser.add_argument('--runtime-pod-cost-per-hour', type=float, default=0.12)
    parser.add_argument('--pulsar-cluster-cost-per-month', type=float, default=3500.0)
    parser.add_argument('--vector-cluster-cost-per-month', type=float, default=4200.0)
    parser.add_argument('--out-json', default='stress/capacity_cost_report.json')
    parser.add_argument('--out-md', default='stress/capacity_cost_report.md')
    args = parser.parse_args()

    input_data = CapacityInput(
        peak_connected=args.peak_connected,
        active_ratio=args.active_ratio,
        gateway_conn_per_pod=args.gateway_conn_per_pod,
        runtime_active_per_pod=args.runtime_active_per_pod,
        safety_factor=args.safety_factor,
        hours_per_month=args.hours_per_month,
        gateway_pod_cost_per_hour=args.gateway_pod_cost_per_hour,
        runtime_pod_cost_per_hour=args.runtime_pod_cost_per_hour,
        pulsar_cluster_cost_per_month=args.pulsar_cluster_cost_per_month,
        vector_cluster_cost_per_month=args.vector_cluster_cost_per_month,
    )
    output = estimate(input_data)

    report = {
        'input': asdict(input_data),
        'output': asdict(output),
    }

    with open(args.out_json, 'w', encoding='utf-8') as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)

    with open(args.out_md, 'w', encoding='utf-8') as fp:
        fp.write(to_markdown(input_data, output))

    print(f'Generated: {args.out_json}')
    print(f'Generated: {args.out_md}')


if __name__ == '__main__':
    main()

