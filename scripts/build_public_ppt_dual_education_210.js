const fs = require('fs');
const path = require('path');
const pptxgen = require('pptxgenjs');

const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, 'deliverables');
const ASSETS = path.join(ROOT, 'assets', 'public_ppt_v2');
const P3 = path.join(ASSETS, 'p3_evidence');
const DUAL = path.join(ASSETS, 'dual_evidence');
const CODE = path.join(ASSETS, 'code_evidence');

const THEME = {
  bg1: 'F8FBFF',
  bg2: 'DDEEFF',
  bg3: 'CFE4FF',
  card: 'FFFFFF',
  title: '0F172A',
  text: '0F172A',
  sub: '1E3A8A',
  footer: '334155',
  accent: 'F59E0B',
};

const IMAGE_BANK = [
  path.join(P3, 'optimization_score_snapshot.svg'),
  path.join(P3, 'deployment_global_active_active_snapshot.svg'),
  path.join(P3, 'loadtest_snapshot.svg'),
  path.join(P3, 'canary_gate_snapshot.svg'),
  path.join(DUAL, 'dual_education_timeline.svg'),
  path.join(DUAL, 'enterprise_delivery_cycle.svg'),
  path.join(DUAL, 'quality_gate_flow.svg'),
  path.join(DUAL, 'release_pipeline.svg'),
  path.join(DUAL, 'development_loop.svg'),
  path.join(DUAL, 'dual_six_step_method.svg'),
  path.join(DUAL, 'dual_session_plan_12_lessons.svg'),
  path.join(DUAL, 'dual_six_step_page_template.svg'),
  path.join(CODE, 'runtime_orchestrator_card.svg'),
  path.join(CODE, 'runtime_api_card.svg'),
  path.join(CODE, 'event_consumer_card.svg'),
  path.join(CODE, 'gateway_policy_guard_card.svg'),
  path.join(CODE, 'gateway_controller_card.svg'),
  path.join(CODE, 'go_ranker_card.svg'),
  path.join(CODE, 'frontend_app_card.svg'),
  path.join(CODE, 'miniapp_index_card.svg'),
];

const CODE_MAP = {
  backend: [
    ['services/techgroup-enterprise-travel-runtime/src/travel_agent/api/app.py', 1, 140],
    ['services/techgroup-enterprise-travel-runtime/src/travel_agent/orchestrator.py', 1, 160],
    ['services/techgroup-enterprise-travel-runtime/src/travel_agent/events/consumer.py', 1, 180],
    ['services/techgroup-enterprise-travel-gateway/src/main/java/edu/enterprise/travel/gateway/service/PolicyGuardService.java', 1, 210],
    ['services/techgroup-enterprise-travel-ranker-go/main.go', 1, 120],
  ],
  frontend: [
    ['apps/techgroup-enterprise-travel-web/src/App.jsx', 1, 220],
    ['apps/techgroup-enterprise-travel-web/src/api.js', 1, 100],
    ['miniapp-wechat/pages/index/index.js', 1, 140],
    ['miniapp-wechat/pages/index/index.wxml', 1, 80],
  ],
  test: [
    ['tests/test_orchestrator.py', 1, 150],
    ['tests/test_event_consumers.py', 1, 140],
    ['tests/test_go_live_final_check.py', 1, 160],
    ['tests/test_canary_gate.py', 1, 140],
  ],
  ops: [
    ['platform/deploy/scripts/go_live_final_check.py', 1, 260],
    ['platform/deploy/scripts/canary_gate.py', 1, 260],
    ['platform/deploy/scripts/p3_5_autosafemode.py', 1, 180],
    ['stress/go_live_final_report.json', 1, 140],
  ],
};

const SIX_STEPS = ['1.导入', '2.澄清', '3.设计', '4.实施', '5.验收', '6.反思'];

const LESSON_PLANS = [
  { title: '第1课 导入与目标', objective: '理解课程目标与企业交付口径', task: '梳理项目价值与学习边界', acceptance: '形成课程目标卡与术语表' },
  { title: '第2课 需求分析', objective: '掌握用户故事与验收标准', task: '拆解需求与优先级', acceptance: '输出需求卡与风险清单' },
  { title: '第3课 总体设计', objective: '理解多语言分层架构', task: '完成架构图与责任划分', acceptance: '架构评审通过' },
  { title: '第4课 后端实现I', objective: '掌握Runtime与编排链路', task: '跑通接口与A2A协同', acceptance: '输出链路时序证据' },
  { title: '第5课 后端实现II', objective: '掌握策略与事件总线', task: '完成Policy/Event接入', acceptance: '输出策略与事件日志' },
  { title: '第6课 前端接入', objective: '掌握Web与小程序联调', task: '完成表单与结果展示', acceptance: '端到端演示可复现' },
  { title: '第7课 测试质量', objective: '掌握测试金字塔与门禁', task: '补齐关键测试用例', acceptance: '测试报告可审计' },
  { title: '第8课 压测评估', objective: '理解p95/p99与容量边界', task: '执行压测与容量建模', acceptance: '形成压测/成本报告' },
  { title: '第9课 升级迭代I', objective: '理解双栈迁移策略', task: '执行canary与对比演练', acceptance: '输出迁移报告与门禁结论' },
  { title: '第10课 升级迭代II', objective: '理解Pulsar与向量库升级', task: '完成事件与向量后端切换', acceptance: '输出升级验证证据' },
  { title: '第11课 上线发布', objective: '掌握go-live最终验收', task: '执行最终检查脚本', acceptance: '生成go_live_final_report.json' },
  { title: '第12课 复盘答辩', objective: '完成公开分享与技术答辩', task: '组织证据链并答辩', acceptance: '形成复盘纪要与改进计划' },
];

function rationaleFor(phaseName, topic) {
  const text = `${phaseName} ${topic}`;
  if (/总体设计|技术分工|架构图|服务治理/.test(text)) {
    return [
      '为何 Nacos + Etcd：Nacos 生态成熟、控制台友好；Etcd 一致性强、云原生兼容好。双栈用于平滑迁移与风险隔离。',
      '为何 Redis + RocksDB：Redis 适合共享热点会话与分布式缓存；RocksDB 适合本地高吞吐落盘与低成本持久化。',
      '为何 Java + Python + Go：Java 稳定治理入口，Python 迭代AI编排，Go 承担高并发热点路径。',
    ];
  }
  if (/升级迭代|迁移策略|canary|autosafemode/.test(text)) {
    return [
      '为何 Kafka 升级 Pulsar：Pulsar 天然多租户、存算分离、跨地域复制更顺滑，适配云原生多活。',
      '为何要做 canary 与自动熔断：先小流量验证，再自动回滚，降低生产事故半径。',
      '为何引入向量库（Qdrant/Milvus）：支持语义检索与长期记忆，提升推荐解释性与召回质量。',
    ];
  }
  if (/上线发布|发布流程|门禁报告|回滚策略/.test(text)) {
    return [
      '为何做异地多活：区域故障可快速切换，提升连续服务能力与SLA稳定性。',
      '为何做全球化部署：就近接入降低延迟，分区治理提升扩展上限与合规能力。',
      '为何必须证据驱动发布：容量与性能声明必须附压测参数、持续时长、回滚演练证据。',
    ];
  }
  if (/压测|容量模型|边界声明/.test(text)) {
    return [
      '容量数字必须区分本地基线与分布式认证，不可直接外推。',
      '高并发提升通常来自架构治理与数据/消息分层，而非单一语言重写。',
      '成本模型需与扩容策略联合评估，避免“性能提升但不可持续”。',
    ];
  }
  return [
    '本页按“结论 -> 证据 -> 动作”讲解，确保课堂与企业任务一致。',
    '每个技术决策都需要说明前因后果、替代方案与风险边界。',
  ];
}

const PHASES = [
  {
    code: 'P1',
    name: '导入与双元制方法',
    sub: '课堂理论 + 企业任务 + 代码证据 + 验证闭环',
    topics: ['课程定位', '双元制6步法', '12次授课节奏', '公开分享标准', '证据链总览'],
    codeKind: null,
  },
  {
    code: 'P2',
    name: '需求分析',
    sub: '业务场景、需求拆解、边界与验收口径',
    topics: ['用户画像', '场景拆解', '需求优先级', '风险清单', '需求验收'],
    codeKind: null,
  },
  {
    code: 'P3',
    name: '总体设计',
    sub: '架构分层、技术选型、数据与治理',
    topics: ['架构图', '技术分工', '服务治理', '数据架构', '设计评审'],
    codeKind: null,
  },
  {
    code: 'P4',
    name: '后端实现',
    sub: '网关、编排、事件、策略、并发组件',
    topics: ['Runtime', 'Orchestrator', 'Event', 'Policy', 'Go Ranker'],
    codeKind: 'backend',
  },
  {
    code: 'P5',
    name: '前端接入',
    sub: 'Web与小程序联调、交互与体验',
    topics: ['Web Form', 'API Client', 'MiniApp', '联调', '体验优化'],
    codeKind: 'frontend',
  },
  {
    code: 'P6',
    name: '测试与质量',
    sub: '单测、契约、门禁、回归',
    topics: ['单元测试', '契约测试', '回归', '门禁', '事故复盘'],
    codeKind: 'test',
  },
  {
    code: 'P7',
    name: '压测与容量评估',
    sub: 'p95/p99、容量模型、成本模型',
    topics: ['压测方法', '报告解读', '容量模型', '成本模型', '边界声明'],
    codeKind: 'ops',
  },
  {
    code: 'P8',
    name: '升级迭代',
    sub: '迁移、灰度、canary、自动熔断',
    topics: ['迁移策略', 'canary', 'autosafemode', '兼容性', '演练复盘'],
    codeKind: 'ops',
  },
  {
    code: 'P9',
    name: '上线发布',
    sub: 'go-live checklist、runbook、最终验收',
    topics: ['发布流程', '最终验收脚本', '门禁报告', '回滚策略', '发布复盘'],
    codeKind: 'ops',
  },
  {
    code: 'P10',
    name: '公开分享收束',
    sub: '路线图、答辩、附录与资源索引',
    topics: ['路线图', '风险边界', '附录证据', 'Q&A', '收官'],
    codeKind: 'frontend',
  },
];

function exists(p) {
  return p && fs.existsSync(p);
}

function firstExisting(paths) {
  for (const p of paths) {
    if (exists(p)) return p;
  }
  return null;
}

function gradient(slide) {
  slide.background = { color: THEME.bg1 };
  slide.addShape('rect', { x: 0, y: 0, w: 13.333, h: 2.2, fill: { color: THEME.bg2, transparency: 20 }, line: { color: THEME.bg2, pt: 0 } });
  slide.addShape('rect', { x: 0, y: 2.2, w: 13.333, h: 2.2, fill: { color: THEME.bg2, transparency: 45 }, line: { color: THEME.bg2, pt: 0 } });
  slide.addShape('rect', { x: 0, y: 4.4, w: 13.333, h: 3.1, fill: { color: THEME.bg3, transparency: 65 }, line: { color: THEME.bg3, pt: 0 } });
}

function chrome(slide, phase, page, total, topic, lessonNo) {
  const lesson = LESSON_PLANS[Math.max(0, Math.min(LESSON_PLANS.length - 1, lessonNo - 1))];
  slide.addText(phase.code, { x: 0.8, y: 0.58, w: 1.8, h: 0.25, fontFace: 'Arial', fontSize: 12, color: THEME.accent, bold: true });
  slide.addText(phase.name, { x: 0.8, y: 0.92, w: 11.8, h: 0.52, fontFace: 'Microsoft YaHei', fontSize: 21, color: THEME.title, bold: true, fit: 'shrink' });
  slide.addText(`${topic} | 德国双元制6步法 | 第${lessonNo}次授课`, { x: 0.8, y: 1.46, w: 11.8, h: 0.28, fontFace: 'Microsoft YaHei', fontSize: 12, color: THEME.sub, fit: 'shrink' });
  slide.addText(lesson.title, { x: 0.8, y: 1.76, w: 6.8, h: 0.22, fontFace: 'Microsoft YaHei', fontSize: 10, color: '334155', fit: 'shrink' });
  slide.addShape('roundRect', { x: 10.25, y: 0.2, w: 2.9, h: 0.32, fill: { color: 'DBEAFE' }, line: { color: 'DBEAFE', pt: 0 } });
  slide.addText(`${page}/210`, { x: 10.35, y: 0.24, w: 2.7, h: 0.2, fontFace: 'Microsoft YaHei', fontSize: 9, color: '1E3A8A', bold: true, align: 'center' });
}

function snippet(rel, start, end, max = 22) {
  const abs = path.join(ROOT, rel);
  if (!exists(abs)) return `// file not found: ${rel}`;
  const rows = fs.readFileSync(abs, 'utf8').split(/\r?\n/);
  const pick = rows.slice(Math.max(0, start - 1), Math.min(rows.length, end)).slice(0, max);
  if (end - start + 1 > max) pick.push('// ...truncated...');
  return pick.join('\n');
}

function addImageRichSlide(pptx, phase, page, total, topic, lessonNo, preferredImage) {
  const slide = pptx.addSlide();
  gradient(slide);
  chrome(slide, phase, page, total, topic, lessonNo);

  slide.addShape('roundRect', { x: 0.75, y: 2.0, w: 8.0, h: 4.75, fill: { color: THEME.card, transparency: 2 }, line: { color: 'BFDBFE', pt: 1 } });
  slide.addShape('roundRect', { x: 8.9, y: 2.0, w: 3.9, h: 4.75, fill: { color: THEME.card, transparency: 2 }, line: { color: 'BFDBFE', pt: 1 } });

  const img = firstExisting([preferredImage, ...IMAGE_BANK]);
  if (img) {
    slide.addImage({ path: img, x: 1.0, y: 2.2, w: 7.6, h: 3.5 });
  }

  const step = SIX_STEPS[(page - 1) % SIX_STEPS.length];
  const lesson = LESSON_PLANS[Math.max(0, Math.min(LESSON_PLANS.length - 1, lessonNo - 1))];
  const rationale = rationaleFor(phase.name, topic);
  slide.addText([
    `当前6步法步骤：${step}`,
    `课堂目标：${lesson.objective}`,
    `企业任务：${lesson.task}`,
    `验收口径：${lesson.acceptance}`,
    ...rationale,
  ].map((t) => ({ text: t, options: { bullet: { indent: 8 } } })), {
    x: 9.1,
    y: 2.3,
    w: 3.45,
    h: 3.95,
    fontFace: 'Microsoft YaHei',
    fontSize: 10,
    color: THEME.text,
    breakLine: true,
    fit: 'shrink',
  });
}

function addCodeRichSlide(pptx, phase, page, total, topic, lessonNo, codeSpec) {
  const slide = pptx.addSlide();
  gradient(slide);
  chrome(slide, phase, page, total, topic, lessonNo);

  const rel = codeSpec[0];
  slide.addShape('roundRect', { x: 0.75, y: 2.0, w: 8.9, h: 4.75, fill: { color: '0B1220' }, line: { color: '1E293B', pt: 1 } });
  slide.addText(rel, { x: 0.95, y: 2.2, w: 8.5, h: 0.24, fontFace: 'Consolas', fontSize: 9, color: '93C5FD', fit: 'shrink' });
  slide.addText(snippet(rel, codeSpec[1], codeSpec[2]), { x: 0.95, y: 2.48, w: 8.5, h: 3.95, fontFace: 'Consolas', fontSize: 8.5, color: 'E2E8F0', fit: 'shrink' });

  slide.addShape('roundRect', { x: 9.8, y: 2.0, w: 3.0, h: 4.75, fill: { color: THEME.card, transparency: 2 }, line: { color: 'BFDBFE', pt: 1 } });
  const codeCardMap = {
    'services/techgroup-enterprise-travel-runtime/src/travel_agent/orchestrator.py': path.join(CODE, 'runtime_orchestrator_card.svg'),
    'services/techgroup-enterprise-travel-runtime/src/travel_agent/api/app.py': path.join(CODE, 'runtime_api_card.svg'),
    'services/techgroup-enterprise-travel-runtime/src/travel_agent/events/consumer.py': path.join(CODE, 'event_consumer_card.svg'),
    'services/techgroup-enterprise-travel-gateway/src/main/java/edu/enterprise/travel/gateway/service/PolicyGuardService.java': path.join(CODE, 'gateway_policy_guard_card.svg'),
    'services/techgroup-enterprise-travel-gateway/src/main/java/edu/enterprise/travel/gateway/api/TravelGatewayController.java': path.join(CODE, 'gateway_controller_card.svg'),
    'services/techgroup-enterprise-travel-ranker-go/main.go': path.join(CODE, 'go_ranker_card.svg'),
    'apps/techgroup-enterprise-travel-web/src/App.jsx': path.join(CODE, 'frontend_app_card.svg'),
    'miniapp-wechat/pages/index/index.js': path.join(CODE, 'miniapp_index_card.svg'),
  };
  const codeImg = firstExisting([codeCardMap[rel], path.join(DUAL, 'dual_six_step_page_template.svg'), ...IMAGE_BANK]);
  if (codeImg) slide.addImage({ path: codeImg, x: 9.95, y: 2.1, w: 2.7, h: 1.4 });

  const step = SIX_STEPS[(page - 1) % SIX_STEPS.length];
  const lesson = LESSON_PLANS[Math.max(0, Math.min(LESSON_PLANS.length - 1, lessonNo - 1))];
  const rationale = rationaleFor(phase.name, topic);
  slide.addText([
    `6步法步骤：${step}`,
    `课堂目标：${lesson.objective}`,
    '代码截图已附带注释，便于课堂讲解。',
    `企业任务：${lesson.task}`,
    ...rationale.slice(0, 2),
    '验收：将本函数映射到测试与门禁证据。',
  ].map((t) => ({ text: t, options: { bullet: { indent: 8 } } })), {
    x: 10.02,
    y: 3.7,
    w: 2.5,
    h: 2.6,
    fontFace: 'Microsoft YaHei',
    fontSize: 9.8,
    color: THEME.text,
    breakLine: true,
    fit: 'shrink',
  });
}

function lessonNumber(page) {
  return Math.min(12, Math.max(1, Math.floor((page - 1) / 18) + 1));
}

async function build() {
  const ppt = new pptxgen();
  ppt.layout = 'LAYOUT_WIDE';
  ppt.author = 'Enterprise Travel Agent';
  ppt.company = 'Enterprise Travel Agent';
  ppt.title = 'Enterprise Travel Agent Public Final 210p (Dual Education)';

  let page = 1;
  const total = 210;

  while (page <= 210) {
    const phaseIdx = Math.min(PHASES.length - 1, Math.floor((page - 1) / 20));
    const phase = PHASES[phaseIdx];
    const topic = phase.topics[(page - 1) % phase.topics.length];
    const lessonNo = lessonNumber(page);

    const phaseImageByName = {
      '导入与双元制方法': path.join(DUAL, 'dual_six_step_method.svg'),
      '需求分析': path.join(DUAL, 'enterprise_delivery_cycle.svg'),
      '总体设计': path.join(P3, 'deployment_global_active_active_snapshot.svg'),
      '后端实现': path.join(CODE, 'runtime_orchestrator_card.svg'),
      '前端接入': path.join(CODE, 'frontend_app_card.svg'),
      '测试与质量': path.join(DUAL, 'quality_gate_flow.svg'),
      '压测与容量评估': path.join(P3, 'loadtest_snapshot.svg'),
      '升级迭代': path.join(P3, 'canary_gate_snapshot.svg'),
      '上线发布': path.join(DUAL, 'release_pipeline.svg'),
      '公开分享收束': path.join(P3, 'optimization_score_snapshot.svg'),
    };

    const shouldCode = phase.codeKind && ((page - 1) % 3 === 0);
    if (shouldCode) {
      const bank = CODE_MAP[phase.codeKind] || CODE_MAP.ops;
      addCodeRichSlide(ppt, phase, page, total, topic, lessonNo, bank[(page - 1) % bank.length]);
    } else {
      addImageRichSlide(ppt, phase, page, total, topic, lessonNo, phaseImageByName[phase.name]);
    }
    page += 1;
  }

  fs.mkdirSync(OUT, { recursive: true });
  const fileName = path.join(OUT, 'Enterprise_Travel_Agent_Public_Final_210p_light-gradient.pptx');
  await ppt.writeFile({ fileName });
  console.log(`Generated: ${fileName}`);
}

build().catch((err) => {
  console.error(err);
  process.exit(1);
});

