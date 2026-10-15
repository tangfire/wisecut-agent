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

当前是 WP-11 R6 崩溃恢复点：
- 已提交 `40aa7ac`：全量 Ruff clean、334 个 pytest、mypy 降到 79。
- 已提交 `4c02ffb`：隔离开发 Compose 和 Dockerfile 基线。
- 已提交 `c9d1dc4`：记录崩溃恢复点。
- 当前工作区仍有 12 个未提交文件，涉及 `app/main.py`、`app/persistence/engine.py`、`compose.yaml`、`docker/Dockerfile`、`requirements.txt` 和测试文件。
- 严禁 reset、checkout、clean 或覆盖这些未提交改动。先逐个审阅 diff，再决定拆分提交。
- 当前验证基线：`pytest tests -q` 为 334 passed，`python -m ruff check app tests` 通过，`python -m mypy app --ignore-missing-imports` 为 79 errors，`docker-compose -f compose.yaml config --quiet` 通过。
- 下一步是启动隔离 PostgreSQL、RabbitMQ、Redis、MinIO，验证 OutboxPublisher、Worker、GraphRunner、SSE 和恢复链路；Real Provider 留到 WP-14。
- R6 最新诊断：不要直接把 async SQLAlchemy 全量迁移到同步 psycopg2。当前 Compose 把 `ENABLE_WORKER=true` 放在 Uvicorn API 容器中，API 主事件循环和 Worker 线程事件循环共享全局 AsyncEngine/asyncpg pool，这是 `POST /conversations` 返回 500 的首要嫌疑。优先把 API、Worker、OutboxPublisher 拆成独立进程/Compose 服务，各自拥有自己的事件循环和 DB pool，然后重新验证真实 POST。
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
