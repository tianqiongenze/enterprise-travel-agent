"""Module provides service components and helpers."""

from pathlib import Path
from html import escape
from typing import List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "assets" / "public_ppt_v2" / "code_evidence"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def read_snippet(rel_path: str, start: int, end: int, max_lines: int = 20) -> str:
    target = PROJECT_ROOT / rel_path
    if not target.exists():
        return f"# file not found: {rel_path}"
    lines = target.read_text(encoding="utf-8").splitlines()
    picked = lines[max(0, start - 1): min(len(lines), end)][:max_lines]
    if (end - start + 1) > max_lines:
        picked.append("# ...truncated...")
    return "\n".join(picked)


def render_code_card(title: str, rel_path: str, snippet: str, notes: List[str]) -> str:
    code_lines = snippet.splitlines()
    line_h = 18
    code_h = max(260, 40 + len(code_lines) * line_h)
    height = max(720, code_h + 180)

    y = 170
    code_text = []
    for i, line in enumerate(code_lines):
        code_text.append(
            f'<text x="90" y="{y + i * line_h}" font-size="14" font-family="Consolas" fill="#E2E8F0">{escape(line)}</text>'
        )

    note_items = []
    ny = 220
    for note in notes[:6]:
        note_items.append(f'<text x="980" y="{ny}" font-size="16" font-family="Microsoft YaHei" fill="#0F172A">• {escape(note)}</text>')
        ny += 34

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="{height}">
<rect width="100%" height="100%" fill="#F8FAFC"/>
<text x="70" y="60" font-size="34" font-family="Microsoft YaHei" fill="#0F172A" font-weight="bold">{escape(title)}</text>
<text x="70" y="95" font-size="18" font-family="Microsoft YaHei" fill="#334155">{escape(rel_path)}</text>
<rect x="70" y="120" width="860" height="{code_h}" rx="12" fill="#0B1220" stroke="#1E293B"/>
{''.join(code_text)}
<rect x="960" y="120" width="370" height="{code_h}" rx="12" fill="#FFFFFF" stroke="#BFDBFE"/>
<text x="980" y="170" font-size="22" font-family="Microsoft YaHei" fill="#1E3A8A" font-weight="bold">代码讲解注释</text>
{''.join(note_items)}
<text x="70" y="{height-35}" font-size="15" font-family="Microsoft YaHei" fill="#475569">Generated for public teaching PPT (code screenshot + annotations)</text>
</svg>'''


def build_assets() -> List[Path]:
    specs: List[Tuple[str, str, int, int, List[str], str]] = [
        (
            "runtime_orchestrator_card.svg",
            "services/techgroup-enterprise-travel-runtime/src/travel_agent/orchestrator.py",
            1,
            120,
            [
                "编排入口初始化注册中心、事件总线、技能与记忆层。",
                "支持 InMemory/Redis/RocksDB/Vector 四种记忆后端。",
                "A2A 路由消息被审计并写入日志。",
                "推荐前后事件会发布到事件总线。",
            ],
            "Python Orchestrator Core",
        ),
        (
            "runtime_api_card.svg",
            "services/techgroup-enterprise-travel-runtime/src/travel_agent/api/app.py",
            1,
            120,
            [
                "API 层处理签名校验与trace透传。",
                "将请求映射为 Runtime contract。",
                "返回结构化推荐结果与审计信息。",
            ],
            "Python Runtime API",
        ),
        (
            "event_consumer_card.svg",
            "services/techgroup-enterprise-travel-runtime/src/travel_agent/events/consumer.py",
            1,
            170,
            [
                "消费者支持重试、退避和DLQ。",
                "指标输出为 Prometheus 文本格式。",
                "可将事件落盘形成审计证据。",
            ],
            "Event Consumer with Retry/DLQ",
        ),
        (
            "gateway_policy_guard_card.svg",
            "services/techgroup-enterprise-travel-gateway/src/main/java/edu/enterprise/travel/gateway/service/PolicyGuardService.java",
            1,
            190,
            [
                "策略服务支持 Go 后端与 canary 分流。",
                "加入短 TTL 缓存优化高并发重复策略调用。",
                "暴露 cacheStats 便于上线窗口观测。",
            ],
            "Java Policy Guard Service",
        ),
        (
            "gateway_controller_card.svg",
            "services/techgroup-enterprise-travel-gateway/src/main/java/edu/enterprise/travel/gateway/api/TravelGatewayController.java",
            1,
            120,
            [
                "网关统一入口对接 runtime。",
                "响应中带 traceId 与结构化结果卡片字段。",
                "新增策略缓存统计接口用于发布观测。",
            ],
            "Java Gateway Controller",
        ),
        (
            "go_ranker_card.svg",
            "services/techgroup-enterprise-travel-ranker-go/main.go",
            1,
            120,
            [
                "Go 组件承接高并发重排。",
                "按技能权重做分值汇总。",
                "提供低延迟评分能力。",
            ],
            "Go Ranker",
        ),
        (
            "frontend_app_card.svg",
            "apps/techgroup-enterprise-travel-web/src/App.jsx",
            1,
            180,
            [
                "Web 前端表单提交与结果卡片展示。",
                "支持 raw JSON 与卡片模式切换。",
                "保存会话默认值用于课堂复现。",
            ],
            "Frontend Web App",
        ),
        (
            "miniapp_index_card.svg",
            "miniapp-wechat/pages/index/index.js",
            1,
            140,
            [
                "小程序端字段校验与请求构造。",
                "记录埋点事件支持教学分析。",
                "返回结果同时保留卡片和原始JSON。",
            ],
            "Mini Program Index Page",
        ),
    ]

    generated: List[Path] = []
    for filename, rel_path, start, end, notes, title in specs:
        snippet = read_snippet(rel_path, start, end)
        svg = render_code_card(title, rel_path, snippet, notes)
        target = OUT_DIR / filename
        target.write_text(svg, encoding="utf-8")
        generated.append(target)
    return generated


def main() -> None:
    generated = build_assets()
    index = OUT_DIR / "README.md"
    lines = ["# Code Evidence Assets", "", "Generated code screenshot cards with annotations:", ""]
    for item in generated:
        lines.append(f"- `{item.name}`")
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")

    for item in generated:
        print(f"Generated: {item}")
    print(f"Generated: {index}")


if __name__ == "__main__":
    main()

