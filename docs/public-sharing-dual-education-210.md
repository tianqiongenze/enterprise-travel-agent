# German Dual Education Public Deck (210p)

## Goal

Generate a 200+ page public-sharing PPT in a light gradient theme, aligned with German dual education and a real enterprise delivery rhythm.

## Script

- `scripts/build_public_ppt_dual_education_210.js`

## One-shot commands

```powershell
npm run run:dual-education:assets
npm run run:p3:evidence:assets
python platform/deploy/scripts/generate_code_evidence_assets.py
npm run run:dual-education:ppt
```

## Teaching Rhythm (German Dual 6-Step)

- Recommended course cadence: **12 lessons**
- Every lesson follows 6-step method:
  1. 导入
  2. 澄清
  3. 设计
  4. 实施
  5. 验收
  6. 反思
- Deck pages embed lesson number + current 6-step marker for delivery pacing.

## Advanced Tech Decisions to Explain in-class

- `Nacos + Etcd`:
  - Nacos is strong for enterprise management and console-driven governance.
  - Etcd is strong for consistency and cloud-native control-plane style.
  - Both are introduced for dual-stack migration, risk isolation, and rollback safety.

- `Redis + RocksDB`:
  - Redis handles shared hot-session memory and distributed cache.
  - RocksDB handles local persistent high-throughput storage with lower cost.
  - Combination balances latency, persistence, and operational cost.

- `Kafka -> Pulsar`:
  - Pulsar offers native multi-tenancy, storage/compute separation, and geo-replication.
  - Better fit for cross-region event streaming and cloud-native multi-active targets.

- `Multi-region active-active / global deployment`:
  - Lower latency via nearest-region access.
  - Better resilience and SLA during regional failures.
  - Compliance and scaling benefits through partitioned governance.

## Content Structure

1. Dual education introduction
2. Requirement analysis
3. Architecture and design
4. Backend implementation
5. Frontend integration
6. Test and quality gates
7. Load testing and capacity planning
8. Upgrade / migration / canary
9. Release and operations
10. Public sharing appendix

## Evidence assets

- `assets/public_ppt_v2/dual_evidence/dual_education_timeline.svg`
- `assets/public_ppt_v2/dual_evidence/enterprise_delivery_cycle.svg`
- `assets/public_ppt_v2/dual_evidence/quality_gate_flow.svg`
- `assets/public_ppt_v2/dual_evidence/release_pipeline.svg`
- `assets/public_ppt_v2/dual_evidence/development_loop.svg`
- `assets/public_ppt_v2/dual_evidence/dual_six_step_method.svg`
- `assets/public_ppt_v2/dual_evidence/dual_session_plan_12_lessons.svg`
- `assets/public_ppt_v2/dual_evidence/dual_six_step_page_template.svg`

## Code screenshot assets

- `assets/public_ppt_v2/code_evidence/runtime_orchestrator_card.svg`
- `assets/public_ppt_v2/code_evidence/runtime_api_card.svg`
- `assets/public_ppt_v2/code_evidence/event_consumer_card.svg`
- `assets/public_ppt_v2/code_evidence/gateway_policy_guard_card.svg`
- `assets/public_ppt_v2/code_evidence/gateway_controller_card.svg`
- `assets/public_ppt_v2/code_evidence/go_ranker_card.svg`
- `assets/public_ppt_v2/code_evidence/frontend_app_card.svg`
- `assets/public_ppt_v2/code_evidence/miniapp_index_card.svg`

## Output

- `deliverables/Enterprise_Travel_Agent_Public_Final_210p_light-gradient.pptx`

## Verification

- 210 slides
- light gradient style
- code, docs, tests, load test, deployment, and release evidence linked

