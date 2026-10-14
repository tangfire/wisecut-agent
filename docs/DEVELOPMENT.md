# Agent 开发执行流程

本文说明其他编程智能体如何在本仓库中持续开发，避免只写代码而丢失协议、进度和验证证据。

## 1. 接手任务

```powershell
cd D:\dx\wisecut-agent
Get-Content README.md
Get-Content plan.md
Get-Content execution.md
Get-Content AGENTS.md
Get-Content docs\MAA_CONTRACT_SOURCE_MAP.md
Get-Content docs\WISECUT_INTEGRATION.md
Get-Content docs\REBASELINE_2026-10-14.md
git status --short --branch
git log --oneline -10
```

先确认 `execution.md` 当前工作包，不要从头重复已完成的工作。

## 2. 开发循环

```text
读取 plan.md 约束
  ↓
读取 execution.md 当前工作包
  ↓
读取对应 Go Client/前端/后端来源代码
  ↓
实现一个可验证的垂直切片
  ↓
写测试和 fixture
  ↓
启动真实依赖
  ↓
运行测试与契约验证
  ↓
更新 execution.md
  ↓
提交一个聚焦 commit
```

一个工作包可以有多个 commit，但每个 commit 要能说明自身状态；最后一个 commit 才把工作包标记为 `[x]`。

## 3. 每次开发前自检

- 当前工作包是否允许修改这个目录？
- 是否会改变 MAA wire contract？
- 是否会改变 Event type、payload、seq 或 terminal 语义？
- 是否会改变数据库状态迁移或幂等约束？
- 是否需要同时修改 OpenAPI、JSON Schema、fixture 和测试？
- 是否涉及 Go 后端、Go Consumer 或前端联调？
- 是否需要真实 PostgreSQL、RabbitMQ、Redis、MinIO 或模型 Provider？
- 是否会引入 Secret、用户数据或内部路径到日志？

## 4. 验证层级

### 单元验证

验证纯函数、状态路由、Schema、Prompt 组装、幂等键和错误映射。

### 契约验证

启动 MAA API，使用当前 `wisecut/internal/third_party/maa/agent/` 客户端或等价真实 HTTP 请求验证响应和 SSE。

### 集成验证

使用 Docker 中的 PostgreSQL、RabbitMQ、Redis 和对象存储验证事务、Outbox、Worker、Checkpoint、重试和恢复。

### 端到端验证

启动 WiseCut API、`agent_film_consumer`、用户端和运营后台，从页面操作到 MySQL 业务落库验证完整链路。

## 5. 工作包完成模板

在 `execution.md` 中更新：

```text
状态：[x]
完成内容：...
验证命令：...
验证结果：...
关键输出：...
涉及仓库：...
关联 commit：...
遗留风险：...
```

如果有失败测试、未完成 Provider 或暂时的 Demo 行为，保持 `[~]` 并记录原因，不要提前勾选。

## 6. Git 提交

```powershell
git diff --check
git status --short
git add <相关文件>
git diff --cached --check
git commit -m "<conventional commit message>"
git status --short --branch
```

提交前确认没有 `.env`、运行数据、抓包、数据库、日志或模型文件。

## 7. 交接给下一位 Agent

交接内容必须包含：

- 当前工作包和完成百分比只是辅助信息，最终以勾选任务为准。
- 已完成的任务和对应 commit。
- 最近一次真实验证命令和输出。
- 当前失败、阻塞和风险。
- 下一步最小可执行任务。
- 不应重复修改的文件和已冻结的协议。
