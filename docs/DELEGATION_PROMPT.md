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

目标不是写一个简化聊天 Demo，而是按 plan.md 完成可接入 WiseCut 的最终 MAA Agent 平台。核心技术路线是 FastAPI + LangChain + LangGraph + PostgreSQL + RabbitMQ + Redis + Docker。

请从 execution.md 当前工作包开始，严格按工作包顺序推进。当前应先完成 WP-00 的初始基线提交，然后进入 WP-01 MAA 协议冻结。不要跳过 MAA wire contract、OpenAPI、JSON Schema、fixture 和契约测试，不能直接先写 Agent Film 业务节点。

开发要求：
- 先检查现有文件和 Git 状态，再给出本次工作包的简短执行说明。
- 修改前先核对 D:\dx\wisecut、D:\dx\wise-cut 和 D:\dx\oss-admin 中的真实 Client、Service、Consumer 和前端类型。
- 不猜测协议字段；不确定内容记录到 execution.md 的风险表。
- 每完成一个可验证工作包，运行真实测试，更新 execution.md，记录命令和关键输出，然后创建一个聚焦的 Git commit。
- 只有实现、测试、文档、验证和 commit 全部完成，才能把任务标为 [x]。
- 不要提交 .env、Token、密码、数据库、日志、上传文件或模型缓存。
- 未经我明确要求，不要 push 到远端 GitHub。

本轮开始时请先完成 WP-00：检查并提交当前项目文档基线。提交后继续执行 WP-01；如果 WP-01 不能在当前工作轮次完成，请停在真实完成点，更新 execution.md，明确记录已完成、未完成、测试输出、commit 和下一步，而不是虚报完成。
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
