"""Module provides service components and helpers."""

import json
from pathlib import Path
from typing import Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "assets" / "public_ppt_v2" / "p3_evidence"


def _load_json(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_svg(name: str, body: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / name
    target.write_text(body, encoding="utf-8")
    return target


def _bars_svg(title: str, labels: List[str], current: List[float], target: List[float]) -> str:
    width = 1200
    height = 680
    max_v = max(target + current + [100.0])
    chart_x = 80
    chart_y = 110
    chart_w = 1020
    chart_h = 460
    group_w = chart_w / len(labels)

    bars = []
    for i, label in enumerate(labels):
        cx = chart_x + i * group_w + 50
        cur_h = (current[i] / max_v) * chart_h
        tar_h = (target[i] / max_v) * chart_h
        cur_y = chart_y + chart_h - cur_h
        tar_y = chart_y + chart_h - tar_h
        bars.append(f'<rect x="{cx}" y="{cur_y:.1f}" width="46" height="{cur_h:.1f}" fill="#38BDF8"/>')
        bars.append(f'<rect x="{cx+52}" y="{tar_y:.1f}" width="46" height="{tar_h:.1f}" fill="#F59E0B"/>')
        bars.append(f'<text x="{cx+24}" y="{chart_y+chart_h+30}" font-size="20" fill="#0F172A">{label}</text>')

    grid = []
    for i in range(0, 11):
        y = chart_y + chart_h - (i / 10.0) * chart_h
        grid.append(f'<line x1="{chart_x}" y1="{y:.1f}" x2="{chart_x+chart_w}" y2="{y:.1f}" stroke="#CBD5E1" stroke-width="1"/>')
        grid.append(f'<text x="20" y="{y+6:.1f}" font-size="14" fill="#475569">{i*10}</text>')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
<rect width="100%" height="100%" fill="#F1F5F9"/>
<text x="80" y="60" font-size="32" fill="#0F172A" font-weight="bold">{title}</text>
<text x="80" y="90" font-size="18" fill="#334155">Current vs Target</text>
{''.join(grid)}
{''.join(bars)}
<rect x="840" y="36" width="16" height="16" fill="#38BDF8"/><text x="864" y="50" font-size="16" fill="#0F172A">Current</text>
<rect x="960" y="36" width="16" height="16" fill="#F59E0B"/><text x="984" y="50" font-size="16" fill="#0F172A">Target</text>
</svg>'''


def _deployment_svg() -> str:
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="680">
<rect width="100%" height="100%" fill="#F8FAFC"/>
<text x="70" y="56" font-size="32" fill="#0F172A" font-weight="bold">Global Active-Active Deployment Snapshot</text>
<text x="70" y="86" font-size="18" fill="#334155">Region A / B / C + Pulsar + Vector DB + Gateway/Runtime/Go services</text>
<rect x="80" y="130" width="320" height="460" rx="12" fill="#DBEAFE" stroke="#93C5FD"/>
<text x="100" y="165" font-size="24" fill="#1E3A8A" font-weight="bold">Region A</text>
<text x="100" y="205" font-size="16" fill="#0F172A">Gateway + Runtime + Go*</text>
<text x="100" y="235" font-size="16" fill="#0F172A">Pulsar Broker (geo-replication)</text>
<text x="100" y="265" font-size="16" fill="#0F172A">Qdrant/Milvus partition A</text>
<rect x="440" y="130" width="320" height="460" rx="12" fill="#DCFCE7" stroke="#86EFAC"/>
<text x="460" y="165" font-size="24" fill="#166534" font-weight="bold">Region B</text>
<text x="460" y="205" font-size="16" fill="#0F172A">Gateway + Runtime + Go*</text>
<text x="460" y="235" font-size="16" fill="#0F172A">Pulsar Broker (geo-replication)</text>
<text x="460" y="265" font-size="16" fill="#0F172A">Qdrant/Milvus partition B</text>
<rect x="800" y="130" width="320" height="460" rx="12" fill="#FCE7F3" stroke="#F9A8D4"/>
<text x="820" y="165" font-size="24" fill="#9D174D" font-weight="bold">Region C</text>
<text x="820" y="205" font-size="16" fill="#0F172A">Gateway + Runtime + Go*</text>
<text x="820" y="235" font-size="16" fill="#0F172A">Pulsar Broker (geo-replication)</text>
<text x="820" y="265" font-size="16" fill="#0F172A">Qdrant/Milvus partition C</text>
<line x1="400" y1="360" x2="440" y2="360" stroke="#334155" stroke-width="2" marker-end="url(#arr)"/>
<line x1="760" y1="360" x2="800" y2="360" stroke="#334155" stroke-width="2" marker-end="url(#arr)"/>
<defs><marker id="arr" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#334155"/></marker></defs>
<text x="70" y="632" font-size="16" fill="#334155">Generated from P3.6 deployment blueprint for PPT usage.</text>
</svg>'''


def _loadtest_svg(report: Dict[str, object]) -> str:
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    req = summary.get("requests", "N/A")
    suc = summary.get("success_rate", "N/A")
    p95 = summary.get("p95_latency_ms", "N/A")
    p99 = summary.get("p99_latency_ms", "N/A")
    avg = summary.get("avg_latency_ms", "N/A")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="680">
<rect width="100%" height="100%" fill="#F8FAFC"/>
<text x="70" y="56" font-size="32" fill="#0F172A" font-weight="bold">Load Test Snapshot</text>
<text x="70" y="86" font-size="18" fill="#334155">Source: stress/report_5k.json</text>
<rect x="90" y="130" width="1020" height="450" rx="14" fill="#FFFFFF" stroke="#CBD5E1"/>
<text x="130" y="210" font-size="28" fill="#0F172A">requests: {req}</text>
<text x="130" y="270" font-size="28" fill="#0F172A">success_rate: {suc}</text>
<text x="130" y="330" font-size="28" fill="#0F172A">avg_latency_ms: {avg}</text>
<text x="130" y="390" font-size="28" fill="#0F172A">p95_latency_ms: {p95}</text>
<text x="130" y="450" font-size="28" fill="#0F172A">p99_latency_ms: {p99}</text>
<text x="130" y="520" font-size="18" fill="#475569">Note: Capacity claim requires distributed multi-region evidence, not local-only benchmark.</text>
</svg>'''


def _gate_svg(decision: Dict[str, object]) -> str:
    action = str(decision.get("action", "rollback"))
    reasons = decision.get("reasons", []) if isinstance(decision.get("reasons", []), list) else []
    reasons_text = '\\n'.join([f"- {r}" for r in reasons[:6]]) if reasons else "- none"
    color = "#16A34A" if action == "promote" else "#DC2626"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="680">
<rect width="100%" height="100%" fill="#F8FAFC"/>
<text x="70" y="56" font-size="32" fill="#0F172A" font-weight="bold">Canary Gate Decision Snapshot</text>
<rect x="90" y="120" width="1020" height="500" rx="14" fill="#FFFFFF" stroke="#CBD5E1"/>
<text x="130" y="210" font-size="42" fill="{color}" font-weight="bold">action: {action}</text>
<text x="130" y="280" font-size="24" fill="#0F172A">reasons:</text>
<text x="130" y="320" font-size="20" fill="#334155" xml:space="preserve">{reasons_text}</text>
<text x="130" y="560" font-size="18" fill="#475569">Source: stress/canary_gate_decision.json</text>
</svg>'''


def main() -> None:
    load_report = _load_json(PROJECT_ROOT / "stress" / "report_5k.json")
    gate_decision = _load_json(PROJECT_ROOT / "stress" / "canary_gate_decision.json")

    generated: List[Path] = []
    generated.append(_save_svg("optimization_score_snapshot.svg", _bars_svg(
        "Optimization Score Snapshot",
        ["性能", "稳定", "可观测", "可维护"],
        [61, 65, 69, 71],
        [88, 90, 86, 92],
    )))
    generated.append(_save_svg("deployment_global_active_active_snapshot.svg", _deployment_svg()))
    generated.append(_save_svg("loadtest_snapshot.svg", _loadtest_svg(load_report)))
    generated.append(_save_svg("canary_gate_snapshot.svg", _gate_svg(gate_decision)))

    index = OUT_DIR / "README.md"
    lines = ["# P3 Evidence Assets", "", "Generated visual assets for PPT and public sharing:", ""]
    for item in generated:
        lines.append(f"- `{item.name}`")
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")

    for item in generated:
        print(f"Generated: {item}")
    print(f"Generated: {index}")


if __name__ == "__main__":
    main()

