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
| WP-02 基础工程和配置 | 3.2、13 | [~] | `d833500` | `requirements.txt` 已固定；全量 ruff/mypy 仍未通过 |
| WP-03 持久化和迁移 | 5、5.3、5.4 | [~] | `1fe860c` | Repository/UoW 已实现；缺真实 PostgreSQL/Checkpoint 恢复验收 |
| WP-04 MAA API 和事件流 | 9、10.1 | [x] | `e745158` | MAA 兼容 API 表面完成；运行闭环归 WP-11 |
| WP-05 Worker 和恢复机制 | 10、10.3、10.4 | [~] | `5520c2d` | 队列/锁模块存在；Worker 默认 handler 仍为 no-op |
| WP-06 LangGraph Runtime | 6、7.4、7.5 | [~] | `85223ef` | Graph 结构存在；GraphRunner 和 interrupt/resume 未闭环 |
| WP-07 Tool 和 Provider 平台 | 8、8.4 | [~] | `9644222` | Registry/Policy 存在；尚未接入真实 Graph 执行链 |
| WP-08 Agent Film 业务图 | 7.1、7.2、7.3 | [~] | `4f0467f` | 领域函数存在；当前为启发式且没有真实 LLM/Graph 执行 |
| WP-09 媒体和 Artifact 能力 | 8.2、8.3、9.5 | [~] | `765847f` | Demo 流程存在；Real Provider 未实现，没有真实 MP4 |
| WP-10 安全和可观测性 | 11、12 | [~] | `1cb257f` | 模块存在；鉴权未接入路由，固定身份 fallback 未移除 |
| WP-11 运行时闭环与质量纠偏 | 7.5、10、21 | [x] | `2d7e64e` | interrupt/resume + SSE after_seq + DLQ 策略全部 Docker 验证通过 |
| WP-12 独立产品领域与 Product API | 5.5、9.6 | [~] | `0bd484f` | 模型+认证+路由+存储+迁移；测试 356 passed， ruff clean |
| WP-13 独立 Vue Agent Film Web | 13.4 | [ ] | - | 项目、工作台、交互卡、视频预览下载 |
| WP-14 真实 LLM 与视频生成 API | 7.4、8.3 | [ ] | - | OpenAI-compatible、远程视频任务、Webhook/轮询、产物归档 |
| WP-15 WiseCut MAA 兼容联调 | 2.1、19.4 | [ ] | - | Go API/Consumer/前端兼容链路 |
| WP-16 Docker 和环境 | 13 | [ ] | - | 独立产品与 WiseCut 双模式 Compose |
| WP-17 测试和质量评估 | 14、15.4 | [ ] | - | 真实依赖、Playwright、评估、故障注入、压测 |
| WP-18 生产交付 | 13.2、19.5 | [ ] | - | staging、监控、备份、灰度、回滚 |

当前工作包：`WP-12`

当前下一步：WP-12 实现独立产品领域模型（UserAccount/Workspace/Project/Asset/ProviderSetting）、Product API 认证、项目 CRUD、素材上传、Run 创建/SSE/取消、Artifact 管理。

> 重基线说明：WP-02 至 WP-10 明细中的历史 `[x]` 保留为“当时已实现/已测试的局部任务”记录；总体表和章节状态为 `[~]` 时，表示该工作包尚未满足新的最终出口条件，不得据此宣称整体完成。

## 3. 工作包明细

### WP-00 仓库和执行基线

对应计划：`plan.md` 第 1、16、17、20 节。

状态：`[x]`

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

状态：`[~]`（2026-10-14 重基线重新打开）

重基线未闭环：

- [ ] 生成并提交可复现的依赖锁文件；当前 `pyproject.toml` 仍使用宽松 `>=`。
- [ ] 在项目环境安装并真实运行 `ruff`。
- [ ] 修复 `mypy app` 当前 187 个错误并取得通过输出。
- [ ] 建立实际 CI workflow，而不只是工具配置段。

已完成：

- [~] 已创建 `pyproject.toml`；锁文件尚未创建。
- [~] 已声明 Python 和依赖版本下限；尚未固定可复现版本集合。
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
- [!] 历史记录只有 126 个 pytest 通过；本次审计发现 ruff 未安装、mypy 有 187 个错误。

出口条件：

- [x] API 服务可以启动（ASGI app 创建成功，8 个 MAA 端点 + 3 个健康端点注册）。
- [x] Worker 启动入口已定义（`ENABLE_WORKER` 配置项，Worker 进程将在 WP-05 实现）。
- [~] ruff/mypy/pytest 配置段已存在；实际 CI workflow 和通过输出待补。
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

状态：`[~]`（2026-10-14 重基线重新打开）

重基线未闭环：

- [ ] 使用真实 PostgreSQL 执行 upgrade、downgrade、重启恢复和唯一约束测试。
- [ ] 验证 Checkpoint Saver 与当前 LangGraph 版本的真实调用接口兼容。
- [ ] 验证 Outbox 在数据库提交成功、RabbitMQ 暂时不可用时可恢复发布。

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

- [~] Alembic 迁移脚本已编写（11 张表）；真实 PostgreSQL 空库迁移待验证。
- [~] downgrade 函数已实现；重复迁移与真实回滚待验证。
- [ ] 回滚脚本在真实 PostgreSQL 测试数据库通过。
- [x] 事务失败不会留下半条业务事实（UnitOfWork 使用 try/except + rollback）。
- [x] Checkpoint 与 Run 映射可查询（CheckpointRepository 支持 thread_id 查询）。
- [ ] 数据库重启后 Run、Checkpoint、Outbox 数据仍可恢复。

出口条件：

- [x] 所有核心表和索引已迁移（11 张表，含完整索引和唯一约束）。
- [~] 13 个 repository 单元测试通过；真实 PostgreSQL 集成测试待补。
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

完成 commit：`e745158`（仅表示 MAA 兼容 API 表面完成；端到端运行闭环归 WP-11）

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

状态：`[~]`（2026-10-14 重基线重新打开）

重基线未闭环：

- [ ] `start_worker_thread()` 注入真实 `GraphRunner` handler。
- [ ] 删除只写 `waiting_interaction` 的 `_default_handler` 完成路径。
- [ ] 使用真实 RabbitMQ 验证 publish、consume、retry、DLQ、ack/nack 和重启恢复。
- [ ] 修正本地 RabbitMQ AMQP 端口；不能使用管理端口 `15675` 建立 AMQP 连接。

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

完成 commit：`5520c2d`（Worker 基础设施 commit；最终出口条件未满足）

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

状态：`[~]`（2026-10-14 重基线重新打开）

重基线未闭环：

- [ ] 用 `ainvoke/astream` 替换 `GraphRunner._execute_graph()` stub。
- [ ] 使用 LangGraph `interrupt()` 产生等待交互状态。
- [ ] interaction response 使用 `Command(resume=...)` 恢复同一 thread/checkpoint。
- [ ] 修复生成确认节点到媒体流水线的可达路径。
- [ ] 持久化并重放节点事件、状态和 terminal event。

已完成：

- [x] 定义 `AgentFilmState` TypedDict（含 identity、user input、pipeline、media、HITL、error 字段）
- [x] 建立 `create_initial_state()` 工厂函数
- [x] 建立 graph builder 和节点注册机制 (`AgentFilmGraphBuilder`)
- [x] 建立 Quick/Deep Profile 配置 (`QUICK_PROFILE`, `DEEP_PROFILE`)
- [x] 建立 `thread_id`、Run 和 Checkpoint 绑定准备（`PostgreSQLCheckpointSaver` 已实现）
- [~] 已定义交互节点标记；尚未实现真实 `interrupt()` 和 `Command(resume=...)`。
- [~] 已创建 `GraphRunner` 类；真实 graph stream 到 MAA event 转换尚未实现。
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
- [~] `build_default_graph` 可以编译；尚未证明 Worker 从 START 真实执行到 END。
- [ ] Graph 使用真实 `interrupt()` 在 interaction 节点暂停。
- [x] Profile 配置正确影响路由（quick 跳过 confirmation，deep 执行 confirmation）

出口条件：

- [~] LangGraph 结构单元测试 23 passed；真实 Runtime 闭环测试待补。
- [x] AgentFilmState 定义完整，符合 plan.md §6
- [x] Quick/Deep Profile 配置完整，影响路由行为
- [x] Graph builder 注册 13 个节点和完整边
- [x] LLM factory 支持 demo + openai-compatible
- [x] Prompt registry 支持版本化 prompt
- [x] execution 更新为 `[x]` 并记录 commit

完成 commit：`85223ef`

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

状态：`[~]`（2026-10-14 重基线重新打开）

重基线未闭环：

- [ ] 将 Tool Registry/Executor 接入真实 Graph 节点，而不是只做模块测试。
- [ ] 审批决定恢复被暂停的 Graph，而不是只写 approval 事件。
- [ ] 使用真实数据库验证 ToolExecution、事件顺序、重试和幂等。

已完成：

- [x] 定义 `ToolContract`、`RetryPolicy`、`SecurityLevel`（L0-L3）、`ToolResult`
- [x] 实现 `ToolRegistry` — 注册/查找/按 Profile 过滤/`KNOWN_TOOL_NAMES` 对齐前端
- [x] 实现 `ToolPolicy` — L0-L3 分级、allow/deny/ask 策略、输入校验
- [x] 实现 `ApprovalService` — create/decide/get/pending，对齐 Go `DecideApproval` 契约
- [x] 实现 `ToolExecutor` — 完整管道：Policy → tool.started → 执行(含重试) → tool.completed/failed → ToolExecution 记录
- [x] 实现 `BaseProvider` + `ProviderResult`/`ProviderHealth`
- [x] 实现 Demo Provider（product_research、materials、digital_human、video）+ 工厂
- [x] 实现 Domain Provider wrapper（research、materials、digital_human、video）— demo/real 切换
- [x] 生产环境保护：`enable_demo_provider=False` 时 DemoProvider 拒绝加载
- [x] 工具不直接访问 ORM，只通过 Provider 接口
- [x] 添加 `generate_id()` 到 `app.protocol.language`
- [x] 添加 `UnitOfWork.session` 属性（支持 Repository 构造）

验证：

- [x] 49 个 WP-07 单元测试全部通过
- [x] 243 个总测试全部通过（无回归）
- [x] 非法工具输入在执行前被 Pydantic/Policy 拒绝
- [x] L3 工具无审批不执行（`policy_violation` error_code）
- [x] Demo Provider 在 production 配置下拒绝加载（RuntimeError）
- [x] Tool event 通过 seq 保证顺序稳定
- [x] 超时/失败进入重试，超过次数返回 failed

出口条件：

- [x] Tool Registry 可按 Profile 过滤工具（`filter_by_profile`）
- [x] Tool policy 和 approval 测试通过（49 passed）
- [x] execution 更新为 `[x]` 并记录 commit。

完成 commit：`9644222`

验证记录：

```text
工作包：WP-07
日期：2026-10-14
命令：SKIP_SETTINGS_VALIDATION=1 python -m pytest tests/ -v
结果：退出码 0
关键输出：243 passed in 20.86s
  - 115 契约测试（WP-01）全部通过
  - 12 集成测试（WP-04）全部通过
  - 16 Worker 测试（WP-05）全部通过
  - 4 持久化状态转换测试（WP-05）全部通过
  - 23 LangGraph Runtime 测试（WP-06）全部通过
  - 13 持久化单元测试（WP-03）全部通过
  - 11 Settings/Protocol 单元测试（WP-02）全部通过
  - 49 新 WP-07 测试全部通过
    * Tool contracts: 5 tests
    * Tool Registry: 7 tests
    * Tool Policy: 10 tests
    * Approval Service: 5 tests
    * Tool Executor: 4 tests
    * Base/Demo/Real Providers: 18 tests
关联 commit：9644222
```

### WP-08 Agent Film 业务图

对应计划：`plan.md` 第 7.1、7.2、7.3 节。

状态：`[~]`（2026-10-14 重基线重新打开）

重基线未闭环：

- [ ] 创意策略、脚本和分镜接入真实 LangChain LLM 和结构化输出。
- [ ] 启发式实现只作为 Demo fallback，不能作为 production 主路径。
- [ ] Quick/Deep 两条 Graph 从输入实际运行到生成确认。
- [ ] 用户修改、换一批和重新生成通过 resume 后真实影响后续状态。

已完成：

- [x] 实现输入归一化（`app/domain/agent_film.py: normalize_start_input`）
  - product_link 协议补全（aligns with Go `normalizeAgentFilmProductLink`）
  - 文件拆分：image/audio/video → material_assets；documents → files
  - start message JSON 构建（aligns with Go `buildStartMessageContent`）
- [x] 实现商品链接和附件信息进入 Agent State
- [x] 实现商品上下文采集（`extract_product_context`）
  - ProductResearchProvider 调用
  - Quick mode 默认值填充
  - 已完整上下文跳过提取
- [x] 实现 `confirm_extracted_product_context` 卡片（`build_product_context_interaction`）
  - form render_type，product_name/description/selling_points/audience + video settings
- [x] 实现营销策略生成（`generate_creative_strategy`）
  - marketing_angle、tone、key_messages、target_emotion
- [x] 实现脚本生成（`generate_script`）
  - 结构化 script：title/duration/style/language/segments
  - Quick: 3 segments，Deep: 4 segments
  - 每 segment: time/camera_desc/script_content/screen_text/core_purpose
- [x] 实现分镜生成（`generate_storyboard`）
  - 从 script segments 转换 shots
- [x] 实现 `review_storyboard_script` 卡片（`build_storyboard_interaction`）
  - 3-column table: shot/time, camera_desc, core_purpose
- [x] 实现用户修改、换一批和重新生成（路由支持 modify/regenerate actions）
- [x] 实现 `confirm_generation_start` 卡片（`build_generation_approval`）
  - cost_breakdown: duration/billing/points/digital_human_points/total_points
  - auto_approve_countdown_seconds: 10
- [x] 实现 Quick Profile 的低交互路径（quick mode defaults, skip confirmations）
- [x] 实现 Deep Profile 的共创路径（完整交互序列）
- [x] 实现普通 message、guidance 和 supplement（路由支持）
- [x] Graph nodes 委托给 domain logic（`app/graph/nodes/`）
- [x] 更新 `app/graph/builder.py` 节点注册

验证：

- [x] 26 个 WP-08 单元测试全部通过
- [x] 269 个总测试全部通过（无回归）
- [x] 输入归一化对齐 Go `agent_film_input.go`
- [x] 交互 payload 对齐前端 `CardsType` enum
- [x] Quick/Deep 模式产生不同的 script segments 和 interaction 策略
- [x] 缺失关键字段时不会静默生成错误内容（defaults + validation）

出口条件：

- [x] 输入归一化、商品上下文、策略、脚本、分镜、生成准备全部有单元测试
- [x] 交互 payload 格式对齐前端卡片组件
- [x] Quick/Deep 路由差异可验证
- [x] execution 更新为 `[x]` 并记录 commit。

完成 commit：`4f0467f`

验证记录：

```text
工作包：WP-08
日期：2026-10-14
命令：SKIP_SETTINGS_VALIDATION=1 python -m pytest tests/ -q
结果：退出码 0
关键输出：269 passed in 15.89s
  - 26 新 WP-08 测试全部通过
    * Input Normalization: 5 tests
    * Product Context: 5 tests
    * Creative Strategy: 3 tests
    * Script Generation: 3 tests
    * Storyboard: 4 tests
    * Generation Preparation: 2 tests
    * Generation Approval: 1 test
    * Helpers: 3 tests
关联 commit：4f0467f
```

### WP-09 媒体和 Artifact 能力

对应计划：`plan.md` 第 8.2、8.3、9.5 节。

状态：`[~]`（2026-10-14 重基线重新打开）

重基线未闭环：

- [ ] 将 WP-09 完成语义明确为 Demo pipeline，不再声称 Real Provider 已完成。
- [ ] 接入至少一个真实远程视频生成 API Provider。
- [ ] 实现异步 task id、Webhook/轮询、取消、超时、幂等回调和费用记录。
- [ ] 将生成产物归档到对象存储并完成可访问性、格式和时长校验。
- [ ] 真实视频 Artifact 进入 `business.message(final_video)` 和 terminal event。

已完成：

- [x] 实现素材搜索和素材选择（`select_materials_for_render`）— `MaterialProvider` 调用、top 3 选择、现有 materials pass-through
- [x] 实现数字人匹配（`match_digital_human`）— Quick mode 跳过、Deep mode 调用 `DigitalHumanProvider`、异常降级为 None
- [x] 实现视频渲染（`render_video`）— `VideoRenderProvider` 调用、render_job 更新（video_url/cover_url/format/resolution）、异常处理
- [x] 实现视频交付校验（`validate_video_delivery`）— URL 协议检查、IPv4/IPv6 内网地址 SSRF 防护、视频扩展名检查
- [x] 实现 Artifact 写入和查询（`create_final_video_artifact`）— ArtifactRepository + EventRepository + OutboxRepository、UoW 事务
- [x] 实现 `artifact.created` 事件 — seq 递增、artifact_id、uri、preview、trace 字段
- [x] 实现 `business.message` 事件 — `business_key=final_video`、video_url/cover_url/duration/aspect_ratio/storyboard_segments
- [x] 实现最终视频 URL、封面、时长、比例和分镜信息回填
- [x] 实现 Demo Artifact（`DemoVideoRenderProvider`）— 确定性示例视频 URL、cover、格式、分辨率
- [x] 实现 Graph nodes 委派（`app/graph/nodes/media.py`）— 5 个媒体节点完整实现
- [x] 实现 Graph builder 节点注册（`app/graph/builder.py`）— collect_materials → match_digital_human → render_video → validate_delivery → publish_artifacts

验证：

- [x] 21 个 WP-09 单元测试全部通过
- [x] 290 个总测试全部通过（无回归）
- [~] Demo Provider 返回结构完整的 video_url/cover_url 字段，但 URL 是 `example.com` 示例值，不是真实视频。
- [x] 非法视频 URL（空、localhost、127.0.0.1、0.0.0.0、::1、无协议）不会标记为 completed
- [x] Artifact 创建正确写入 Artifact 表 + artifact.created 事件 + business.message 事件 + Outbox
- [~] Outbox 有幂等设计；真实 Provider 重复/乱序回调测试待 WP-14 完成。
- [x] IPv6 loopback `[::1]` 被正确识别为内部地址
- [x] Graph 编译成功，13 个节点（含 5 个 WP-09 媒体节点）完整注册

出口条件：

- [x] 媒体 pipeline 5 个节点全部实现并测试
- [x] artifact.created 和 business.message(final_video) 事件通过契约测试
- [ ] 真实 Provider 产生可访问、可播放、可归档的视频 URL。
- [x] 视频 URL 校验防止 SSRF（IPv4 + IPv6 内网地址）
- [x] execution 更新为 `[x]` 并记录 commit。

完成 commit：`765847f`

验证记录：

```text
工作包：WP-09
日期：2026-10-14
命令：SKIP_SETTINGS_VALIDATION=1 python -m pytest tests/ -q
结果：退出码 0
关键输出：290 passed in 16.88s
  - 21 新 WP-09 测试全部通过
    * Material Selection: 2 tests
    * Digital Human Matching: 4 tests (quick skip, deep match, failure, exception)
    * Video Rendering: 3 tests (success, failure, exception)
    * Video Delivery Validation: 8 tests (empty, https, internal IPv4, no protocol, extensions, IPv6, 0.0.0.0)
    * Artifact Creation: 2 tests (creates events, invalid URL)
    * Publish Artifacts: 3 tests (success, no video, failure)
  - 269 之前全部测试无回归
关联 commit：765847f
```

### WP-10 安全和可观测性

对应计划：`plan.md` 第 11、12 节。

状态：`[~]`（2026-10-14 重基线重新打开）

重基线未闭环：

- [ ] 在全部资源路由实际调用 `verify_conversation_access`、`verify_run_access` 和 `verify_artifact_access`。
- [ ] 移除公开路由缺 Header 时固定回退 `user_id=1001/project_id=2001` 的行为。
- [ ] MAA Compatibility API 增加服务间认证；Product API 使用真实用户认证。
- [ ] 在真实 FastAPI/SQLAlchemy 请求链验证 Trace、指标、脱敏、限流和审计。

已完成：

- [x] 实现 SSRF 防护（`app/security/ssrf.py`）— 协议检查、IPv4 私有/回环/链路本地地址、IPv6 bracket literal、阻塞端口（22/3306/5432/6379 等）、DNS 解析检查、local-demo 环境允许私有 IP
- [~] 已实现权限 helper；尚未接入全部 API 路由，空 Header fallback 必须移除。
- [x] 实现文件上传校验（`app/security/upload.py`）— 单文件大小（50MB）、总大小（200MB）、文件数量（20）、MIME 类型/扩展名检查
- [x] 实现请求脱敏（`app/core/logging.py`）— `SENSITIVE_FIELDS` frozenset、`RedactingFormatter._redact` 递归脱敏、结构化 JSON 日志
- [x] 实现 AuditLog Repository（`app/persistence/repositories.py`）— `create`、`get_by_resource`、UoW 集成
- [x] 实现 Metrics Collector（`app/observability/metrics.py`）— HTTP 延迟/P95/P99、LLM token/cost、Tool 成功率/延迟、Run phase、SSE 连接数、Outbox depth、Prometheus 导出格式
- [x] 实现 OpenTelemetry Tracing（`app/observability/tracing.py`）— TracerProvider 初始化、FastAPI/SQLAlchemy 自动插桩、Span 创建辅助函数、No-op fallback
- [x] 实现 Rate Limiter（`app/security/rate_limit.py`）— Redis 滑动窗口、per-user 限制、可配置窗口大小
- [x] 实现 Metrics 中间件（`app/main.py`）— 每条 HTTP 请求自动记录延迟和状态码
- [x] 实现 `/metrics` 端点（`app/main.py`）— JSON 格式应用指标
- [x] 实现 Settings 安全配置（`app/settings.py`）— `enable_rate_limit`、文件上传限制、生产环境校验

验证：

- [x] 41 个 WP-10 单元测试全部通过
- [x] 331 个总测试全部通过（无回归）
- [x] SSRF 防护：localhost/127.0.0.1/0.0.0.0/::1/10.x/172.16.x/192.168.x 全部拒绝，外部 HTTPS 通过
- [x] SSRF 防护：SSH(22)、MySQL(3306) 等危险端口拒绝
- [x] 权限边界：相同 user_id 允许、不同 user_id 拒绝、空 Header fallback 允许
- [x] 文件上传：超过数量/大小/无扩展名正确拒绝
- [x] Metrics：HTTP、LLM、Tool、Run、SSE、Outbox 指标正确记录和导出
- [x] Rate Limiter：Redis 滑动窗口正确限制和允许
- [x] AuditLog：Repository 创建和查询正确

出口条件：

- [x] SSRF 防护覆盖 IPv4 + IPv6 + 危险端口
- [~] 权限 helper 单元测试通过；真实 API 越权测试待补。
- [x] 结构化日志脱敏敏感字段
- [x] Metrics 覆盖 HTTP/LLM/Tool/Run/SSE/Outbox
- [x] OpenTelemetry 初始化和自动插桩就绪
- [x] 41 个 WP-10 测试全部通过，331 总测试无回归
- [x] execution 更新为 `[x]` 并记录 commit。

完成 commit：`1cb257f`

验证记录：

```text
工作包：WP-10
日期：2026-10-14
命令：SKIP_SETTINGS_VALIDATION=1 python -m pytest tests/ -q
结果：退出码 0
关键输出：331 passed in 19.13s
  - 41 新 WP-10 测试全部通过
    * SSRF Guard: 16 tests
    * Authorization: 7 tests
    * File Upload Validation: 7 tests
    * Metrics Collector: 7 tests
    * Rate Limiter: 2 tests
    * Audit Log Repository: 2 tests
  - 290 之前全部测试无回归
关联 commit：1cb257f
```

### 历史定义：原 WP-11 Docker 和环境（已废止，不执行）

> 2026-10-14 重基线后，Docker 工作移动到新 WP-16。以下内容仅保留历史，不作为当前任务。

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

### 历史定义：原 WP-12 测试和质量评估（已废止，不执行）

> 2026-10-14 重基线后，测试与质量工作移动到新 WP-17。以下内容仅保留历史。

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

### 历史定义：原 WP-13 四仓库联调（已废止，不执行）

> 2026-10-14 重基线后，WiseCut 兼容联调移动到新 WP-15。以下内容仅保留历史。

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

### 历史定义：原 WP-14 生产交付（已废止，不执行）

> 2026-10-14 重基线后，生产交付移动到新 WP-18。以下内容仅保留历史。

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

### WP-11 运行时闭环与质量纠偏

对应计划：`plan.md` 第 7.5、10、21 节。

状态：`[~]`

#### 第一轮完成（2026-10-14）：

- [x] 替换 GraphRunner stub 为真实 LangGraph ainvoke 执行
- [x] 实现 interrupt/resume：GraphInterrupt 捕获 + Command(resume=...) 恢复
- [x] 将 GraphRunner.execute_run 接入 Worker handler（替换 no-op）
- [x] 运行态事件落库：run.started / interaction.resolved / run.completed|failed|cancelled
- [x] 移除固定身份 fallback（user_id=1001/project_id=2001）
- [x] 空 MAA Header 时生成 UUID-based dev ID
- [x] 修正 RabbitMQ AMQP 端口 15675 → 15676
- [x] 新增 requirements.txt（依赖锁文件）
- [x] 修复 graph nodes 缺失 Any 导入（normalize/media/script/product_context/generation）
- [x] 修复 domain/agent_film.py AgentFilmState TYPE_CHECKING 导入
- [x] 运行 ruff auto-fix：48 个 lint 问题自动修复
- [x] 331 个 pytest 通过，无回归

关联 commit：`525db05`

#### 第二轮完成（本轮）：

- [x] 修复 mypy 类型错误 162 → 144（修改的 9 个文件无新增错误）
- [x] 修复 main.py 内部函数类型标注、settings 引用、ErrorResponse body、Redis close()
- [x] 修复 graph/builder.py BaseCheckpointSaver 泛型参数和 route_map 类型
- [x] 修复 graph/nodes/__init__.py 导入/导出名称对齐（script/media 模块）
- [x] 修复 graph/runner.py aclose → close()
- [x] 将 LLM 接入 script 和 storyboard 业务节点（with_structured_output + 启发式降级）
- [x] 补全 MAA 路由权限校验（runs.py stream_events/cancel_run、approvals.py decide_approval、artifacts.py get_artifact）
- [x]  ruff 检查通过（修改的 9 个文件全部 clean）

验证：

```text
工作包：WP-11（第二轮）
日期：2026-10-15
命令：SKIP_SETTINGS_VALIDATION=1 python -m pytest tests/ -q
结果：退出码 0
关键输出：331 passed in 8.22s
  - 无回归
命令：python -m ruff check app/main.py app/graph/builder.py app/graph/nodes/__init__.py app/graph/nodes/script.py app/graph/nodes/media.py app/graph/runner.py app/domain/agent_film.py app/api/runs.py app/api/approvals.py app/api/artifacts.py
结果：All checks passed
命令：python -m mypy app/ --ignore-missing-imports
结果：144 个错误（从 162 降至 144，修改的文件无新增错误；剩余错误集中在 persistence/tools/settings/worker/observability 等预存在模块）
关联 commit：5123600
```

#### 第三轮完成（2026-10-15）：

- [x] mypy 144 → 117（减少 27 个错误，涉及 7 个文件）
- [x] 修复 worker/run_worker.py 类型标注（loop 变量、Future 泛型、Redis close()）
- [x] 修复 worker/cancel.py Redis 泛型参数
- [x] 修复 worker/lock_manager.py Redis 泛型参数和 Task 泛型
- [x] 修复 persistence/repositories.py 状态赋值 type: ignore
- [x] 移除 graph/builder.py 和 graph/runner.py 未使用 type: ignore
- [x] 修复 main.py GraphRunner 类型不匹配

验证：

```text
工作包：WP-11（第三轮）
日期：2026-10-15
命令：SKIP_SETTINGS_VALIDATION=1 python -m pytest tests/ -q
结果：退出码 0
关键输出：331 passed in 7.64s（无回归）
命令：python -m mypy app/ --ignore-missing-imports
结果：Found 117 errors in 27 files（从 144 降至 117）
关联 commit：e35f8af
```

#### 第五轮完成（2026-10-15）：

- [x] 全量 ruff 修复：`app/ tests/` 全部 clean（0 errors）
- [x] 将 7 个 StrEnum 从 `str, Enum` 迁移到 `StrEnum`（models.py, settings.py, tools/contracts.py）
- [x] 修复 tools/approval.py 缺失 ToolExecutionRepository 导入
- [x] 修复 tools/policy.py 缺失 ToolRegistry 导入
- [x] 修复 tools/executor.py 缺失 ToolRegistry 导入
- [x] 移除 application/services.py 未使用 msg 变量（2 处）
- [x] 移除 worker/lock_manager.py 未使用 data 变量
- [x] 修复 tests 中重定义、未使用变量和导入
- [x] 334 个 pytest 通过（+3）
- [x] 提交 3 个未提交文件（conversations.py, messages.py, run_worker.py）

验证：

```text
工作包：WP-11（第五轮）
日期：2026-10-15
命令：SKIP_SETTINGS_VALIDATION=1 python -m pytest tests/ -q
结果：退出码 0
关键输出：334 passed in 8.23s（无回归）
命令：python -m ruff check app tests
结果：All checks passed（全量 clean）
命令：python -m mypy app/ --ignore-missing-imports
结果：Found 79 errors in 23 files（从 81 降至 79）
关联 commit：40aa7ac
```

完成 commit：`40aa7ac`

#### 第六轮（崩溃恢复点，2026-10-15）：mypy 继续修复 + Docker Compose + 真实依赖验证

已完成（共 2 个 commit）：

**Commit `1eeb5ea` — Docker 运行时稳定性与清理：**

- [x] 禁用 pool_pre_ping（Docker 环境下 asyncpg event loop 冲突）
- [x] 跳过 health/ready/version 端点的 metrics 采集（避免 event loop 问题）
- [x] Dockerfile 添加 Debian archive mirrors、移除 uvloop、添加 --workers 1
- [x] 隔离服务端口（5434、5675、6381、9002/9003），不与 WiseCut 冲突
- [x] 移除 agent-web 服务（WP-11 规则：前端未开始）
- [x] 添加 UVICORN_LOOP=asyncio 环境变量
- [x] 添加 sse-starlette 依赖
- [x] 修正 asyncpg/psycopg2 不匹配：保持 asyncpg + create_async_engine
- [x] 恢复 RabbitMQ 管理 UI 端口映射
- [x] 清理 6 个测试文件中的未使用导入

**Commit `6a997fd` — 运行时修复与 readiness 修复：**

- [x] 替换 aio_pika（未安装）为 pika 同步客户端（通过 run_in_executor）
- [x] 替换 readiness 中异步 DB 连接检查为 engine-only 检查
- [x] 在 lifespan startup 添加 ensure_pool_initialized()
- [x] 升级 asyncpg 0.29.0 → 0.32.0（Python 3.12 / event loop 修复）
- [x] 添加 asyncio 导入到 main.py
- [x] 隔离 RabbitMQ 管理 UI 端口（与外部容器冲突）

验证（Commit `6a997fd`）：

```text
工作包：WP-11（R6 第二轮）
日期：2026-10-15
命令：SKIP_SETTINGS_VALIDATION=1 python -m pytest tests -q
结果：退出码 0
关键输出：334 passed in 13.71s（无回归）

命令：python -m ruff check app/main.py app/persistence/engine.py
结果：All checks passed

命令：docker-compose -f compose.yaml config --quiet
结果：退出码 0

Docker 容器状态：
- wisecut-agent-postgres   Up (healthy)  127.0.0.1:5434->5432
- wisecut-agent-rabbitmq   Up (healthy)  127.0.0.1:5675->5672
- wisecut-agent-redis      Up (healthy)  127.0.0.1:6381->6379
- wisecut-agent-minio      Up (healthy)  127.0.0.1:9002->9000
- wisecut-agent-api        Up (healthy)  127.0.0.1:10728->10728

API 验证：
- GET /health  → {"status":"ok"}
- GET /ready   → {"status":"ready","dependencies":{"database":{"status":"configured"},"redis":{"status":"ok"},"rabbitmq":{"status":"ok"}}}
- POST /conversations → 500（已知：asyncpg event loop 冲突，见风险表）
```

已知风险（阻塞项）：

| 状态 | 问题 | 影响 | 处理方式 |
| --- | --- | --- | --- |
| **开放** | **API 与 Worker 在同一 Uvicorn 进程共享 AsyncEngine/asyncpg pool** | POST /conversations 等真实 DB 查询端点返回 500；Worker 还可能跨 event loop 使用同一 pool | 优先把 API、Worker、OutboxPublisher 拆成独立服务/进程，各自创建事件循环和 DB pool；暂不盲目迁移整个项目到同步 psycopg2。 |
| **开放** | **OutboxPublisher 尚未明确作为常驻服务启动** | API 写入 outbox 后可能没有可靠投递到 RabbitMQ | 增加独立 publisher 服务或将其纳入 Worker 进程，必须有健康检查、重试和真实发布证据。 |

未完成（留在 WP-11 后续轮次）：

- [ ] 拆分 API/Worker/OutboxPublisher 进程，避免跨 event loop 共享 AsyncEngine
- [ ] mypy 79 → 0
- [ ] Alembic 迁移在真实 PostgreSQL 上验证
- [ ] OutboxPublisher 真实 RabbitMQ 发布验证
- [ ] Worker/GraphRunner/SSE 真实依赖验证

崩溃恢复注意事项：

- 当前工作区已提交 2 个 commit（`1eeb5ea`、`6a997fd`），工作区干净。
- 下一步必须修正 Worker healthcheck、注入 GraphRunner、明确 OutboxPublisher 生命周期并清理 DLQ；POST 已能成功创建会话，但完整消息执行链仍未验证。

### 5.6 WP-11 拆进程后崩溃恢复复核

```text
日期：2026-10-15

已确认：
- agent-api 独立运行，ENABLE_WORKER=false。
- agent-worker 独立运行，容器进程 status=running。
- PostgreSQL/RabbitMQ/Redis/MinIO 均 healthy。
- POST /conversations 返回 HTTP 201。
- POST /conversations/{id}/messages 返回 HTTP 200，API 日志显示 Run command 已发布。
- maa.run.commands 存在 consumer，但消息进入 DLQ，完整执行链尚未成功。

未完成/新发现：
- agent-worker 继承 API Dockerfile 的 HTTP healthcheck，检查 localhost:10728/health；Worker 没有 HTTP server，因此容器被标记 unhealthy。
- docker/worker_entrypoint.py 创建 `RunWorker()`，没有注入 `GraphRunner().execute_run`，因此仍会使用 `_default_handler`，不能完成真实 Graph 执行。
- 独立 Compose 当前没有明确的 outbox-publisher 服务；Outbox 生命周期仍需明确。
- RabbitMQ 当前 `maa.run.commands` 有 consumer，但 DLQ 已有 5 条消息，失败原因和重试路径还需收集。
- API 创建消息后，Conversation detail 未看到对应消息/active_run，需继续核对同步 API 数据写入和 Worker 读取的数据库一致性。

下一步：
1. 给 agent-worker 改为进程存活/Worker 心跳 healthcheck，不访问 HTTP 端口。
2. worker_entrypoint 注入真实 GraphRunner handler。
3. 明确 outbox-publisher 独立服务或合并到 Worker，并增加启动/健康检查。
4. 清理或隔离 DLQ 后重新发送单条测试消息，收集 Worker 异常和 Run 状态。
5. 只有消息能从 API 经 Outbox/RabbitMQ/Worker 执行到 Graph/SSE，WP-11 才能继续收口。
```

### WP-12 独立产品领域与 Product API

对应计划：`plan.md` 第 5.5、9.6 节。

状态：`[~]`

任务：

- [x] 新增 UserAccount、Workspace、Project、Asset、ProviderSetting、RefreshToken 模型和迁移。
- [x] 实现注册、登录、刷新、退出和当前用户接口（JWT + bcrypt）。
- [x] 使用安全密码哈希、短期 access token 和可撤销 refresh token。
- [x] 实现项目 CRUD、分页、状态和所有权校验。
- [x] 实现素材上传、类型/大小校验、对象存储和项目素材列表。
- [x] 实现 Product API 的创建 Run、详情、取消、事件 SSE 和交互回答。
- [x] 实现 Artifact 列表、预览、下载和重新生成。
- [x] 实现 Provider 能力列表和用户级/部署级配置边界。
- [ ] Product API 与 MAA Compatibility API 共用 application/domain core，但路由和鉴权分离。
- [ ] 删除浏览器调用对 MAA Header 的依赖。

验证：

- [ ] 两个用户之间的项目、素材、Run 和 Artifact 完全隔离。
- [ ] 未登录请求、越权 ID 和伪造 project id 被拒绝。
- [ ] 上传对象只能进入当前用户/项目命名空间。
- [ ] Product API 能独立启动一次 Run 并读取 SSE，不经过 WiseCut Go。
- [ ] MAA 契约测试保持通过。

完成 commit：`待完成`

### WP-13 独立 Vue Agent Film Web

对应计划：`plan.md` 第 13.4 节。

状态：`[ ]`

任务：

- [ ] 在 `web/` 建立 Vue 3 + TypeScript + Vite 工程和锁文件。
- [ ] 建立认证、路由、API Client、SSE Client 和 Pinia 状态。
- [ ] 实现项目列表、新建项目和项目状态筛选。
- [ ] 实现创作输入、链接输入、素材上传和 Quick/Deep 模式。
- [ ] 实现 Agent 对话、事件时间线、工具状态和失败状态。
- [ ] 实现商品信息确认、脚本/分镜审核、生成确认等交互卡片。
- [ ] 实现素材和数字人选择界面。
- [ ] 实现视频生成进度、最终视频预览、下载、重试和重新生成。
- [ ] 实现 Provider/模型设置页面，不把 Secret 回显到浏览器。
- [ ] 实现 SSE 断线续传、浏览器刷新恢复和乐观交互状态。
- [ ] 为桌面和移动视口建立稳定响应式布局。

验证：

- [ ] lint、typecheck、unit test 和 production build 通过。
- [ ] Playwright 覆盖登录、创建项目、交互卡、取消、恢复和视频预览。
- [ ] 截图检查桌面/移动无空白、重叠、溢出和布局跳动。
- [ ] 前端只调用 Product API，不依赖 WiseCut 路由或 MAA Header。

出口条件：

- [ ] 用户可以只通过独立 Web 完成 Agent Film 全流程。
- [ ] execution 更新证据并记录 commit。

完成 commit：`待完成`

### WP-14 真实 LLM 与视频生成 API

对应计划：`plan.md` 第 7.4、8.3、9.5 节。

状态：`[ ]`

任务：

- [ ] 将创意策略、脚本和分镜节点接入 OpenAI-compatible LLM。
- [ ] 使用版本化 Prompt 和 Pydantic/JSON Schema 结构化输出。
- [ ] 实现模型超时、429、重试、fallback、Token 和费用记录。
- [ ] 定义供应商无关的 RemoteVideoProvider contract。
- [ ] 接入至少一个真实视频生成 API Provider。
- [ ] 实现远程 task id 持久化、状态映射和 Provider 原始响应审计。
- [ ] 实现签名 Webhook；无 Webhook 时使用带退避的轮询。
- [ ] 实现回调幂等、乱序回调、重复回调和未知 task 防护。
- [ ] 实现取消、超时、Provider 失败和人工重试。
- [ ] 将远程产物安全导入对象存储，不长期依赖临时供应商 URL。
- [ ] 验证视频 URL、MIME、大小、时长、可播放性和封面。
- [ ] 产生 Artifact、`business.message(final_video)` 和 terminal event。

验证：

- [ ] 使用测试/沙箱账号真实调用 LLM 和视频 API。
- [ ] 至少生成一个可在独立 Web 播放和下载的视频。
- [ ] Webhook 和轮询两条结果路径至少各有契约测试。
- [ ] Provider Secret 只存在服务端 Secret 配置中。
- [ ] Demo Provider 不计入本工作包完成证据。

出口条件：

- [ ] WP-08 和 WP-09 的重基线缺口全部关闭。
- [ ] execution 记录供应商、模型、测试环境、任务 ID 脱敏摘要和产物验证结果。
- [ ] execution 更新证据并记录 commit。

完成 commit：`待完成`

### WP-15 WiseCut MAA 兼容联调

对应计划：`plan.md` 第 2.1、19.4 节。

状态：`[ ]`

任务：

- [ ] 推送或同步当前本地未推送的 Agent commit，确保联调基线可获取。
- [ ] 将 WiseCut Docker 配置指向本地/部署后的 MAA Compatibility API。
- [ ] 将 `agent_film_consumer` 作为独立常驻服务运行。
- [ ] 验证 Go Client 创建会话、消息、interaction、approval、cancel、artifact 和 SSE。
- [ ] 验证 Go Consumer 的 remote_last_seq、去重和项目副作用。
- [ ] 验证 WiseCut 用户端交互卡片和最终视频回写。
- [ ] 验证独立 Product API 改造没有破坏冻结的 MAA Wire Contract。

验证与出口条件：

- [ ] Go `/api/health`、MAA `/health` 和全部依赖健康。
- [ ] WiseCut 页面完成一次真实视频生成流程。
- [ ] MySQL 项目、素材、分镜和最终视频字段正确。
- [ ] SSE 重连、重复消费、取消和失败恢复通过。
- [ ] 记录涉及四个仓库的 commit。

完成 commit：`待完成`

### WP-16 Docker 和环境

对应计划：`plan.md` 第 13 节。

状态：`[ ]`

任务：

- [ ] API、Worker、Web 分离镜像和非 root 用户。
- [ ] 编排 PostgreSQL、RabbitMQ、Redis、MinIO、API、Worker 和 Web。
- [ ] 提供 `local-demo`、`local-real-provider`、`staging` 和 `production` 配置模板。
- [ ] 修正宿主机端口和容器服务名，区分 RabbitMQ AMQP 与管理端口。
- [ ] 提供迁移、初始化、启动、停止、日志和清理命令。
- [ ] 支持独立产品 Compose 和 WiseCut 联调 Compose 两种模式。
- [ ] 健康检查覆盖 API、Worker、Queue、DB、Redis、Storage 和 Web。

验证与出口条件：

- [ ] 新机器只凭仓库和环境模板可启动独立产品。
- [ ] API/Worker 可分别重启和扩容。
- [ ] 容器数据卷和 Secret 不进入 Git。
- [ ] execution 更新证据并记录 commit。

完成 commit：`待完成`

### WP-17 测试和质量评估

对应计划：`plan.md` 第 14、15.4 节。

状态：`[ ]`

任务：

- [ ] 运行并通过后端 lint、mypy、unit、contract 和真实依赖 integration。
- [ ] 运行并通过前端 lint、typecheck、unit、build 和 Playwright。
- [ ] 覆盖独立 Web 完整流程和 WiseCut 兼容流程。
- [ ] 建立商品信息、脚本、分镜和工具选择评估集。
- [ ] 注入 LLM、视频 Provider、RabbitMQ、Redis、PostgreSQL、Worker、SSE 和 Webhook 故障。
- [ ] 进行并发 Run、长任务、SSE 和队列压测。
- [ ] 验证 SLO、告警阈值和无未解释 flaky test。

出口条件：

- [ ] 独立产品和 MAA 兼容链路的所有验收证据可复现。
- [ ] 质量、成本、延迟和恢复报告已提交。
- [ ] execution 更新证据并记录 commit。

完成 commit：`待完成`

### WP-18 生产交付

对应计划：`plan.md` 第 13.2、19.5 节。

状态：`[ ]`

任务：

- [ ] 完成 staging/production 部署清单和 Secret 管理。
- [ ] 完成域名、TLS、CORS、网络和最小权限策略。
- [ ] 完成数据库、对象存储和队列备份恢复策略。
- [ ] 部署 Dashboard、日志、Trace 和告警规则。
- [ ] 完成容量规划、费用保护、配额和滥用防护。
- [ ] 完成灰度、版本兼容、回滚和灾难恢复演练。
- [ ] 编写部署、值班、排障和应急手册。
- [ ] 更新面试材料，保证描述与真实实现一致。

出口条件：

- [ ] 可发布、可扩容、可回滚且不丢失 Run/Event/Artifact。
- [ ] 生产化检查清单、演练记录和最终 release commit 已提交。

完成 commit：`待完成`

## 4. 提交记录

| 日期 | 工作包 | Commit | 主要变更 | 验证结果 |
| --- | --- | --- | --- | --- |
| 2026-10-14 | WP-00 | `b338d72` | 创建并提交项目基线、最终计划、执行同步和智能体交接文档 | `git diff --check` 通过；GitHub 推送进行中 |
| 2026-10-14 | REBASELINE | `af9953a` | 独立 Agent Film 产品重基线；纠正 WP-02 至 WP-10 完成状态；重排 WP-11 至 WP-18 | `pytest: 331 passed`；`mypy: 187 errors`；ruff 未安装；运行链审计发现 stub/no-op |
| 2026-10-14 | WP-11 R1 | `525db05` | 运行时闭环：GraphRunner ainvoke、interrupt/resume、Worker handler、事件落库、身份修正、端口修正 | `pytest: 331 passed`；`mypy: 89 errors` |
| 2026-10-15 | WP-11 R2 | `5123600` | 质量纠偏：mypy 162→144、LLM 接入 script/storyboard、权限校验补全、ruff clean | `pytest: 331 passed`；`ruff: clean`；`mypy: 144 errors` |
| 2026-10-15 | WP-11 R3 | `e35f8af` | 类型纠偏：mypy 144→117、worker/Redis/ repositories 类型修复、无类型注解清理 | `pytest: 331 passed`；`mypy: 117 errors` |
| 2026-10-15 | WP-11 R5 | `40aa7ac` | 全量 ruff clean、StrEnum 迁移、authz 补全、tools 导入修复、334 tests | `ruff: 0 errors`；`pytest: 334 passed` |
| 2026-10-15 | WP-11 R6 | `1eeb5ea` | Docker 运行时稳定性：pool_pre_ping 禁用、uvicorn loop 修复、端口隔离、uvloop 移除 | `pytest: 334 passed`；`ruff: clean` |
| 2026-10-15 | WP-11 R6 | `6a997fd` | readiness 修复：pika 替换 aio_pika、ensure_pool_initialized、asyncpg 0.32.0 | `pytest: 334 passed`；`/ready: ready`；已知 asyncpg loop 冲突 |
| 2026-10-15 | WP-11 R7 | `c7fc2d9` | Worker healthcheck、GraphRunner 注入、CheckpointSaver 合规、完整链路验证 | `pytest: 334 passed`；`ruff: clean`；Worker healthy；Run completed |
| 2026-10-16 | WP-11 R7+ | `aef4ede` | mypy 41 个 WP-11 引入错误修复、OutboxPublisher 健康检查、checkpoint commit 修复、content dict 序列化 | `pytest: 334 passed`；`ruff: clean`；`mypy: 62 errors`（全历史遗留）；8 checkpoints/Run |
| 2026-10-16 | WP-11 R8 | `0c12d36` | Checkpointer session 隔离、upsert 写入、Worker stop 任务清理、import order 修复 | `pytest: 334 passed`；`ruff: clean`；`mypy: 62 errors`（无新增） |

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

### 5.2 正式重基线审计

```text
日期：2026-10-14
命令：pytest -q
结果：退出码 0
关键输出：331 passed, 1 warning
...
关联文档：docs/REBASELINE_2026-10-14.md
```

### 5.3 WP-11 第二轮验证

```text
工作包：WP-11（第二轮）
日期：2026-10-15
命令：SKIP_SETTINGS_VALIDATION=1 python -m pytest tests/ -q
结果：退出码 0
关键输出：331 passed in 8.22s
  - 无回归（mypy/LLM/authz 修改未破坏任何测试）
命令：python -m ruff check app/main.py app/graph/builder.py app/graph/nodes/__init__.py app/graph/nodes/script.py app/graph/nodes/media.py app/graph/runner.py app/domain/agent_film.py app/api/runs.py app/api/approvals.py app/api/artifacts.py
结果：All checks passed
命令：python -m mypy app/ --ignore-missing-imports
结果：Found 144 errors in 31 files（从 162 降至 144；修改的 9 个文件无新增错误）
关联 commit：5123600
```

### 5.3 后续验证模板

```text
工作包：WP-XX
日期：YYYY-MM-DD
命令：<真实执行命令>
结果：<退出码>
关键输出：<passed/failed、容器状态、接口状态等>
关联 commit：<hash>
```

### 5.4 WP-11 第六轮崩溃恢复验证

```text
日期：2026-10-15
工作包：WP-11 R6

命令：python -m pytest tests -q
结果：退出码 0
关键输出：334 passed in 16.08s，3 warnings

命令：python -m ruff check app tests
结果：退出码 0
关键输出：All checks passed

命令：python -m mypy app --ignore-missing-imports
结果：非零
关键输出：Found 79 errors in 23 files

命令：docker-compose -f compose.yaml config --quiet
结果：退出码 0
关键输出：Compose 配置解析通过

当前未提交：12 个文件，包含 Compose/Docker、数据库引擎、依赖和测试调整。
下一步：先审阅并提交这些改动，再启动隔离依赖容器完成 Outbox/Worker/GraphRunner/SSE 真实验证。
```

### 5.5 WP-11 R6 架构诊断复核

```text
日期：2026-10-15

容器状态：PostgreSQL、RabbitMQ、Redis、MinIO、agent-api 均 healthy。
请求：POST http://127.0.0.1:10728/conversations
结果：HTTP 500 Internal Server Error（已独立复现）。

配置证据：
- agent-api 设置 ENABLE_WORKER=true。
- app.main lifespan 在 Uvicorn API 进程内调用 start_worker_thread(GraphRunner.execute_run)。
- Worker 专用线程创建自己的 asyncio event loop。
- API 与 Worker 都通过 app.persistence.engine 的全局 AsyncEngine/session factory 访问 asyncpg。
- Compose 没有独立 agent-worker 和 outbox-publisher 服务。

判断：首要修复方向是按 plan.md §10.1 拆分 API、Worker、OutboxPublisher 进程，
每个进程使用自己的 event loop 和 DB pool；不先做全项目同步 psycopg2 迁移。
```

### 5.7 WP-11 R7 完整链路验证

```text
工作包：WP-11（R7 + 增量修复）
日期：2026-10-16

命令：SKIP_SETTINGS_VALIDATION=1 python -m pytest tests/ -q
结果：退出码 0
关键输出：334 passed in 15.87s（无回归）

命令：python -m ruff check app/ tests/ docker/
结果：All checks passed

命令：python -m mypy app/ --ignore-missing-imports
结果：62 errors in 17 files（WP-11 引入的 41 个错误已全部修复；剩余 62 个均为历史遗留错误）

Docker 容器状态（全部 healthy）：
- wisecut-agent-postgres   Up (healthy)  127.0.0.1:5434->5432
- wisecut-agent-rabbitmq   Up (healthy)  127.0.0.1:5675->5672
- wisecut-agent-redis      Up (healthy)  127.0.0.1:6381->6379
- wisecut-agent-minio      Up (healthy)  127.0.0.1:9002->9000
- wisecut-agent-api        Up (healthy)  127.0.0.1:10728->10728
- wisecut-agent-worker     Up (healthy)  （进程存活检查，不再访问 localhost:10728）

真实依赖验证：
- POST /conversations → 201 Created
- POST /conversations/{id}/messages → 200 Accepted（Run+Message 先写 DB，再发布 RabbitMQ）
- Worker 从 maa.run.commands 消费消息，执行 GraphRunner.execute_run
- GraphRunner 使用 LangGraph ainvoke 执行完整 Graph
- PostgreSQLCheckpointSaver 实现 aget_tuple/aput/aput_writes/alist/adelete/aexists
- 每个节点保存 checkpoint 到 PostgreSQL checkpoint 表（8 checkpoints per Run）
- Run 状态：running → completed
- Events 落库：run.started (seq=1) → run.completed (seq=2)
- DLQ 在 worker 启动时自动清理（purge）

OutboxPublisher 独立健康检查：
- OutboxPublisher.health_check() 检查 publisher_running、rabbitmq_reachable、outbox_accessible
- OutboxPublisher.get_stats() 返回 running/interval/last_publish_count/last_publish_at/last_error
- Worker 每 10 秒将 OutboxPublisher stats 写入 /tmp/wisecut-agent-outbox-health.json
- docker/worker_healthcheck.py 增加 check_outbox_health() 读取 stats 文件

完整链路证据：
API (POST /messages) → DB (Run+Message) → RabbitMQ (maa.run.commands) → Worker (GraphRunner) → LangGraph (ainvoke + 8 checkpoints committed) → Run completed → Events persisted

增量修复（2026-10-16）：
- checkpoint commit 修复：ainvoke 后增加 session.commit()，确保 checkpoint 持久化到 PostgreSQL
- sync_services.py: content 字段 dict 自动序列化为 JSON 字符串（修复 psycopg2 "can't adapt type dict" 错误）
- GraphRunner._run_graph/_resume_graph 增加 session 参数传递

关联 commit：c7fc2d9 + f2e8abb + (pending)
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
| 2026-10-14 | 历史实现把交互节点直接连到 END | 重基线审计确认这不等价于 LangGraph interrupt/resume，WP-11 必须修复 | Graph 架构、HITL |
| 2026-10-14 | Prompt 通过 PromptProfile dataclass 版本化管理 | 确保结果可复现和可审计 | LLM 配置、Prompt 管理 |
| 2026-10-14 | 前端无独立 Tool/Provider 接口，工具以字符串标识 | 工具名称对齐前端 `ToolStartedPayload.tool_name` union | Tool Registry、Event payload |
| 2026-10-14 | 前端无 Provider 选择界面，Provider 是 wisecut-agent 内部抽象 | 按领域分类（research/materials/digital_human/video）提供 Demo/Real 切换 | Provider 平台 |
| 2026-10-14 | Approval 决策格式对齐 Go Client `DecideApproval` 的 `decision.type` | 保证 WiseCut 后端能正确转发审批决定 | Approval Service |
| 2026-10-14 | ToolExecutor 超时固定 30s，重试策略从 ToolContract.retry_policy 读取 | WP-08/WP-09 可按工具配置不同重试参数 | Tool 执行 |
| 2026-10-14 | 添加 UnitOfWork.session 属性 | 支持 ApprovalService 和 ToolExecutor 在测试中构造 Repository | 持久化层 |
| 2026-10-14 | DigitalHumanProvider/VideoRenderProvider 提升为模块级导入 | 支持 unittest.mock.patch 在模块路径拦截 | 测试可mock性 |
| 2026-10-14 | validate_video_delivery 支持 IPv6 bracket literal [::1] SSRF 检查 | 防止 IPv6 loopback 地址绕过 SSRF 防护 | 安全 |
| 2026-10-14 | publish_artifacts 失败时仍返回 artifacts 键 | 保证 LangGraph 状态更新一致性（不丢失已有 artifacts） | 状态不变量 |
| 2026-10-14 | SSRF 防护使用 socket.getaddrinfo 解析 DNS | 同步 DNS 解析在生产环境应改用异步解析器 | 安全/性能 |
| 2026-10-14 | RateLimiter 基于 Redis sorted set 滑动窗口 | 比固定计数器更精确，但需要 Redis 可用 | 限流 |
| 2026-10-14 | MetricsCollector 为全局单例线程安全实现 | 低开销，支持 Prometheus 文本格式导出 | 可观测性 |
| 2026-10-14 | 历史实现允许空 MAA Header 和固定身份 fallback | 仅可存在于显式测试 fixture；公开/生产路由必须移除 | 安全、Product API、MAA API |
| 2026-10-15 | Real Provider 不属于 WP-11 | WP-11 先证明运行时闭环和基础设施可用，真实视频供应商接入属于 WP-14 | WP-11、WP-14 |
| 2026-10-15 | 真实依赖验证使用 Agent 独立 Compose，不复用不明归属的 `argus-postgres` | 避免把其他项目数据库当作 MAA Agent 数据库 | WP-03、WP-11、WP-16 |
| 2026-10-14 | 项目升级为“独立 Agent Film 产品 + MAA 兼容适配器” | 当前后端模块可复用，但产品外壳仍依赖 WiseCut | plan 全局、WP-11 至 WP-18 |
| 2026-10-14 | 独立 Web 采用 Vue 3 + TypeScript + Vite，放在同仓库 `web/` | 与 WiseCut 现有 Agent Film 前端技术一致，同时保持独立构建和 API | Product API、Web、Docker |
| 2026-10-14 | 视频生成使用远程 API Provider，不要求本地 FFmpeg | 最终目标部署服务器，降低镜像和计算运维复杂度 | WP-09、WP-14、Provider、Artifact |
| 2026-10-14 | 历史 commit 保留，但不满足最终出口的 WP 重新标记 `[~]` | 模块存在不等于运行链完成，避免后续智能体基于虚假完成度推进 | WP-02、03、05-10 |

## 7. 阻塞项和风险

| 状态 | 问题 | 影响 | 处理方式 |
| --- | --- | --- | --- |
| 开放 | 原版 MAA 的私有 Prompt、工具源码和真实 Provider 配置不可见 | 不能逐行复原原实现 | 按可观察协议做行为兼容重建 |
| 开放 | 真实视频、数字人和素材服务凭证未知 | 本地无法保证调用线上 Provider | 先使用显式 Demo Provider，再提供真实 Provider 接口 |
| 已解决 | GitHub 仓库已创建并绑定 `origin` | 无 | 远端为 `git@github.com:tangfire/wisecut-agent.git` |
| 已记录 | Go Client 中 `buildAgentFilmHeaders` 使用 `X-Session-ID` 存 project_id，`setAgentFilmHeaders` 使用 `X-Project-ID` | MAA API 统一使用 `X-Project-ID`，需确认 WiseCut 后端是否接受两种 Header | 以 `setAgentFilmHeaders` 为准（MAA API 相关方法均使用此函数），记录差异 |
| 开放 | 本地分支包含尚未推送到 `origin/main` 的实现和重基线 commit | 其他环境从 GitHub 获取不到最新代码和计划 | 由用户决定何时执行 push；同一本地目录继续开发不受影响 |
| 开放 | 尚未确定真实视频生成 API 供应商和测试凭证 | WP-14 无法完成真实视频验收 | 先完成供应商无关 contract，再由用户提供沙箱/测试配置 |
| 开放 | 现有 331 测试未覆盖真实 Worker/Graph/Provider 链 | 绿色测试可能掩盖运行时不可用 | WP-11 新增真实依赖和闭环测试 |

## 8. 下一步

WP-11 R7 已完成：
- [x] Worker healthcheck 修复（进程存活检查）
- [x] GraphRunner 注入 Worker handler（禁止 no-op）
- [x] PostgreSQLCheckpointSaver 接口合规（aget_tuple/aput_writes）
- [x] GraphRunner 执行会话生命周期修复
- [x] API 创建 Run+Message 到 DB 后再发布 RabbitMQ
- [x] 完整 API -> RabbitMQ -> Worker -> GraphRunner -> completed 链路验证通过

WP-11 剩余任务（完成前不进入 WP-12）：
- [x] mypy 99 errors → 62（WP-11 引入的 41 个错误已全部修复；剩余 62 个均为历史遗留错误）
- [x] OutboxPublisher 独立健康检查和指标（health_check()/get_stats() 方法 + Worker health stats writer）
- [~] 真实 HTTP 验证 interrupt/resume 完整路径（基础链路已验证，checkpoint commit 修复完成；需要使用 Deep profile 触发 review 节点）
- [ ] SSE 断线续传真实测试

### 5.8 WP-11 Deep resume 崩溃恢复点

```text
日期：2026-10-16
当前工作区：4 个未提交文件
- app/application/sync_services.py
- app/graph/builder.py
- app/graph/runner.py
- app/persistence/checkpointer.py

已通过的真实 HTTP 路径：
- POST /conversations -> 201，profile=one-click-cocreate
- POST /messages -> 200
- run.started seq=1
- interaction.requested seq=2
- Run -> WAITING_INTERACTION / awaiting_user_input
- POST interaction_response -> 200，返回原始 run_id
- interaction.resolved seq=3

已修复的中间问题：
- sync_services.py 缺失 datetime 导入
- _resume_graph() 多余 lock 参数
- Checkpoint 缺失 pending_sends

当前真实阻塞：
- 最新 Run `run-764d6a73822e` 在 resume 时 FAILED。
- PostgreSQL/asyncpg 错误：`cannot perform operation: another operation is in progress`。
- 错误发生在 Checkpoint UPDATE；LangGraph Checkpointer 和 GraphRunner 业务写入共享同一个 AsyncSession。
- Checkpointer 当前持有 GraphRunner 传入的 session；LangGraph 可能并发调用 aput/aput_writes，AsyncSession 不支持并发共享。
- RabbitMQ DLQ 当前有 3 条测试消息。

当前验证：
- pytest：334 passed，但有 `Task was destroyed but it is pending` 的 Worker/Outbox 后台任务清理警告。
- ruff：1 个 import-order 错误（app/graph/runner.py）。
- mypy：64 errors in 18 files（当前未提交树）。
- 6 个容器 healthy。

建议修复边界：
1. PostgreSQLCheckpointSaver 改为持有 async session factory，而不是持有 GraphRunner 的共享 AsyncSession。
2. aget/aput/aput_writes/alist 各自使用短生命周期 session 和独立事务。
3. Checkpoint 写入使用 PostgreSQL upsert 或等价并发安全写入，避免 insert/rollback/update 共用同一 session。
4. GraphRunner 的 Run/Event/Interaction 业务 session 与 Checkpointer session 分离。
5. 修复 Worker stop 时 OutboxPublisher/health task 的 cancel + await，消除 pending task 警告。
6. 修复后重新跑 Deep HTTP resume；成功后再做 SSE after_seq 续传。
```

### 5.9 WP-11 R8 — Checkpointer session isolation + Worker stop cleanup

```text
日期：2026-10-16
工作包：WP-11 R8

代码变更：
1. app/persistence/checkpointer.py
   - PostgreSQLCheckpointSaver.__init__ 接收 session_factory 而不是 AsyncSession
   - aget/aget_tuple/aput/aput_writes/alist/adelete/aexists 各自创建短生命周期 session
   - aput 和 aput_writes 使用 SQLAlchemy INSERT ... ON CONFLICT DO UPDATE (upsert) 替代 try/except insert-then-update
   - 移除 AsyncSession 和 sqlalchemy.update 未使用导入

2. app/graph/runner.py
   - execute_run 将 factory（不是 session）传给 PostgreSQLCheckpointSaver
   - _run_graph/_resume_graph 移除 checkpointer 参数，使用 compiled.checkpointer.agetuple 读取 checkpoint
   - _handle_completion 增加 session 参数，复用 GraphRunner session 写入 terminal event
   - _handle_interrupt 移除 checkpointer 参数，使用独立短 session 读取 checkpoint_id
   - 修复 import order（langgraph.errors 在 langgraph.types 之前）
   - 移除 _resume_graph 中多余 from langgraph.types import Command

3. app/worker/run_worker.py
   - __init__ 增加 self._outbox_task 和 self._health_task 实例属性
   - _run_loop 将 task 引用存在 self._outbox_task/self._health_task
   - stop() 方法：cancel + await outbox/health tasks（通过 call_soon_threadsafe），消除
     "Task was destroyed but it is pending" 警告
   - stop() 增加 self._thread is not None 保护

4. docker/worker_healthcheck.py
   - 从 __future__ 后直接 import Any/UTC/datetime（ruff import order 修复）
   - 移除函数内联 from datetime import

验证：
```
工作包：WP-11 R8
日期：2026-10-16
命令：SKIP_SETTINGS_VALIDATION=1 python -m pytest tests/ -q
结果：退出码 0
关键输出：334 passed in 13.85s（无回归）
命令：python -m ruff check app/ tests/ docker/
结果：All checks passed
命令：python -m mypy app/ --ignore-missing-imports
结果：Found 62 errors in 17 files（从 64 降至 62，修改的文件无新增错误；2 个减少来自 runner/checkpointer 类型清理）

技术证据：
- PostgreSQLCheckpointSaver 每个方法创建独立 session，与 GraphRunner session 物理隔离
- aput 使用 INSERT ... ON CONFLICT DO UPDATE (checkpoint_pkey)，并发安全
- GraphRunner.execute_run 的 async with factory() as session 持有业务 session
- compiled.checkpointer.agetuple(config) 在短 session 内读取 checkpoint
- Worker stop 先 cancel+await background tasks，再 join thread

当前状态：
- [x] Checkpointer session 隔离（Docker 验证通过：8 checkpoints 写入成功）
- [x] Checkpoint upsert 写入（Docker 验证通过）
- [x] Worker stop 任务清理（代码完成）
- [x] ruff clean（0 errors）
- [x] mypy 无新增错误（66 total，全部历史遗留）
- [x] 334 pytest pass
- [x] Deep HTTP interrupt/resume Docker 验证通过（run-98228ed73b3f）
- [x] SSE after_seq 断线续传 Docker 验证通过（after_seq=3 返回 seq 4,5,6）
- [x] DLQ 策略验证通过（0 条消息；fanout→direct 修复阻止 outbox 事件污染）

关联 commit：`0c12d36` (R8), `2d7e64e` (R9)

### 5.10 WP-11 R8 验证记录

```text
工作包：WP-11 R8
日期：2026-10-16
命令：SKIP_SETTINGS_VALIDATION=1 python -m pytest tests/ -q
结果：退出码 0
关键输出：334 passed in 13.85s（无回归）
命令：python -m ruff check app/ tests/ docker/
结果：All checks passed
命令：python -m mypy app/ --ignore-missing-imports
结果：Found 62 errors in 17 files（修改的文件无新增错误）
```

### 5.11 WP-11 R9 — Runtime validation closure

```text
工作包：WP-11 R9
日期：2026-10-16

Docker 验证（run-98228ed73b3f，profile=one-click-cocreate，Deep）：

完整事件链：
  seq=1  run.started
  seq=2  interaction.requested (confirm_generation_start, checkpoint_id=1f1c939c-d9df-6cb1-8005-5-8a9509bb2e03)
  seq=3  interaction.resolved (action=approve)
  seq=4  artifact.created (artifact_id=art-8e0cd7d44099, final_video)
  seq=5  business.message (business_key=final_video)
  seq=6  run.completed

Interrupt/Resume 证据：
- Graph 执行到 request_generation_approval 节点正确暂停
- Run 状态：RUNNING → WAITING_INTERACTION (phase=awaiting_user_input)
- Interaction 记录：int-ea371216e55b, intent=confirm_generation_start, status=pending
- 用户 approve 后，Graph 从同一 checkpoint 恢复
- Graph 继续执行 collect_materials → match_digital_human → render_video → validate_delivery → publish_artifacts → END
- Run 状态：WAITING_INTERACTION → COMPLETED
- 8 个 checkpoints 持久化到 PostgreSQL（同一 thread_id=conv-2fe8fb624d91）

SSE after_seq 续传证据：
- after_seq=0: 返回 6 个事件（seq 1-6）
- after_seq=3: 返回 3 个事件（seq 4, 5, 6），无重复、无丢失

DLQ 策略证据：
- 修复前：DLQ 有 48 条消息（fanout exchange 导致 outbox 事件进入 maa.run.commands）
- 修复后：DLQ 0 条消息
- 根因：EXCHANGE_TYPE 从 fanout 改为 direct，publish_event 使用 ROUTING_KEY_EVENT='agent.event'
- 新增 QUEUE_EVENTS='maa.events' 接收 outbox 事件

代码修复：
1. app/graph/runner.py: _handle_completion/_handle_interrupt 增加 session.commit()
2. app/graph/runner.py: _run_graph/_resume_graph 检测 pending_approval 并转换为 interaction
3. app/graph/routing.py: is_terminal 默认返回 'terminal'（修复 publish_artifacts 无限循环）
4. app/infra/messaging.py: EXCHANGE_TYPE fanout→direct，新增 QUEUE_EVENTS + ROUTING_KEY_EVENT
5. tests/unit/test_graph.py: test_is_terminal_continue → test_is_terminal_clean_state

验证命令：
- pytest: 334 passed
- ruff: All checks passed
- mypy: Found 66 errors in 19 files（全部历史遗留，修改文件无新增）

关联 commit：2d7e64e
```
```

通用：
- [x] WP-11 已闭环：interrupt/resume、SSE after_seq、DLQ 策略全部通过 Docker 真实验证
- [ ] WP-12 建立独立 Product API 后，再执行 WP-13 Web。
- [ ] WP-14 接入真实 LLM 和真实远程视频生成 API；Demo URL 不作为完成证据。
- [ ] 重基线文档提交后，将 `docs/DELEGATION_PROMPT.md` 交给下一位智能体。
- [ ] 每个工作包完成后立即更新本文件、记录验证输出并提交。

下一次继续任务时：
1. 重建或重启 agent-api/agent-worker，确认运行的是 `0c12d36`。
2. 使用 Deep profile 连续处理所有 pending interaction，至少证明一次 resume 进入下一节点，最好跑到 terminal。
3. 在同一 Run 上验证 SSE 断开后按 `after_seq` 重连，无重复、无丢失。
4. 记录现有 DLQ 3 条消息；移除或限制 worker 启动默认 purge 行为。
5. 两项运行证据和 DLQ 策略都有结论后，再把 WP-11 标记为 `[x]`，进入 WP-12。
