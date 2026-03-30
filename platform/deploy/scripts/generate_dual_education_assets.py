"""Module provides service components and helpers."""

from pathlib import Path


OUT_DIR = Path(__file__).resolve().parents[2] / "assets" / "public_ppt_v2" / "dual_evidence"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def svg_timeline() -> str:
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="720">
<rect width="100%" height="100%" fill="#F8FBFF"/>
<text x="70" y="60" font-size="34" fill="#0F172A" font-weight="bold">German Dual System Teaching Rhythm</text>
<text x="70" y="92" font-size="18" fill="#334155">Classroom theory + enterprise task + code evidence + verification</text>
<line x1="100" y1="280" x2="1300" y2="280" stroke="#93C5FD" stroke-width="6"/>
<g fill="#FFFFFF" stroke="#60A5FA" stroke-width="4">
  <rect x="80" y="200" rx="16" width="170" height="160"/>
  <rect x="280" y="200" rx="16" width="170" height="160"/>
  <rect x="480" y="200" rx="16" width="170" height="160"/>
  <rect x="680" y="200" rx="16" width="170" height="160"/>
  <rect x="880" y="200" rx="16" width="170" height="160"/>
  <rect x="1080" y="200" rx="16" width="170" height="160"/>
</g>
<g font-family="Arial" font-size="20" fill="#0F172A">
  <text x="105" y="250" font-weight="bold">Week 1-2</text><text x="105" y="285">Theory</text><text x="105" y="315">Context</text>
  <text x="305" y="250" font-weight="bold">Week 3-4</text><text x="305" y="285">Analysis</text><text x="305" y="315">User story</text>
  <text x="505" y="250" font-weight="bold">Week 5-6</text><text x="505" y="285">Design</text><text x="505" y="315">Architecture</text>
  <text x="705" y="250" font-weight="bold">Week 7-10</text><text x="705" y="285">Backend</text><text x="705" y="315">APIs</text>
  <text x="905" y="250" font-weight="bold">Week 11-13</text><text x="905" y="285">Test</text><text x="905" y="315">Quality</text>
  <text x="1105" y="250" font-weight="bold">Week 14-16</text><text x="1105" y="285">Release</text><text x="1105" y="315">Ops</text>
</g>
<text x="70" y="600" font-size="18" fill="#475569">Use: introduction slides, timeline slides, and training schedule overview.</text>
</svg>'''


def svg_cycle() -> str:
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="720">
<rect width="100%" height="100%" fill="#F8FAFC"/>
<text x="70" y="60" font-size="34" fill="#0F172A" font-weight="bold">Enterprise Delivery Cycle</text>
<text x="70" y="92" font-size="18" fill="#334155">analysis → design → backend → frontend → test → load test → iteration → release</text>
<g font-family="Arial" font-size="20" fill="#0F172A" font-weight="bold">
<rect x="70" y="160" width="160" height="90" rx="14" fill="#DBEAFE" stroke="#60A5FA"/><text x="110" y="214">Analysis</text>
<rect x="250" y="160" width="160" height="90" rx="14" fill="#E0F2FE" stroke="#38BDF8"/><text x="292" y="214">Design</text>
<rect x="430" y="160" width="160" height="90" rx="14" fill="#DCFCE7" stroke="#22C55E"/><text x="470" y="214">Backend</text>
<rect x="610" y="160" width="160" height="90" rx="14" fill="#FEF3C7" stroke="#F59E0B"/><text x="648" y="214">Frontend</text>
<rect x="790" y="160" width="160" height="90" rx="14" fill="#FCE7F3" stroke="#F472B6"/><text x="848" y="214">Test</text>
<rect x="970" y="160" width="160" height="90" rx="14" fill="#E9D5FF" stroke="#A855F7"/><text x="1000" y="214">Load Test</text>
<rect x="1150" y="160" width="160" height="90" rx="14" fill="#FFE4E6" stroke="#FB7185"/><text x="1186" y="214">Release</text>
</g>
<g stroke="#94A3B8" stroke-width="4" fill="none" marker-end="url(#arr)">
<path d="M230 205 L250 205"/><path d="M410 205 L430 205"/><path d="M590 205 L610 205"/><path d="M770 205 L790 205"/><path d="M950 205 L970 205"/><path d="M1130 205 L1150 205"/>
</g>
<defs><marker id="arr" markerWidth="12" markerHeight="12" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#94A3B8"/></marker></defs>
<rect x="90" y="340" width="1220" height="240" rx="18" fill="#FFFFFF" stroke="#CBD5E1"/>
<text x="120" y="390" font-size="22" fill="#0F172A">Artifacts</text>
<text x="120" y="430" font-size="18" fill="#334155">docs → code → tests → benchmarks → deployment → runbook → final report</text>
<text x="120" y="470" font-size="18" fill="#334155">Each phase produces evidence for public sharing and release gating.</text>
<text x="120" y="510" font-size="18" fill="#334155">This is the exact rhythm used in dual education: learn, apply, verify, reflect.</text>
</svg>'''


def svg_quality_gate() -> str:
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="720">
<rect width="100%" height="100%" fill="#F8FAFC"/>
<text x="70" y="60" font-size="34" fill="#0F172A" font-weight="bold">Quality Gate Map</text>
<text x="70" y="92" font-size="18" fill="#334155">test → contract → load → canary → rollback → promote</text>
<g font-family="Arial" font-size="18" fill="#0F172A">
<rect x="70" y="150" width="180" height="100" rx="14" fill="#DBEAFE" stroke="#60A5FA"/><text x="110" y="205" font-weight="bold">Unit Test</text>
<rect x="280" y="150" width="180" height="100" rx="14" fill="#E0F2FE" stroke="#38BDF8"/><text x="313" y="205" font-weight="bold">Contract</text>
<rect x="490" y="150" width="180" height="100" rx="14" fill="#DCFCE7" stroke="#22C55E"/><text x="532" y="205" font-weight="bold">Integration</text>
<rect x="700" y="150" width="180" height="100" rx="14" fill="#FEF3C7" stroke="#F59E0B"/><text x="748" y="205" font-weight="bold">Load</text>
<rect x="910" y="150" width="180" height="100" rx="14" fill="#FCE7F3" stroke="#F472B6"/><text x="950" y="205" font-weight="bold">Canary</text>
<rect x="1120" y="150" width="180" height="100" rx="14" fill="#FFE4E6" stroke="#FB7185"/><text x="1153" y="205" font-weight="bold">Promote</text>
</g>
<g stroke="#94A3B8" stroke-width="4" fill="none" marker-end="url(#arr)">
<path d="M250 200 L280 200"/><path d="M460 200 L490 200"/><path d="M670 200 L700 200"/><path d="M880 200 L910 200"/><path d="M1090 200 L1120 200"/>
</g>
<defs><marker id="arr" markerWidth="12" markerHeight="12" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#94A3B8"/></marker></defs>
<rect x="90" y="330" width="1220" height="250" rx="18" fill="#FFFFFF" stroke="#CBD5E1"/>
<text x="120" y="382" font-size="22" fill="#0F172A">Gate rules for go-live</text>
<text x="120" y="425" font-size="18" fill="#334155">No rollback reasons, no DLQ growth, no consumer lag, no Java compile failure.</text>
<text x="120" y="465" font-size="18" fill="#334155">All failures must map to a visible artifact and an action owner.</text>
<text x="120" y="505" font-size="18" fill="#334155">This snapshot is used on release slides and final acceptance reports.</text>
</svg>'''


def svg_release_pipeline() -> str:
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="720">
<rect width="100%" height="100%" fill="#F8FAFC"/>
<text x="70" y="60" font-size="34" fill="#0F172A" font-weight="bold">Release Pipeline Snapshot</text>
<text x="70" y="92" font-size="18" fill="#334155">preflight → build → test → canary → rollout → incident fallback</text>
<g font-family="Arial" font-size="18" fill="#0F172A" font-weight="bold">
<rect x="70" y="150" width="180" height="100" rx="14" fill="#DBEAFE" stroke="#60A5FA"/><text x="112" y="205">Preflight</text>
<rect x="280" y="150" width="180" height="100" rx="14" fill="#E0F2FE" stroke="#38BDF8"/><text x="333" y="205">Build</text>
<rect x="490" y="150" width="180" height="100" rx="14" fill="#DCFCE7" stroke="#22C55E"/><text x="542" y="205">Test</text>
<rect x="700" y="150" width="180" height="100" rx="14" fill="#FEF3C7" stroke="#F59E0B"/><text x="746" y="205">Canary</text>
<rect x="910" y="150" width="180" height="100" rx="14" fill="#FCE7F3" stroke="#F472B6"/><text x="956" y="205">Rollout</text>
<rect x="1120" y="150" width="180" height="100" rx="14" fill="#FFE4E6" stroke="#FB7185"/><text x="1135" y="205">Fallback</text>
</g>
<g stroke="#94A3B8" stroke-width="4" fill="none" marker-end="url(#arr)">
<path d="M250 200 L280 200"/><path d="M460 200 L490 200"/><path d="M670 200 L700 200"/><path d="M880 200 L910 200"/><path d="M1090 200 L1120 200"/>
</g>
<defs><marker id="arr" markerWidth="12" markerHeight="12" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#94A3B8"/></marker></defs>
<rect x="90" y="330" width="1220" height="250" rx="18" fill="#FFFFFF" stroke="#CBD5E1"/>
<text x="120" y="382" font-size="22" fill="#0F172A">Evidence chain</text>
<text x="120" y="425" font-size="18" fill="#334155">Load test report → canary decision → incident ticket → rollback or promote.</text>
<text x="120" y="465" font-size="18" fill="#334155">Use in PPT for launch day, release operations and governance slides.</text>
<text x="120" y="505" font-size="18" fill="#334155">Designed for public sharing and enterprise release runbooks.</text>
</svg>'''


def svg_dev_ops() -> str:
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="720">
<rect width="100%" height="100%" fill="#F8FBFF"/>
<text x="70" y="60" font-size="34" fill="#0F172A" font-weight="bold">Development Loop Snapshot</text>
<text x="70" y="92" font-size="18" fill="#334155">analysis → design → implement → test → load test → iterate → release</text>
<circle cx="260" cy="320" r="90" fill="#DBEAFE" stroke="#60A5FA" stroke-width="4"/>
<circle cx="480" cy="320" r="90" fill="#DCFCE7" stroke="#22C55E" stroke-width="4"/>
<circle cx="700" cy="320" r="90" fill="#FEF3C7" stroke="#F59E0B" stroke-width="4"/>
<circle cx="920" cy="320" r="90" fill="#FCE7F3" stroke="#F472B6" stroke-width="4"/>
<circle cx="1140" cy="320" r="90" fill="#E9D5FF" stroke="#A855F7" stroke-width="4"/>
<text x="220" y="325" font-size="24" fill="#0F172A" font-weight="bold">Analysis</text>
<text x="455" y="325" font-size="24" fill="#0F172A" font-weight="bold">Design</text>
<text x="660" y="325" font-size="24" fill="#0F172A" font-weight="bold">Implement</text>
<text x="890" y="325" font-size="24" fill="#0F172A" font-weight="bold">Test</text>
<text x="1105" y="325" font-size="24" fill="#0F172A" font-weight="bold">Release</text>
<line x1="350" y1="320" x2="390" y2="320" stroke="#94A3B8" stroke-width="4" marker-end="url(#arr)"/>
<line x1="570" y1="320" x2="610" y2="320" stroke="#94A3B8" stroke-width="4" marker-end="url(#arr)"/>
<line x1="790" y1="320" x2="830" y2="320" stroke="#94A3B8" stroke-width="4" marker-end="url(#arr)"/>
<line x1="1010" y1="320" x2="1050" y2="320" stroke="#94A3B8" stroke-width="4" marker-end="url(#arr)"/>
<defs><marker id="arr" markerWidth="12" markerHeight="12" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#94A3B8"/></marker></defs>
<text x="90" y="580" font-size="18" fill="#475569">This image is suitable for teaching the enterprise delivery rhythm in dual education.</text>
</svg>'''


def svg_dual_six_steps() -> str:
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="720">
<rect width="100%" height="100%" fill="#F8FBFF"/>
<text x="70" y="60" font-size="34" fill="#0F172A" font-weight="bold">German Dual Education 6-Step Method</text>
<text x="70" y="92" font-size="18" fill="#334155">1. 情境导入 2.任务澄清 3.方案设计 4.实施执行 5.结果验收 6.反思迁移</text>
<circle cx="700" cy="360" r="235" fill="#FFFFFF" stroke="#BFDBFE" stroke-width="4"/>
<g font-family="Microsoft YaHei" font-size="18" font-weight="bold" fill="#0F172A">
  <circle cx="700" cy="150" r="72" fill="#DBEAFE" stroke="#60A5FA" stroke-width="3"/><text x="648" y="157">1.导入</text>
  <circle cx="885" cy="255" r="72" fill="#DCFCE7" stroke="#22C55E" stroke-width="3"/><text x="833" y="262">2.澄清</text>
  <circle cx="885" cy="465" r="72" fill="#FEF3C7" stroke="#F59E0B" stroke-width="3"/><text x="833" y="472">3.设计</text>
  <circle cx="700" cy="570" r="72" fill="#E9D5FF" stroke="#A855F7" stroke-width="3"/><text x="648" y="577">4.实施</text>
  <circle cx="515" cy="465" r="72" fill="#FCE7F3" stroke="#F472B6" stroke-width="3"/><text x="463" y="472">5.验收</text>
  <circle cx="515" cy="255" r="72" fill="#FFE4E6" stroke="#FB7185" stroke-width="3"/><text x="463" y="262">6.反思</text>
</g>
<text x="585" y="355" font-size="28" fill="#1E3A8A" font-weight="bold">课堂 × 企业</text>
<text x="602" y="388" font-size="20" fill="#334155">任务闭环</text>
<text x="70" y="660" font-size="18" fill="#475569">每次授课都按6步法推进：讲概念 -> 布任务 -> 看代码 -> 做实验 -> 出证据 -> 做复盘。</text>
</svg>'''


def svg_dual_session_plan() -> str:
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="720">
<rect width="100%" height="100%" fill="#F8FAFC"/>
<text x="70" y="58" font-size="34" fill="#0F172A" font-weight="bold">Dual Education Session Plan (12 Lessons)</text>
<text x="70" y="90" font-size="18" fill="#334155">每次授课执行6步法：导入-澄清-设计-实施-验收-反思</text>
<rect x="70" y="130" width="1260" height="510" rx="14" fill="#FFFFFF" stroke="#CBD5E1"/>
<g font-family="Microsoft YaHei" fill="#0F172A">
<text x="95" y="170" font-size="18" font-weight="bold">课次</text>
<text x="170" y="170" font-size="18" font-weight="bold">阶段</text>
<text x="360" y="170" font-size="18" font-weight="bold">企业任务</text>
<text x="760" y="170" font-size="18" font-weight="bold">代码/文档证据</text>
<text x="1120" y="170" font-size="18" font-weight="bold">验收产物</text>

<text x="95" y="210" font-size="16">L1</text><text x="170" y="210" font-size="16">导入与分析</text><text x="360" y="210" font-size="16">拆用户故事与边界</text><text x="760" y="210" font-size="16">docs/course-delivery.md</text><text x="1120" y="210" font-size="16">需求卡</text>
<text x="95" y="245" font-size="16">L2</text><text x="170" y="245" font-size="16">总体设计</text><text x="360" y="245" font-size="16">画系统架构图</text><text x="760" y="245" font-size="16">docs/system-design.md</text><text x="1120" y="245" font-size="16">设计评审</text>
<text x="95" y="280" font-size="16">L3</text><text x="170" y="280" font-size="16">后端实现1</text><text x="360" y="280" font-size="16">实现网关与runtime契约</text><text x="760" y="280" font-size="16">app.py / Gateway</text><text x="1120" y="280" font-size="16">接口联调</text>
<text x="95" y="315" font-size="16">L4</text><text x="170" y="315" font-size="16">后端实现2</text><text x="360" y="315" font-size="16">实现A2A与技能加载</text><text x="760" y="315" font-size="16">orchestrator.py</text><text x="1120" y="315" font-size="16">功能验收</text>
<text x="95" y="350" font-size="16">L5</text><text x="170" y="350" font-size="16">前端实现1</text><text x="360" y="350" font-size="16">Web表单与结果卡片</text><text x="760" y="350" font-size="16">frontend App.jsx</text><text x="1120" y="350" font-size="16">页面演示</text>
<text x="95" y="385" font-size="16">L6</text><text x="170" y="385" font-size="16">前端实现2</text><text x="360" y="385" font-size="16">MiniApp交互联调</text><text x="760" y="385" font-size="16">miniapp index.js</text><text x="1120" y="385" font-size="16">端到端演示</text>
<text x="95" y="420" font-size="16">L7</text><text x="170" y="420" font-size="16">测试质量1</text><text x="360" y="420" font-size="16">单测与契约测试</text><text x="760" y="420" font-size="16">tests/*</text><text x="1120" y="420" font-size="16">测试报告</text>
<text x="95" y="455" font-size="16">L8</text><text x="170" y="455" font-size="16">测试质量2</text><text x="360" y="455" font-size="16">门禁与故障注入</text><text x="760" y="455" font-size="16">canary_gate.py</text><text x="1120" y="455" font-size="16">门禁结论</text>
<text x="95" y="490" font-size="16">L9</text><text x="170" y="490" font-size="16">压测评估</text><text x="360" y="490" font-size="16">执行压测与容量建模</text><text x="760" y="490" font-size="16">stress/*.json</text><text x="1120" y="490" font-size="16">容量报告</text>
<text x="95" y="525" font-size="16">L10</text><text x="170" y="525" font-size="16">升级迭代</text><text x="360" y="525" font-size="16">Pulsar/Vector升级</text><text x="760" y="525" font-size="16">events/vector_store</text><text x="1120" y="525" font-size="16">迁移报告</text>
<text x="95" y="560" font-size="16">L11</text><text x="170" y="560" font-size="16">上线发布</text><text x="360" y="560" font-size="16">最终验收与runbook</text><text x="760" y="560" font-size="16">go_live_final_check.py</text><text x="1120" y="560" font-size="16">go_live_report</text>
<text x="95" y="595" font-size="16">L12</text><text x="170" y="595" font-size="16">复盘答辩</text><text x="360" y="595" font-size="16">公开分享与路线图</text><text x="760" y="595" font-size="16">PPT + Docs</text><text x="1120" y="595" font-size="16">答辩纪要</text>
</g>
</svg>'''


def svg_dual_six_step_template() -> str:
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="720">
<rect width="100%" height="100%" fill="#F8FBFF"/>
<text x="70" y="58" font-size="34" fill="#0F172A" font-weight="bold">6-Step Teaching Page Template</text>
<text x="70" y="90" font-size="18" fill="#334155">每次授课页可按此模板插入：步骤、任务、代码、验证、复盘</text>
<g font-family="Microsoft YaHei" font-size="18" fill="#0F172A">
<rect x="70" y="130" width="400" height="250" rx="14" fill="#DBEAFE" stroke="#60A5FA"/><text x="95" y="168" font-weight="bold">Step 1-2 导入/澄清</text><text x="95" y="205">课堂目标</text><text x="95" y="235">企业任务卡</text>
<rect x="500" y="130" width="400" height="250" rx="14" fill="#DCFCE7" stroke="#22C55E"/><text x="525" y="168" font-weight="bold">Step 3-4 设计/实施</text><text x="525" y="205">代码与函数截图</text><text x="525" y="235">实现过程说明</text>
<rect x="930" y="130" width="400" height="250" rx="14" fill="#FEF3C7" stroke="#F59E0B"/><text x="955" y="168" font-weight="bold">Step 5-6 验收/反思</text><text x="955" y="205">测试与压测证据</text><text x="955" y="235">复盘与改进项</text>

<rect x="70" y="410" width="1260" height="220" rx="14" fill="#FFFFFF" stroke="#CBD5E1"/>
<text x="95" y="450" font-weight="bold">Page checklist</text>
<text x="95" y="485">- 至少1张图（架构/流程/证据）</text>
<text x="95" y="515">- 至少1段代码截图并配注释</text>
<text x="95" y="545">- 明确本节任务与验收口径</text>
<text x="95" y="575">- 收尾给出反思与下一步任务</text>
</g>
</svg>'''


def main() -> None:
    files = {
        "dual_education_timeline.svg": svg_timeline(),
        "enterprise_delivery_cycle.svg": svg_cycle(),
        "quality_gate_flow.svg": svg_quality_gate(),
        "release_pipeline.svg": svg_release_pipeline(),
        "development_loop.svg": svg_dev_ops(),
        "dual_six_step_method.svg": svg_dual_six_steps(),
        "dual_session_plan_12_lessons.svg": svg_dual_session_plan(),
        "dual_six_step_page_template.svg": svg_dual_six_step_template(),
    }
    for name, content in files.items():
        (OUT_DIR / name).write_text(content, encoding="utf-8")
    index = OUT_DIR / "README.md"
    index.write_text(
        "# Dual education visual assets\n\n" + "\n".join(f"- `{name}`" for name in files) + "\n",
        encoding="utf-8",
    )
    for name in files:
        print(f"Generated: {OUT_DIR / name}")
    print(f"Generated: {index}")


if __name__ == "__main__":
    main()

