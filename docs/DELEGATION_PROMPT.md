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

当前是 WP-11 R7+ 收口点，不是崩溃恢复点：
- 已提交 `40aa7ac`：全量 Ruff clean、334 个 pytest、mypy 降到 79。
- 已提交 `4c02ffb`：隔离开发 Compose 和 Dockerfile 基线。
- 已提交 `1eeb5ea`、`6a997fd`：Docker 稳定性、readiness 和依赖调整。
- 已提交 `d186dbb`、`9bef3c9`、`c9d1dc4`、`94c3317`：崩溃恢复、拆进程架构和执行记录。
- 已提交 `c7fc2d9`：Worker healthcheck、GraphRunner 注入、CheckpointSaver 合规和主链验证。
- 已提交 `aef4ede`：mypy 41 个 WP-11 引入错误修复、OutboxPublisher 健康检查、checkpoint commit 修复和 content dict 序列化。
- 当前 API 与 Worker 已拆成两个容器，且两个容器 healthy；API 的 `ENABLE_WORKER=false`，Worker 注入真实 GraphRunner。
- `POST /conversations` 已真实返回 `201 Created`，`POST /messages` 已返回 `200` 并发布 Run command。
- 主链已验证：API -> RabbitMQ -> Worker -> GraphRunner -> LangGraph -> completed，并确认 8 个 checkpoint 持久化。
- 当前工作区有 4 个未提交文件：`app/application/sync_services.py`、`app/graph/builder.py`、`app/graph/runner.py`、`app/persistence/checkpointer.py`。这些是 interrupt/resume 收口改动，严禁 reset、checkout、clean 或覆盖；先审阅 diff。
- Deep profile 已真实产生 `interaction.requested`，HTTP 回答已产生 `interaction.resolved` 并返回原始 run_id。
- 已修复 `_resume_graph(lock=...)` 和 Checkpoint `pending_sends` 问题。
- 当前 resume 失败于 Checkpoint UPDATE：`asyncpg InterfaceError: another operation is in progress`。根因边界是 Checkpointer 和 GraphRunner 业务写入共享同一个 AsyncSession。
- 当前验证基线：`pytest tests -q` 为 334 passed，但有 Worker/Outbox pending task 清理警告；ruff 有 1 个 runner import-order 错误；mypy 当前未提交树为 64 errors；6 个容器 healthy；DLQ 有 3 条测试消息。
- 当前剩余是 Checkpointer session 隔离、真实 HTTP resume、SSE 断线续传和 DLQ 排查；Real Provider 留到 WP-14。
- Real Provider 留到 WP-14，不要在 WP-11 中实现。
- 不要直接把全项目迁移到同步 psycopg2；先修 Worker healthcheck 和 GraphRunner 注入，再验证真实消息链。

本次收口任务必须按以下顺序：
1. 审阅上述 4 个未提交文件，保留已经修好的 datetime、run_id、lock 和 pending_sends 逻辑。
2. 将 PostgreSQLCheckpointSaver 改为持有 async session factory；每个 aget/aput/aput_writes/alist 使用自己的短 session/事务，不和 GraphRunner 业务 session 共用。
3. 使用 PostgreSQL upsert 或等价并发安全写入 Checkpoint，避免同一 session 上 insert/rollback/update。
4. 修复 Worker stop 时 OutboxPublisher 和 health task 的 cancel + await，消除 `Task was destroyed but it is pending`。
5. 修复 runner.py 的 Ruff import-order 错误，运行 pytest、ruff、mypy。
6. 使用 Deep profile 重新执行真实 HTTP interaction response，确认同一 checkpoint 恢复并进入下一 interaction 或 terminal state。
7. 断开 SSE 后使用 `after_seq` 重连，确认事件不重复、不丢失。
8. 检查 DLQ 3 条测试消息并记录原因，不要无证据清空。
9. 更新 execution.md、记录数据库/Event/Checkpoint/Run 证据并提交聚焦 commit。
10. interrupt/resume 和 SSE 两项都有真实证据后，才把 WP-11 标记为 `[x]`，然后进入 WP-12。
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
