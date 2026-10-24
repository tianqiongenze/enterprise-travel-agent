# ADR-0006: TripPlan 聚合仓储持久化（SQLAlchemy + 事件外送）

- 状态：Accepted（2026-09-20，Gap2 落地）
- 背景：运行时此前仅有旧版 ORM CRUD（`db/crud.py` 的 `create_plan` /
  `get_plans_by_user`，存 plan_detail_json），DDD 聚合 `TripPlan`
  只存在于内存，重启即丢；领域事件（TripPlanCreated /
  TripPlanOptionsAttached）在聚合内记录后无处可去。
- 决策：
  1. `infrastructure/repositories.py` 新增
     `SqlAlchemyTripPlanRepository`：聚合 → ORM（`db/models.py`
     `trip_plans` 表）双向映射，`save()` 走后台事件循环
     （`_BackgroundLoopRunner`，独立守护线程），`get()/list_by_city()`
     DB 异常时降级内存镜像（不阻塞推荐主链路）。
  2. `application/recommend_service.py` 构造函数追加
     `repository=None, event_bus=None`；`plan_trip()` 在挂接候选后
     `repository.save(plan)` 并把 `plan.events` 逐条发布到
     `travel.plan.domain-events` 主题；持久化/外送失败仅告警，
     不使推荐失败。默认经 `TRAVEL_PERSIST_TRIP_PLANS`（默认开）控制。
  3. ORM 与领域类严格分层：`db/crud.py` 中 ORM 引用统一别名
     `TripPlanORM`（新增集成测试曝光的同名遮蔽 bug 已修复——
     `from .models import TripPlan` 曾覆盖领域类导致
     `create_plan`/`get_plans_by_user` 直接崩溃）。
  4. 事件外送复用 `events/bus.py`（Local/Pulsar，`build_event_bus_from_env`）
     与 `events/consumer.py` 的 JSONL 落盘，本地教学环境零外网可验证。
- 后果：聚合可跨重启恢复（`get()` 重建聚合并保留事件历史，
  `TripPlanCreated` 去重守卫防止重放重复记录）；新增依赖
  `aiosqlite`（测试）与既有 SQLAlchemy；事件尚随聚合 JSON 列存储，
  独立事件表见 `docs/ddd-event-storming.md` §6 演进项。
- 验证：`services/techgroup-enterprise-travel-runtime/tests/
  test_trip_plan_persistence.py` 四条集成测试（保存/加载等价、
  事件 JSONL 证据、重启后再读、内存聚合直通往返）全绿。
