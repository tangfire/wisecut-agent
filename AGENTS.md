# wisecut-agent 协作开发规则

本文件是交给其他编程智能体的仓库级执行规则。最终架构和验收标准以 [plan.md](./plan.md) 为准，进度和证据以 [execution.md](./execution.md) 为准。

## 开始任何工作前

1. 阅读 `README.md`、`plan.md`、`execution.md`。
2. 阅读 [正式重基线审计](./docs/REBASELINE_2026-10-14.md)、[MAA 协议来源地图](./docs/MAA_CONTRACT_SOURCE_MAP.md) 和 [WiseCut 联调指南](./docs/WISECUT_INTEGRATION.md)。
3. 查看 `execution.md` 的当前工作包、阻塞项和最近提交。
4. 确认本次修改对应哪个 `WP-*`，不要跨越工作包随意实现业务节点。
5. 任何协议、状态、队列或数据库语义变更，先更新 `plan.md` 和 `execution.md` 的决策记录。

## 实现要求

- 使用 Python、FastAPI、LangChain、LangGraph、PostgreSQL、RabbitMQ、Redis 和对象存储的既定架构。
- 项目最终形态是“独立 Vue Agent Film 产品 + MAA Compatibility API”，两套入口共用领域内核但鉴权和路由分离。
- MAA 外部 HTTP/SSE 协议优先兼容当前 WiseCut Go Client，不凭空设计另一套协议。
- API 进程不执行长时间 Agent 工作流；Run 必须通过可靠队列交给 Worker。
- LangGraph Checkpoint、MAA Run、Event seq 和 Artifact 必须保存明确映射。
- 所有外部副作用必须有幂等键、超时、取消、重试上限和审计记录。
- 所有交互、审批、工具执行和状态迁移必须产生可追踪事件。
- Demo Provider 和真实 Provider 必须通过同一接口切换，生产配置禁止加载 Demo Provider。
- 不直接修改 WiseCut MySQL；Agent 通过 MAA 事件和 Artifact 与 Go 后端交互。
- 不把 Redis 当作不可丢失任务队列；可靠 Run command 使用 RabbitMQ。
- 不把模型原始输出未经校验地当作业务事实，结构化输出必须经过 Schema 校验。
- 真实视频通过远程视频生成 API Provider 完成；Provider 必须支持异步任务、Webhook/轮询、取消、超时和幂等回调。
- 当前工作包是 WP-11。WP-11 未闭环前不得开始前端，以免在 stub/no-op 运行链上继续开发。

## 安全要求

- 禁止提交 `.env`、API Key、Token、密码、数据库文件、上传文件、日志和模型缓存。
- 所有外部 URL 必须经过 SSRF、DNS、内网地址、协议和大小限制检查。
- 工具权限遵循 L0/L1/L2/L3 风险等级；L3 必须审批和审计。
- 日志和前端事件不得泄露 Secret、原始 Authorization、内部路径或未脱敏工具参数。

## 验证和提交要求

每个工作包必须完成：

1. 代码、测试、配置和文档同步。
2. 运行与本次修改相关的真实验证命令。
3. 把命令、退出码、关键输出写入 `execution.md`。
4. 更新任务勾选状态和 commit 字段。
5. 使用一个聚焦的 Git commit 提交。

不能因为单元测试通过就声称 MAA 联调通过。涉及协议、SSE、队列、数据库恢复或四仓库联调时，必须运行对应真实依赖和真实 HTTP 测试。

## 不确定时的处理

- 先查现有 Go Client、后端文档和前端类型/组件。
- 如果仍无法确定，记录到 `execution.md` 的风险表，不要静默猜测协议字段。
- 不为了让测试通过而放宽状态不变量、跳过鉴权或隐藏失败。
- 不把临时 fixture、Demo 分支或 TODO 当成最终完成状态。

## 完成定义

工作包只有在实现、验证、文档和提交都完成后，才允许将 `execution.md` 中对应状态改为 `[x]`。没有验证证据的任务只能保持 `[~]`。
