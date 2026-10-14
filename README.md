# WiseCut MAA Agent

这是一个独立的 MAA Agent 服务，用于复现 WiseCut 智能成片场景中的 Agent 平台能力。

项目目标不是恢复原 MAA 的私有源码，而是依据当前 WiseCut 后端已经暴露的 HTTP、SSE、交互卡片、审批、Artifact 和业务事件协议，重新实现一套可以本地运行、可以接入三个 WiseCut 仓库、并具备生产化基础能力的 Agent 服务。

核心技术路线：

- LangChain：模型、工具调用、结构化输出、Prompt 和 Provider 适配
- LangGraph：有状态工作流、Checkpoint、Interrupt/Resume、Human-in-the-loop 和流式执行
- FastAPI：MAA HTTP API、鉴权、健康检查和管理接口
- PostgreSQL：会话、Run、事件、交互、Artifact 和审计数据
- RabbitMQ：可靠 Run 任务、重试队列和死信队列
- Redis：事件通知、分布式锁、限流和短期缓存
- Docker Compose：本地四仓库联调

当前阶段：最终版架构和实施计划已经冻结，后续编码以 [plan.md](./plan.md) 为实施基线，执行状态记录在 [execution.md](./execution.md)。

交接文档：

- [AGENTS.md](./AGENTS.md)：其他编程智能体的执行规则
- [docs/DEVELOPMENT.md](./docs/DEVELOPMENT.md)：开发、验证、提交和交接流程
- [docs/MAA_CONTRACT_SOURCE_MAP.md](./docs/MAA_CONTRACT_SOURCE_MAP.md)：现有 WiseCut 协议来源地图
- [docs/WISECUT_INTEGRATION.md](./docs/WISECUT_INTEGRATION.md)：四仓库联调和 Go Consumer 说明
- [docs/DELEGATION_PROMPT.md](./docs/DELEGATION_PROMPT.md)：交给其他编程智能体的启动指令

计划中的协作目录：

```text
D:\dx\
├── wisecut-agent   # 当前仓库，MAA Agent 服务
├── wisecut         # Go 业务后端
├── wise-cut        # 用户端前端
└── oss-admin       # 运营后台
```

本项目完成后，WiseCut 后端的 `[agent_film]` 配置将指向本地 `maa-agent` 容器，前端可以真实走完会话创建、流式进度、用户确认、工具调用、视频产物和失败恢复链路。
