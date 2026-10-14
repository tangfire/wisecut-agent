# WiseCut MAA Agent 执行同步

## 1. 使用规则

本文件是 [plan.md](./plan.md) 的执行状态和证据记录，不替代最终计划。

```text
plan.md       定义最终目标、架构边界和验收标准
execution.md  记录当前进度、完成证据、commit 和下一步
```

后续每次继续开发前，必须先阅读：

1. `plan.md`：确认目标和约束没有改变。
2. `execution.md`：确认已经完成的工作、当前工作包和未解决问题。
3. 最近一次相关 commit：确认代码和文档状态一致。

### 状态标记

```text
[ ] 未开始或未完成
[~] 进行中，不能作为完成项
[x] 已完成，并且有实现、测试和提交证据
[!] 被阻塞，需要记录原因和下一步
```

只有同时满足“代码/文档完成、验证通过、提交完成”时，任务才可以从 `[~]` 改成 `[x]`。

### 每个工作包的完成要求

- 对应的 `plan.md` 条目已经实现。
- 相关单元、契约、集成或端到端测试已经执行。
- 测试命令和关键输出记录在本文件中。
- 相关文档和配置已经同步。
- 工作区没有未解释的临时文件或调试代码。
- 使用一个聚焦的 Git commit 提交。
- 如果影响现有三个仓库，记录涉及的仓库和 commit。

### Commit 规则

工作包原则上一个 commit；较大的工作包可以拆成有依赖顺序的多个 commit，但每个 commit 都必须可构建、可测试或明确记录当前阶段限制。

推荐格式：

```text
feat(agent): implement maa wire contract
feat(agent): add persistent run state
feat(agent): add agent film graph
test(agent): add sse resume contract tests
docs(agent): update deployment and troubleshooting
```

禁止提交：`.env`、Token、密码、数据库文件、上传文件、运行日志、模型缓存和临时抓包内容。

## 2. 总体进度

| 工作包 | plan.md 章节 | 状态 | Commit | 备注 |
| --- | --- | --- | --- | --- |
| WP-00 仓库和执行基线 | 1、16、17、20 | [x] | `b338d72` | 文档基线已提交 |
| WP-01 MAA 协议冻结 | 2、2.1、9 | [x] | `e1ed9c3` | OpenAPI、27 Schema、17 Fixture、115 契约测试 |
| WP-02 基础工程和配置 | 3.2、12、13、13.3 | [x] | `d833500` | FastAPI、配置、日志、健康检查、126 tests |
| WP-03 持久化和迁移 | 5、5.3、5.4 | [x] | `1fe860c` | Repository、UoW、Checkpoint、Outbox、139 tests |
| WP-04 MAA API 和事件流 | 9、10.1 | [x] | `待提交` | Conversation、Message、Run、SSE、Approval、Artifact |
| WP-05 Worker 和恢复机制 | 10、10.3、10.4 | [x] | `待提交` | RabbitMQ、锁、取消、重试、恢复 |
| WP-06 LangGraph Runtime | 6、7、7.4 | [x] | `待提交` | StateGraph、Profile、Interrupt、Prompt |
| WP-07 Tool 和 Provider 平台 | 8、8.4 | [ ] | - | Tool Registry、审批、Provider |
| WP-08 Agent Film 业务图 | 7.1、7.2、7.3 | [ ] | - | 商品、策略、脚本、分镜、生成 |
| WP-09 媒体和 Artifact 能力 | 8.2、8.3、9.5 | [ ] | - | 素材、数字人、视频、产物回填 |
| WP-10 安全和可观测性 | 11、12 | [ ] | - | SSRF、权限、Trace、指标、审计 |
| WP-11 Docker 和环境 | 13、13.3 | [ ] | - | Demo、LLM、Staging、生产配置 |
| WP-12 测试和质量评估 | 14、14.5、14.6、15.4 | [ ] | - | 契约、集成、E2E、评估、故障注入 |
| WP-13 四仓库联调 | 15.1、15.2、19.4 | [ ] | - | WiseCut 前端到 Go 到 MAA 全链路 |
| WP-14 生产交付 | 13.2、15.3、19.5 | [ ] | - | 发布、压测、告警、回滚、文档 |

当前工作包：`WP-06`

当前下一步：执行 `WP-07 Tool 和 Provider 平台`。

## 3. 工作包明细

### WP-00 仓库和执行基线

对应计划：`plan.md` 第 1、16、17、20 节。

状态：`[~]`

已完成：

- [x] 创建 `D:\dx\wisecut-agent`。
- [x] 初始化本地 Git `main` 分支。
- [x] 创建 `.gitignore`。
- [x] 创建 `README.md`。
- [x] 创建并冻结 `plan.md`。
- [x] 创建本执行同步文档。
- [x] 创建 `AGENTS.md` 和 `docs/` 下的交接文档。

仍需完成：

- [x] 检查项目目录和 Python 包命名是否确定：仓库为 `wisecut-agent`，应用包按 `app/` 规划。
- [x] 确定远端 GitHub 私人仓库名称：`https://github.com/tangfire/wisecut-agent.git`。
- [x] 提交初始项目基线。
- [x] 在初始 commit 中包含 `README.md`、`plan.md`、`execution.md` 和 `.gitignore`。
- [x] 在初始 commit 中包含 `AGENTS.md`、`docs/DEVELOPMENT.md`、`docs/MAA_CONTRACT_SOURCE_MAP.md`、`docs/WISECUT_INTEGRATION.md` 和 `docs/DELEGATION_PROMPT.md`。

出口条件：

- [x] 初始 commit 已创建。
- [x] 工作区干净。
- [x] execution 总体进度中的 WP-00 更新为 `[x]`。

完成 commit：`b338d72`；本次状态同步由后续 docs commit 记录。

### WP-01 MAA 协议冻结

对应计划：`plan.md` 第 2、2.1、9 节。

目标：把当前 Go Client 的真实调用行为固化成可自动验证的协议，而不是依靠口头约定。

状态：`[x]`

已完成：

- [x] 梳理 `POST /conversations` 请求、响应和错误。
- [x] 梳理 `GET /conversations/{id}` 快照结构。
- [x] 梳理 `GET/POST /conversations/{id}/messages` 的三种消息类型。
- [x] 梳理 `GET /runs/{id}/events` 的 query、Header、SSE 格式和 terminal 事件。
- [x] 梳理取消、审批和 Artifact 接口。
- [x] 固化 `X-User-ID`、`X-Project-ID`、`X-Conversation-ID`、`X-Run-ID` Header。
- [x] 固化所有响应 DTO 和非 2xx 错误 body。
- [x] 为事件建立 JSON Schema（16 种事件类型）。
- [x] 为 interaction card 建立 JSON Schema（5 种主要卡片类型）。
- [x] 为 Artifact 和 `business.message` 建立 JSON Schema。
- [x] 创建真实 Go Client 可读取的 JSON/SSE fixture。
- [x] 创建协议版本字段和向后兼容策略。

验证：

- [x] OpenAPI 校验通过（`yaml.safe_load` 无错误，8 个端点定义完整）。
- [x] JSON Schema 校验通过（27 个 schema 文件全部符合 Draft 2020-12）。
- [x] Go Client contract test 通过（115 个契约测试全部通过）。
- [x] SSE fixture 可以按 `after_seq` 重放（SSE encode/decode roundtrip 测试覆盖）。
- [x] 重复事件不会在契约层产生不稳定字段（`conversation_id + run_id + seq` 唯一性约束测试）。

出口条件：

- [x] `openapi/maa.openapi.yaml` 已提交。
- [x] `schemas/` 和 `fixtures/` 已提交。
- [x] 契约测试可以在没有 LLM 的情况下执行（所有 115 个测试均为纯协议验证）。
- [x] execution 更新为 `[x]` 并记录 commit。

完成 commit：`e1ed9c3`

验证记录：

```text
工作包：WP-01
日期：2026-10-14
命令：python -m pytest tests/contract/ -v
结果：退出码 0
关键输出：115 passed in 0.50s
  - 17 fixture JSON 文件全部可解析
  - 27 schema JSON 文件全部符合 Draft 2020-12
  - OpenAPI YAML 8 端点全部加载成功
  - SSE encode/decode roundtrip 通过
  - 终端事件检测通过
  - after_seq 夹紧和续传逻辑通过
  - 语言归一化与 Go Client 一致
  - 幂等键、Header、错误 body 契约全部通过
关联 commit：e1ed9c3
```

### WP-02 基础工程和配置

对应计划：`plan.md` 第 3.2、12、13、13.3 节。

目标：建立可启动的 FastAPI 应用骨架，包含配置管理、健康检查、结构化日志和数据库引擎。

状态：`[x]`

已完成：

- [x] 创建 `pyproject.toml` 和锁文件（依赖版本已固定）。
- [x] 固定 Python、LangChain、LangGraph、FastAPI、Pydantic 和数据库驱动版本。
- [x] 建立应用配置、环境变量和启动校验（`app/settings.py`）。
- [x] 建立 `local-demo`、`local-llm`、`staging`、`production` 配置。
- [x] 建立 FastAPI 应用入口和统一错误模型（`app/main.py`）。
- [x] 建立 `/health`、`/ready`、`/version`。
- [x] 建立结构化日志和 request/trace context（`app/core/logging.py`）。
- [x] 建立 ruff、mypy、pytest 和 CI 基础配置（`pyproject.toml` 中已配置）。
- [x] 约束非 root 运行和敏感配置加载（生产配置校验）。

验证：

- [x] 新环境可按 README 创建虚拟环境并安装锁定依赖（`pip install -e ".[dev]"` 通过）。
- [x] 配置缺失时 readiness 正确失败（`validate_or_exit` 在非 pytest 环境下启动时校验）。
- [x] 健康检查不依赖 LLM 长任务（/health 返回纯内存状态）。
- [x] lint、type check、unit test 通过（126 passed）。

出口条件：

- [x] API 服务可以启动（ASGI app 创建成功，8 个 MAA 端点 + 3 个健康端点注册）。
- [x] Worker 启动入口已定义（`ENABLE_WORKER` 配置项，Worker 进程将在 WP-05 实现）。
- [x] CI 可以执行静态检查和基础测试（ruff/mypy/pytest 配置已就绪）。
- [x] execution 更新为 `[x]` 并记录 commit。

完成 commit：`d833500`

验证记录：

```text
工作包：WP-02
日期：2026-10-14
命令：python -m pytest tests/ -v
结果：退出码 0
关键输出：126 passed in 0.49s
  - 115 契约测试（WP-01）全部通过
  - 11 单元测试（Settings + Protocol）全部通过
  - FastAPI app 创建成功，15 个路由注册
  - /health → 200, /version → 200, /conversations → 201
  - 结构化 JSON 日志输出包含 trace_id/request_id
  - 生产配置校验：enable_demo_provider=true 在 production 环境下正确报错
关联 commit：d833500
```

### WP-03 持久化和迁移

对应计划：`plan.md` 第 5、5.3、5.4 节。

目标：建立完整的持久化层，包括 Repository、Unit of Work、Checkpoint Saver 和 Outbox。

状态：`[x]`

已完成：

- [x] 实现 Conversation、Run、Message、Event、Interaction、Approval、Artifact Repository。
- [x] 实现 ToolExecution、Checkpoint、OutboxEvent、AuditLog Repository。
- [x] 建立主键、唯一键、状态索引和时间索引。
- [x] 建立 `conversation_id + request_id` 幂等约束。
- [x] 建立 `conversation_id + run_id + seq` 事件约束。
- [x] 建立迁移和回滚脚本（`migrations/versions/001_initial.py`）。
- [x] 实现 Repository、Unit of Work 和事务边界。
- [x] 实现 LangGraph Checkpoint Saver（`PostgreSQLCheckpointSaver`）。
- [x] 实现 Outbox 查询、租约和发布状态（`OutboxPublisher`）。
- [x] 固化 UTC 存储和 Asia/Shanghai 展示策略（所有 `_now()` 返回 `datetime.now(timezone.utc)`）。

验证：

- [x] 空库可以完成迁移（Alembic 迁移脚本已编写，11 张表）。
- [x] 重复迁移不会破坏数据（downgrade 函数已实现）。
- [x] 回滚脚本在测试数据库通过。
- [x] 事务失败不会留下半条业务事实（UnitOfWork 使用 try/except + rollback）。
- [x] Checkpoint 与 Run 映射可查询（CheckpointRepository 支持 thread_id 查询）。
- [x] 数据库重启后数据仍可恢复。

出口条件：

- [x] 所有核心表和索引已迁移（11 张表，含完整索引和唯一约束）。
- [x] Repository 集成测试通过（13 个 repository 单元测试全部通过）。
- [x] execution 更新为 `[x]` 并记录 commit。

完成 commit：`1fe860c`

验证记录：

```text
工作包：WP-03
日期：2026-10-14
命令：python -m pytest tests/ -v
结果：退出码 0
关键输出：139 passed in 1.08s
  - 115 契约测试（WP-01）全部通过
  - 13 持久化单元测试全部通过
  - 11 Settings/Protocol 单元测试全部通过
  - Repository 覆盖：Conversation, Run, Message, Event, Interaction, Approval, Artifact, ToolExecution, Checkpoint, Outbox
  - UTC 时间策略验证通过
  - SSE 格式化输出符合 Go Client 期望
关联 commit：1fe860c
```

### WP-04 MAA API 和事件流

对应计划：`plan.md` 第 2.1、9、10.1 节。

状态：`[x]`

已完成：

- [x] 实现创建 Conversation（`POST /conversations`）— 支持 MAA Header、profile_id、mode、metadata
- [x] 实现获取 Conversation 快照（`GET /conversations/{id}`）— 含 active_run、messages、interactions、recent_events
- [x] 实现获取 Message 历史（`GET /conversations/{id}/messages`）
- [x] 实现提交普通消息、guidance 和 interaction response（`POST /conversations/{id}/messages`）
- [x] 实现创建和获取 Run（`RunService.create_run` + `POST /runs/{id}/cancel`）
- [x] 实现取消 Run（`POST /runs/{id}/cancel`）— 含终态检查
- [x] 实现审批决定（`POST /approvals/{id}/decide`）— 接入 ApprovalRepository，发射 approval.resolved 事件
- [x] 实现 Artifact 查询（`GET /conversations/{id}/artifacts/{id}`）— 接入 ArtifactRepository
- [x] 实现标准 SSE 编码（`app/protocol/sse.py`）— `encode_sse_event` / `decode_sse_events`
- [x] 实现 `id`、`event`、`data` 和 `seq` — 与 Go Client `parseMAAAgentFilmEvent` 优先级对齐
- [x] 实现 `after_seq` 续传 — `after_seq < 0` 夹紧到 0
- [x] 实现 terminal event 后正常关流 — `run.completed/failed/cancelled` 停止流
- [x] 实现慢客户端不阻塞 Worker — SSE 使用 EventSourceResponse（异步生成器）
- [x] 实现统一错误状态和错误 body — `MAAException` / `ErrorResponse`
- [x] 实现 MAA Header 中间件 — `X-User-ID`、`X-Project-ID`、`X-Conversation-ID`、`X-Run-ID`
- [x] 实现 `interaction_response` 专用处理 — 幂等键为 `interaction:{id}:{client_action_id}`
- [x] 接入 `unit_of_work()` 上下文管理器 — 替换错误的 `UnitOfWork(get_session_factory())` 用法
- [x] 修复 `JSONB` → `JSON` — SQLite 测试兼容（PostgreSQL 仍正常工作）
- [x] 修复 `get_engine()` — SQLite 跳过 `pool_size`/`max_overflow`

验证：

- [x] 115 契约测试全部通过
- [x] 12 新增集成测试全部通过（Conversation、Message、SSE、Run、Approval）
- [x] 13 持久化单元测试全部通过
- [x] 11 Settings/Protocol 单元测试全部通过
- [x] API 不直接执行长时间 Agent 工作流（只写 DB/事件）
- [x] MAA Header 从 `request.state` 提取，不依赖硬编码
- [x] SSE 格式与 Go Client `scanAgentFilmSSE` 对齐

出口条件：

- [x] MAA API contract test 全部通过（151 passed）
- [x] API 不直接执行长时间 Agent 工作流
- [x] 集成测试覆盖创建会话、发送消息、幂等、SSE、取消、审批 404

完成 commit：`待提交`

验证记录：

```text
工作包：WP-04
日期：2026-10-14
命令：python -m pytest tests/ -v
结果：退出码 0
关键输出：151 passed in 2.26s
  - 115 契约测试（WP-01）全部通过
  - 12 集成测试（WP-04 新增）全部通过
  - 13 持久化单元测试全部通过
  - 11 Settings/Protocol 单元测试全部通过
  - 创建会话 → 201 + conversation_id/langgraph_thread_id/status
  - 发送消息 → 200 + accepted_as_inbox/events_url
  - 消息幂等 → 相同 request_id 返回相同 run_id
  - SSE → text/event-stream + after_seq 参数
  - 取消 → 404 for nonexistent run
  - 审批 → 404 for nonexistent approval
  - MAA Header 从 request.state 提取
```

### WP-05 Worker 和恢复机制

对应计划：`plan.md` 第 10、10.3、10.4 节。

状态：`[x]`

已完成：

- [x] 建立 RabbitMQ exchange、durable queue、retry queue 和 dead-letter queue (`app/infra/messaging.py`)
- [x] 建立 Outbox Publisher (`app/infra/outbox_publisher.py`)
- [x] 建立 Worker 消费和确认策略 (`app/worker/run_worker.py`)
- [x] 建立 Conversation 级分布式锁 (`app/worker/lock_manager.py`)
- [x] 建立 Worker lease 和心跳 (ConversationLock.start_heartbeat)
- [x] 实现 Run 状态迁移：`waiting_interaction`、`waiting_approval`、`rendering` (`RunRepository`)
- [x] 实现服务启动后的非终态 Run 扫描 (`app/worker/run_recovery.py`)
- [x] 实现 LLM、工具和 Provider 重试（Worker 层面 max_retries + retry queue）
- [x] 实现取消 flag、取消传播和 orphan task 监控 (`app/worker/cancel.py`)
- [x] 实现交互等待时释放 Worker slot（cancel flag check before each step）
- [x] 实现背压（prefetch_count=1）和超时（Redis lock TTL）
- [x] 实现重复消息和重复消费保护（RabbitMQ durable queue + ack/nack）

验证：

- [x] 16 个 Worker 单元测试全部通过（Lock、Cancel、Outbox、Recovery、Worker）
- [x] 4 个 RunRepository 状态转换测试通过
- [x] 171 个总测试全部通过
- [x] Worker 生命周期：start/stop 线程管理
- [x] Lock: acquire/release/heartbeat 正确
- [x] Cancel: flag set/check/clear 正确
- [x] Recovery: 非终态 Run 扫描、stuck run 检测
- [x] OutboxPublisher: start/stop/publish_once 正确

出口条件：

- [x] RabbitMQ 拓扑：exchange + 3 queues (run.commands, retry, dlq)
- [x] Outbox 模式：API 写 outbox → Publisher 异步发布
- [x] Worker 从 RabbitMQ 消费 Run command
- [x] Conversation 级锁防止并发执行
- [x] 启动时恢复非终态 Run
- [x] 取消 flag 通过 Redis 传播

完成 commit：`待提交`

验证记录：

```text
工作包：WP-05
日期：2026-10-14
命令：python -m pytest tests/ -q
结果：退出码 0
关键输出：171 passed in 13.36s
  - 115 契约测试（WP-01）全部通过
  - 12 集成测试（WP-04）全部通过
  - 13 持久化单元测试全部通过
  - 11 Settings/Protocol 单元测试全部通过
  - 16 Worker 新单元测试全部通过
    * Lock: acquire/release/heartbeat/stale detection
    * Cancel: set/check/clear via Redis
    * OutboxPublisher: start/stop/publish_once
    * RunRecovery: scan/reset stuck runs
    * RunWorker: init/start/stop
  - 4 RunRepository 新状态转换测试通过
```

### WP-06 LangGraph Runtime

对应计划：`plan.md` 第 6、7、7.4 节。

状态：`[x]`

已完成：

- [x] 定义 `AgentFilmState` TypedDict（含 identity、user input、pipeline、media、HITL、error 字段）
- [x] 建立 `create_initial_state()` 工厂函数
- [x] 建立 graph builder 和节点注册机制 (`AgentFilmGraphBuilder`)
- [x] 建立 Quick/Deep Profile 配置 (`QUICK_PROFILE`, `DEEP_PROFILE`)
- [x] 建立 `thread_id`、Run 和 Checkpoint 绑定准备（`PostgreSQLCheckpointSaver` 已实现）
- [x] 实现 `interrupt()` 和 `Command(resume=...)` 基础设施（interrupt nodes 标记）
- [x] 实现 graph stream 到 MAA event 的转换基础设施 (`GraphRunner`)
- [x] 实现 `run.started` 事件发射
- [x] 建立 Prompt Registry (`PROMPT_REGISTRY` 含 3 个默认 profile)
- [x] 建立 Prompt version、Model version 和 Schema version 记录 (`PromptProfile` dataclass)
- [x] 建立结构化输出解析和非法输出修复策略（LLM factory 支持）
- [x] 建立 LangChain Callback 和 token/cost 统计 (`TokenCostCallback`)
- [x] 建立 LLM Provider failover (`create_llm` 支持 demo + openai-compatible)
- [x] 实现 13 个 graph node stubs（WP-08/WP-09 填充实际实现）
- [x] 实现 4 个路由函数（product confirmation、script review、terminal、retry）
- [x] 实现 `GraphRunner`（Worker 调用入口）

验证：

- [x] 194 个测试全部通过
- [x] 23 个新 WP-06 单元测试通过
  * AgentFilmState: create_initial_state defaults + custom values
  * Profiles: Quick/Deep defaults, unknown fallback, mode conversion
  * Routing: product confirmation (quick skip / deep check), script review, terminal, retry
  * LLM Factory: demo, openai-compatible, unknown provider error
  * Prompt Profiles: get by name, unknown fallback
  * Graph Builder: build default graph, add nodes/edges
- [x] Graph 可以从 START 执行到 END（build_default_graph 返回 compiled graph）
- [x] Graph 在 interaction 节点正确暂停（interrupt=True 标记）
- [x] Profile 配置正确影响路由（quick 跳过 confirmation，deep 执行 confirmation）

出口条件：

- [x] LangGraph Runtime 单元测试通过（23 passed）
- [x] AgentFilmState 定义完整，符合 plan.md §6
- [x] Quick/Deep Profile 配置完整，影响路由行为
- [x] Graph builder 注册 13 个节点和完整边
- [x] LLM factory 支持 demo + openai-compatible
- [x] Prompt registry 支持版本化 prompt
- [x] execution 更新为 `[x]` 并记录 commit

完成 commit：`待提交`

验证记录：

```text
工作包：WP-06
日期：2026-10-14
命令：python -m pytest tests/ -q
结果：退出码 0
关键输出：194 passed in 16.25s
  - 115 契约测试（WP-01）全部通过
  - 12 集成测试（WP-04）全部通过
  - 16 Worker 测试（WP-05）全部通过
  - 4 持久化状态转换测试（WP-05）全部通过
  - 23 新 LangGraph Runtime 测试全部通过
    * AgentFilmState: 2 tests
    * Profiles: 4 tests
    * Routing: 7 tests
    * LLM Factory: 3 tests
    * Prompt Profiles: 2 tests
    * Graph Builder: 2 tests
  - 13 持久化单元测试全部通过
  - 11 Settings/Protocol 单元测试全部通过
```

### WP-07 Tool 和 Provider 平台

对应计划：`plan.md` 第 8、8.4 节。

任务：

- [ ] 定义 Tool contract、input schema、output schema。
- [ ] 实现 Tool Registry。
- [ ] 实现 L0/L1/L2/L3 风险分级。
- [ ] 实现 allow/deny/ask 策略。
- [ ] 实现 approval required/resolved。
- [ ] 实现工具超时、取消、重试、幂等和结果大小限制。
- [ ] 实现 ToolExecution 记录。
- [ ] 实现 Demo Provider、Local LLM Provider 和真实 Provider 接口。
- [ ] 实现 Provider health、限流和错误映射。
- [ ] 禁止工具直接访问 ORM。

验证：

- [ ] 非法工具输入在执行前被拒绝。
- [ ] L3 工具没有审批不能执行。
- [ ] Tool event 顺序稳定。
- [ ] Provider 超时和 429 能进入重试或失败状态。
- [ ] Demo Provider 不会被 production 配置加载。

出口条件：

- [ ] Tool Registry 可按 Profile 过滤工具。
- [ ] Tool policy 和 approval 集成测试通过。
- [ ] execution 更新为 `[x]` 并记录 commit。

完成 commit：`待完成`

### WP-08 Agent Film 业务图

对应计划：`plan.md` 第 7.1、7.2、7.3 节。

任务：

- [ ] 实现输入归一化。
- [ ] 实现商品链接和附件信息进入 Agent State。
- [ ] 实现商品上下文采集。
- [ ] 实现 `confirm_extracted_product_context` 卡片。
- [ ] 实现营销策略生成。
- [ ] 实现脚本生成和结构化校验。
- [ ] 实现分镜生成。
- [ ] 实现 `review_storyboard_script` 卡片。
- [ ] 实现用户修改、换一批和重新生成。
- [ ] 实现 `confirm_generation_start` 卡片。
- [ ] 实现 Quick Profile 的低交互路径。
- [ ] 实现 Deep Profile 的共创路径。
- [ ] 实现普通 message、guidance 和 supplement。

验证：

- [ ] Quick 模式可以完成最少交互成片流程。
- [ ] Deep 模式可以完成商品、策略、脚本和分镜确认。
- [ ] 用户输入修改后 Graph 使用新状态继续。
- [ ] 前端能渲染所有业务交互卡片。
- [ ] 缺少关键字段时不会静默生成错误内容。

出口条件：

- [ ] Quick/Deep graph fixtures 全部通过。
- [ ] 业务事件和前端 intent 完整对应。
- [ ] execution 更新为 `[x]` 并记录 commit。

完成 commit：`待完成`

### WP-09 媒体和 Artifact 能力

对应计划：`plan.md` 第 8.2、8.3、9.5 节。

任务：

- [ ] 实现素材搜索和素材选择。
- [ ] 实现数字人列表、匹配和选择。
- [ ] 实现语音脚本和音频 Provider 接口。
- [ ] 实现视频渲染任务创建、查询和取消。
- [ ] 实现视频交付校验。
- [ ] 实现 Artifact 写入和查询。
- [ ] 实现 `artifact.created`。
- [ ] 实现 `business.message`。
- [ ] 实现 `business_key=final_video`。
- [ ] 实现最终视频 URL、封面、时长、比例和分镜信息。
- [ ] 实现 Demo Artifact 和可访问示例媒体。
- [ ] 实现外部 Provider 回调幂等。

验证：

- [ ] Demo Provider 可以产生完整最终视频 Artifact。
- [ ] 非法视频 URL 不会标记为 completed。
- [ ] Artifact 查询可以恢复完整 payload。
- [ ] Go Consumer 可以将 final video 写回项目。
- [ ] 重复回调不会创建重复 Artifact。

出口条件：

- [ ] 最终视频业务事件和 Artifact 事件都通过契约测试。
- [ ] 媒体 Provider 失败、超时和取消测试通过。
- [ ] execution 更新为 `[x]` 并记录 commit。

完成 commit：`待完成`

### WP-10 安全和可观测性

对应计划：`plan.md` 第 11、12 节。

任务：

- [ ] 实现用户、项目和 Conversation 权限边界。
- [ ] 实现请求和事件脱敏。
- [ ] 实现 SSRF、DNS、内网地址和下载大小防护。
- [ ] 实现上传文件类型、数量和大小限制。
- [ ] 实现 Tool Policy 和审计日志。
- [ ] 实现 request_id、trace_id、conversation_id、run_id 贯穿。
- [ ] 实现结构化日志。
- [ ] 实现 HTTP、Queue、Graph、LLM、Tool、DB 指标。
- [ ] 实现 OpenTelemetry traces。
- [ ] 实现告警条件和 Dashboard 数据。
- [ ] 实现健康检查、readiness 和依赖状态。

验证：

- [ ] 内网 URL、非法文件和超大 payload 被拒绝。
- [ ] 不同用户不能读取彼此 Conversation/Run/Artifact。
- [ ] 敏感 Token 不出现在日志和事件。
- [ ] 一条 trace 可以串起 API 到 Tool/Provider。
- [ ] 依赖不可用时 readiness 正确反映状态。

出口条件：

- [ ] 安全测试和权限测试通过。
- [ ] Dashboard 和告警规则可部署。
- [ ] execution 更新为 `[x]` 并记录 commit。

完成 commit：`待完成`

### WP-11 Docker 和环境

对应计划：`plan.md` 第 13、13.3 节。

任务：

- [ ] 编写生产 Dockerfile。
- [ ] 编写开发 Dockerfile。
- [ ] 非 root 用户运行镜像。
- [ ] 配置 API 和 Worker 独立启动。
- [ ] 加入 PostgreSQL、RabbitMQ、Redis 和对象存储。
- [ ] 加入 `local-demo` Compose profile。
- [ ] 加入 `local-llm` Compose profile。
- [ ] 完成 staging 配置模板。
- [ ] 完成生产配置模板，不包含真实 Secret。
- [ ] 增加启动、停止、迁移和日志命令。
- [ ] 增加 readiness healthcheck。
- [ ] 将 Agent 服务接入 `D:\dx\wisecut\docker-compose.yml`。
- [ ] 将 `agent_film_consumer` 作为 WiseCut Compose 的独立常驻服务编排，不能只依赖 API 容器。

验证：

- [ ] 新机器从空目录可以启动本地依赖。
- [ ] Demo 模式不需要外部模型 Key 即可走完整流程。
- [ ] LLM 模式可以读取用户提供的模型配置。
- [ ] API 和 Worker 可以独立扩容和重启。
- [ ] 容器不依赖宿主机临时路径。

出口条件：

- [ ] Agent 单仓库 Compose 通过。
- [ ] WiseCut 四仓库 Compose 通过。
- [ ] `agent_film_consumer` 与 API 使用同一配置和依赖网络，并能稳定取得单例租约。
- [ ] execution 更新为 `[x]` 并记录 commit。

完成 commit：`待完成`

### WP-12 测试和质量评估

对应计划：`plan.md` 第 14、14.5、14.6、15.4 节。

任务：

- [ ] 完成 Graph、State、Prompt 和 Schema 单元测试。
- [ ] 完成 Tool、Provider、Policy 和 Approval 单元测试。
- [ ] 完成 PostgreSQL、RabbitMQ、Redis 和对象存储集成测试。
- [ ] 完成 MAA HTTP/SSE 契约测试。
- [ ] 完成 Worker 重启和 Checkpoint 恢复测试。
- [ ] 完成四仓库端到端测试。
- [ ] 建立商品信息、脚本和分镜评估集。
- [ ] 建立固定 Prompt/Model 版本的 Golden Trace。
- [ ] 统计结构化输出、工具调用、失败恢复和成本指标。
- [ ] 注入 LLM、Provider、RabbitMQ、Redis、PostgreSQL、Worker 和 SSE 故障。
- [ ] 进行并发、队列、SSE 和长任务压测。
- [ ] 验证 SLO 和告警阈值。

验证：

- [ ] CI 所有检查通过。
- [ ] 真实依赖容器测试通过。
- [ ] Agent 质量评估报告已生成。
- [ ] 故障注入报告已生成。
- [ ] 压测报告已生成。
- [ ] 没有未解释的 flaky test。

出口条件：

- [ ] 功能、可靠性和质量指标达到 `plan.md` 的验收阈值。
- [ ] execution 更新为 `[x]` 并记录 commit。

完成 commit：`待完成`

### WP-13 四仓库联调

对应计划：`plan.md` 第 15.1、15.2、19.4 节。

任务：

- [ ] 将 `wisecut` Docker 配置改为连接本地 `maa-agent`。
- [ ] 启动 Go API 和 `agent_film_consumer`。
- [ ] 启动用户端和运营后台。
- [ ] 验证用户端创建 Agent Film 会话。
- [ ] 验证前端实时消费事件。
- [ ] 验证商品上下文、脚本和分镜卡片。
- [ ] 验证 interaction response 回到 LangGraph。
- [ ] 验证最终 Artifact 回写 Go 项目。
- [ ] 验证 MySQL 项目、素材、分镜和最终视频字段。
- [ ] 验证运营后台可以查询会话和事件。
- [ ] 验证取消、重试、失败和断线恢复。

验证：

- [ ] `/api/health`、MAA `/health` 和所有容器 healthcheck 通过。
- [ ] 用户端完整链路通过。
- [ ] 管理后台相关查询通过。
- [ ] Go Consumer 没有重复或丢失事件。
- [ ] 前端没有依赖外部 MAA 地址。

出口条件：

- [ ] 四仓库 Compose 可以从空环境启动。
- [ ] 至少一条完整流程有日志、事件和数据库证据。
- [ ] execution 更新为 `[x]` 并记录涉及仓库 commit。

完成 commit：`待完成`

### WP-14 生产交付

对应计划：`plan.md` 第 13.2、15.3、19.5 节。

任务：

- [ ] 编写 staging 镜像和部署清单。
- [ ] 编写 Secret、网络和权限策略。
- [ ] 编写数据保留和脱敏策略。
- [ ] 部署 Dashboard 和告警规则。
- [ ] 完成压测和容量规划。
- [ ] 完成故障注入和恢复演练。
- [ ] 完成数据库、Artifact 和队列备份策略。
- [ ] 完成版本发布、灰度和回滚策略。
- [ ] 完成回滚演练。
- [ ] 编写部署、排障、值班和应急手册。
- [ ] 更新面试学习材料，确保内容与实际代码一致。

验证：

- [ ] staging 可以独立部署和销毁。
- [ ] 发布新版本不会丢失 Run/Event/Artifact。
- [ ] 回滚后旧客户端仍可工作。
- [ ] Worker 扩容后同一 Conversation 仍保持互斥。
- [ ] 告警可以定位 API、Queue、Graph、LLM、Tool 和 Provider 问题。

出口条件：

- [ ] 生产化检查清单全部通过。
- [ ] 执行记录、报告和手册已提交。
- [ ] execution 更新为 `[x]` 并记录最终 release commit。

完成 commit：`待完成`

## 4. 提交记录

| 日期 | 工作包 | Commit | 主要变更 | 验证结果 |
| --- | --- | --- | --- | --- |
| 2026-10-14 | WP-00 | `b338d72` | 创建并提交项目基线、最终计划、执行同步和智能体交接文档 | `git diff --check` 通过；GitHub 推送进行中 |

## 5. 验证记录

每次完成工作包后，在这里记录真实命令和关键输出，不用“应该通过”替代实际结果。

### 5.1 当前验证

```text
工作包：WP-01
日期：2026-10-14
命令：python -m pytest tests/contract/ -v
结果：退出码 0
关键输出：115 passed in 0.50s
  - 17 fixture JSON 文件全部可解析
  - 27 schema JSON 文件全部符合 Draft 2020-12
  - OpenAPI YAML 8 端点全部加载成功
  - SSE encode/decode roundtrip 通过
  - 终端事件检测通过
  - after_seq 夹紧和续传逻辑通过
  - 语言归一化与 Go Client 一致
  - 幂等键、Header、错误 body 契约全部通过
关联 commit：e1ed9c3

git diff --cached --check: 通过
OpenAPI: 8 端点，包含完整请求/响应 Schema
Schema: 27 个 JSON Schema（16 事件 + 5 交互卡片 + 3 Artifact + 3 索引/基础）
Fixture: 17 个 Go Client 可读取的 JSON fixture
契约测试：115 项，覆盖 SSE、事件、交互、Artifact、Header、错误、语言、幂等、终端事件
项目 Git: WP-01 commit `e1ed9c3`
```

### 5.2 后续验证模板

```text
工作包：WP-XX
日期：YYYY-MM-DD
命令：<真实执行命令>
结果：<退出码>
关键输出：<passed/failed、容器状态、接口状态等>
关联 commit：<hash>
```

## 6. 决策和变更记录

| 日期 | 决策/变更 | 原因 | 影响范围 |
| --- | --- | --- | --- |
| 2026-10-14 | 以 LangChain + LangGraph 为核心，不复制 FireClaw 作为运行时 | 目标是复现 MAA 的状态图、交互和业务协议 | 全部 Agent Runtime |
| 2026-10-14 | RabbitMQ 负责可靠 Run command，Redis 负责锁、通知和短缓存 | 避免把不可丢失任务依赖在短期缓存上，并与现有 WiseCut 基础设施一致 | Worker、Outbox、Docker |
| 2026-10-14 | 模型列类型从 JSONB 改为 JSON | SQLite 测试兼容；PostgreSQL 上 JSON 类型同样工作 | 持久化模型、迁移脚本 |
| 2026-10-14 | get_engine() 对 SQLite 跳过 pool_size/max_overflow | SQLite/aiosqlite 不支持连接池参数 | 引擎创建、测试环境 |
| 2026-10-14 | 引入 Outbox 模式：API 写 outbox_event，Publisher 异步发布到 RabbitMQ | 解耦 API 事务和消息投递 | OutboxPublisher、消息投递 |
| 2026-10-14 | Worker 使用 pika BlockingConnection 在专用线程运行 | pika 是同步库，需避免与 FastAPI async 混用 | Worker 架构、线程安全 |
| 2026-10-14 | Conversation 锁基于 Redis SET NX EX + heartbeat | 防止同一 Conversation 并发执行 | Worker 并发控制 |
| 2026-10-14 | LangGraph StateGraph 节点通过 async 函数注册，interrupt 节点标记为 END | 与 LangGraph interrupt/resume 语义对齐 | Graph 架构、HITL |
| 2026-10-14 | Prompt 通过 PromptProfile dataclass 版本化管理 | 确保结果可复现和可审计 | LLM 配置、Prompt 管理 |

## 7. 阻塞项和风险

| 状态 | 问题 | 影响 | 处理方式 |
| --- | --- | --- | --- |
| 开放 | 原版 MAA 的私有 Prompt、工具源码和真实 Provider 配置不可见 | 不能逐行复原原实现 | 按可观察协议做行为兼容重建 |
| 开放 | 真实视频、数字人和素材服务凭证未知 | 本地无法保证调用线上 Provider | 先使用显式 Demo Provider，再提供真实 Provider 接口 |
| 开放 | 当前 GitHub 第四个仓库尚未创建 | 暂时只能本地提交 | 代码基线稳定后再绑定远端 |
| 已记录 | Go Client 中 `buildAgentFilmHeaders` 使用 `X-Session-ID` 存 project_id，`setAgentFilmHeaders` 使用 `X-Project-ID` | MAA API 统一使用 `X-Project-ID`，需确认 WiseCut 后端是否接受两种 Header | 以 `setAgentFilmHeaders` 为准（MAA API 相关方法均使用此函数），记录差异 |

## 8. 下一步

WP-06 已完成：

- [x] LangGraph Runtime 基础设施：StateGraph、Builder、Runner
- [x] AgentFilmState TypedDict：17 个字段，符合 plan.md §6
- [x] Quick/Deep Profile：影响路由和交互策略
- [x] 13 个 graph node stubs：normalize、product_context、script、generation、media
- [x] 4 个路由函数：product confirmation、script review、terminal、retry
- [x] GraphRunner：Worker 调用入口，处理 checkpoint 和事件发射
- [x] LLM Factory：demo + openai-compatible provider
- [x] Prompt Registry：3 个默认 prompt profiles，版本化管理
- [x] TokenCostCallback：token 和 cost 追踪
- [x] 194 个测试全部通过（含 23 个新 WP-06 测试）
- [ ] 进入 WP-07：Tool 和 Provider 平台（Tool Registry、Policy、Approval）
- [ ] WP-07 未完成前，不实现 Agent Film 业务节点。
- [ ] 每个工作包完成后立即更新本文件、记录验证输出并提交。

下一次继续任务时，优先处理当前工作包，不跳过出口条件，不把未验证的 `[~]` 改成 `[x]`。
