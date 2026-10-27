# 课程仓库与本仓库的同步机制

## 概述

本项目的教学衍生课程 **enterprise-travel-agent-course**（企业级旅游智能体项目实战）托管在独立仓库：

> https://github.com/tianqiongenze/enterprise-travel-agent-course

课程基于本项目的真实工程资产设计（德国双元制本土化 + 费曼学习法 + 布鲁姆认知分层），包含课程标准、16 周授课计划、教学实施方案、16 份教案与 PPT、学生任务书、实验指导书、考核评价表，以及 md → Word/PDF 双格式学生分发版。

## 同步机制（本仓库更新 → 课程仓库）

课程仓库内置同步脚本：`tools/sync_from_project.py`（课程仓库内）。

**在本仓库每次重要更新后**，在课程仓库本地目录运行：

```bash
cd D:/移动云盘同步盘/enterprise-travel-agent-course
python tools/sync_from_project.py
git add -A && git commit -m "sync: from enterprise-travel-agent@<commit>" && git push
```

脚本会复制以下内容到课程仓库 `09-项目同步资料/`，并记录本仓库来源 commit：

| 同步内容 | 来源路径 |
|---|---|
| 四轮审查与重构方案 | docs/fourth-round-review-and-refactor-plan.md |
| 局域网人工测试指南 | docs/lan-manual-testing-guide.md |
| 评审路线图（评分章节） | docs/expert-review-and-refactoring-roadmap-2026-09.md |
| staging 复测 runbook | docs/staging-retest-runbook.md |
| 第四轮测试报告 | stress/fourth_round_test_report.md |
| staging 复测报告 | stress/staging_retest_report.md |
| GraphQL 契约 | data-contracts/graphql/schema.graphql |
| K8s 部署清单 | platform/deploy/k8s/*.yaml |

同步完成后在课程仓库重跑 `python tools/convert.py` 即可刷新 Word/PDF 学生版。

## 课程仓库目录速览

```
01-课程标准/ 02-授课计划/ 03-教学实施方案/ 04-教案/(16) 05-学生任务书/(6)
06-实验指导书/(5) 07-考核评价/(4) 08-参考资料/ 09-项目同步资料/
ppt/(16) word/(42) pdf/(42) tools/
```
