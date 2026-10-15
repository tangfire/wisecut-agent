# 交给其他编程智能体的启动指令

把下面这段话发送给运行在 `D:\dx\wisecut-agent` 目录中的编程智能体即可开始执行：

```text
你现在负责开发 D:\dx\wisecut-agent，这是一个复现 WiseCut MAA Agent 的独立项目。

请先完整阅读并遵守：
1. AGENTS.md
2. plan.md
3. execution.md
4. docs/DEVELOPMENT.md
5. docs/MAA_CONTRACT_SOURCE_MAP.md
6. docs/WISECUT_INTEGRATION.md
7. docs/REBASELINE_2026-10-14.md

目标不是写一个简化聊天 Demo，而是按 plan.md 完成“独立 Agent Film 产品 + WiseCut MAA 兼容适配器”。核心技术路线是 Vue 3 + FastAPI + LangChain + LangGraph + PostgreSQL + RabbitMQ + Redis + 对象存储 + 远程视频生成 API。

请从 execution.md 当前工作包开始，严格按工作包顺序推进。2026-10-14 已完成正式重基线，当前工作包是 WP-11 运行时闭环与质量纠偏。不要重复执行 WP-00 至 WP-10，也不要因为历史 checklist 中存在 `[x]` 就忽略重基线后重新打开的缺口。

开发要求：
- 先检查现有文件和 Git 状态，再给出本次工作包的简短执行说明。
- 修改前先核对 D:\dx\wisecut、D:\dx\wise-cut 和 D:\dx\oss-admin 中的真实 Client、Service、Consumer 和前端类型。
- 不猜测协议字段；不确定内容记录到 execution.md 的风险表。
- 每完成一个可验证工作包，运行真实测试，更新 execution.md，记录命令和关键输出，然后创建一个聚焦的 Git commit。
- 只有实现、测试、文档、验证和 commit 全部完成，才能把任务标为 [x]。
- 不要提交 .env、Token、密码、数据库、日志、上传文件或模型缓存。
- 未经我明确要求，不要 push 到远端 GitHub。

本轮开始时请先检查 Git 状态，阅读重基线审计，并确认当前为 WP-11。先修复 Worker no-op、GraphRunner stub、interrupt/resume、真实 Graph 事件链、依赖锁、ruff、mypy、RabbitMQ 端口和权限接入。WP-11 未完成前不要开始独立 Vue 前端。不能在当前工作轮次完成时，请停在真实完成点，更新 execution.md，明确记录已完成、未完成、测试输出、commit 和下一步，而不是虚报完成。

当前是 WP-11 拆进程后的崩溃恢复点：
- 已提交 `40aa7ac`：全量 Ruff clean、334 个 pytest、mypy 降到 79。
- 已提交 `4c02ffb`：隔离开发 Compose 和 Dockerfile 基线。
- 已提交 `1eeb5ea`、`6a997fd`：Docker 稳定性、readiness 和依赖调整。
- 已提交 `d186dbb`、`9bef3c9`、`c9d1dc4`、`94c3317`：崩溃恢复、拆进程架构和执行记录。
- 当前 API 与 Worker 已拆成两个容器；API 的 `ENABLE_WORKER=false`，Worker 独立运行。
- `POST /conversations` 已真实返回 `201 Created`，`POST /messages` 已返回 `200` 并发布 Run command。
- 当前 `wisecut-agent-worker` 进程在运行，但容器被错误的 API HTTP healthcheck 标记为 unhealthy。
- 当前 `docker/worker_entrypoint.py` 创建的是 `RunWorker()`，没有注入 `GraphRunner().execute_run`，所以可能仍使用 `_default_handler`，这是当前第一优先级问题。
- RabbitMQ `maa.run.commands` 有 consumer，但消息进入 DLQ；完整 API -> Outbox -> RabbitMQ -> Worker -> Graph -> SSE 链路尚未通过。
- 当前工作区仍有 11 个已修改文件和 3 个未跟踪文件，包含 Compose、Docker、API、Worker、同步数据库适配和测试调整。严禁 `reset`、`checkout`、`clean` 或覆盖这些改动；先逐个审阅 diff。
- 当前验证基线：`pytest tests -q` 为 334 passed，`python -m ruff check app tests` 通过，`python -m mypy app --ignore-missing-imports` 为 79 errors，Compose 配置解析通过。
- Real Provider 留到 WP-14，不要在 WP-11 中实现。
- 不要直接把全项目迁移到同步 psycopg2；先修 Worker healthcheck 和 GraphRunner 注入，再验证真实消息链。

本次恢复任务必须按以下顺序：
1. 读取并审阅所有未提交 diff，确认不丢失智能体已有工作。
2. 将 agent-worker 的 healthcheck 改为进程存活或 Worker 心跳检查，不访问 `localhost:10728/health`。
3. 在 `docker/worker_entrypoint.py` 注入 `GraphRunner().execute_run`，禁止使用默认 no-op handler。
4. 明确 OutboxPublisher 是独立服务还是 Worker 内部服务，并保证有独立生命周期、重试和日志。
5. 隔离/清理旧 DLQ 测试消息后，重新发送单条测试消息。
6. 验证 Run 状态、事件落库、Graph 执行、SSE 和 terminal event。
7. 修复后运行 pytest、ruff、mypy 和 Compose/容器验证，更新 execution.md 并提交聚焦 commit。
8. WP-11 未有完整链路证据时，不得标记 `[x]`，也不得进入 WP-12。
```

## 智能体每轮结束时必须返回

```text
本轮工作包：WP-XX
完成任务：...
未完成任务：...
验证命令和关键输出：...
修改文件：...
Commit：...
当前阻塞或风险：...
下一步：...
```

如果智能体没有先读取 `plan.md` 和 `execution.md`，不要让它直接开始修改业务代码。
