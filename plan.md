# WiseCut Agent Film 独立产品最终实施计划

## 1. 目标定义

### 1.1 最终目标

在当前 `D:\dx\wisecut`、`D:\dx\wise-cut` 和 `D:\dx\oss-admin` 三个仓库之外，建设一个可以独立运行的 `wisecut-agent` Agent Film 产品，同时保留对 WiseCut MAA HTTP/SSE 协议的兼容能力。

最终系统采用“双入口、单内核”架构：

```text
独立产品入口：Standalone Web -> Product API -> Agent Runtime
WiseCut 兼容入口：WiseCut Go -> MAA Compatibility API -> Agent Runtime
```

最终系统必须满足：

1. 提供独立 Vue Web 应用，支持登录、项目管理、素材上传、Agent 交互、分镜审核、视频预览和下载。
2. 提供独立 Product API，不要求调用方理解 WiseCut 的 MAA Header 和内部项目模型。
3. 对 WiseCut Go 后端继续提供兼容的 MAA HTTP API。
4. 对独立 Web 和 WiseCut Consumer 提供可恢复的 SSE 事件流。
5. 使用 LangChain 完成真实模型调用、工具调用和结构化输出适配。
6. 使用 LangGraph 完成有状态、多阶段、可暂停、可恢复的 Agent 工作流。
7. 支持 Quick 和 Deep 两种 Agent Profile。
8. 支持用户交互、工具审批、取消、重试、超时和断点恢复。
9. 支持商品信息采集、脚本规划、分镜审核、素材处理、数字人匹配和视频渲染等智能成片流程。
10. 至少接入一个真实远程视频生成 API Provider，生成可探测、可播放、可下载的视频产物。
11. 支持本地 Demo Provider 和真实 Provider，但两者使用同一套业务接口且生产环境禁止 Demo Provider。
12. 支持 Docker Compose 本地完整运行，并具备迁移到生产环境的部署边界。
13. 让一次 Agent Run 的每个关键状态、事件、工具调用和产物都可追踪、可重放、可审计。

### 1.2 复现边界

本项目复现的是外部行为、业务状态和系统能力，不声称恢复原 MAA 的私有源码、原始 Prompt、原始模型参数、内部知识库、线上素材库或第三方账号配置。

复现优先级：

```text
MAA API / SSE 协议
    > Run / Session / Event 状态语义
    > interaction / approval 行为
    > Agent Film 业务流程
    > 工具输入输出和副作用
    > Prompt 表达和模型选择
```

### 1.3 不接受的终态

以下内容不能作为项目完成：

- 只有一个聊天接口，没有 MAA 会话和 Run 模型。
- 只有内存状态，服务重启后任务全部丢失。
- 只有一次性 JSON 响应，没有 SSE 事件续传。
- 用固定返回值伪装真实工具，却没有 Provider 接口和切换机制。
- 只实现 happy path，不处理重复请求、取消、超时、失败和恢复。
- 只能单独运行 Agent，无法接入 WiseCut Go 后端现有协议。
- 只能通过 WiseCut 页面使用，不能作为独立产品完成项目创建、素材上传和视频交付。
- Demo Provider 只返回示例 URL，却把工作包标记为真实视频生成完成。
- LangGraph、LLM、Tool 和 Provider 各自有代码，但 API 到 Worker 到 Graph 的运行链没有真实闭环。
- 只跑单元测试，没有真实 HTTP、SSE 和 Docker 联调测试。

## 2. 现有系统事实

当前 WiseCut 后端通过外部 `python_base_url` 访问 MAA，并由 `internal/third_party/maa/agent/` 负责 HTTP/SSE 客户端；`internal/task/agent_film_consumer.go` 负责持续消费远端事件并写入本地业务数据。

当前可观察到的 MAA API：

```text
POST /conversations
GET  /conversations/{conversation_id}
GET  /conversations/{conversation_id}/messages
POST /conversations/{conversation_id}/messages
GET  /conversations/{conversation_id}/artifacts/{artifact_id}
GET  /runs/{run_id}/events?after_seq={seq}&live=true
POST /runs/{run_id}/cancel
POST /approvals/{approval_id}/decide
```

当前关键事件：

```text
run.started
run.phase_changed
agent.progress
assistant.delta
assistant.message
tool.started
tool.completed
tool.failed
approval.required
approval.resolved
interaction.requested
interaction.updated
interaction.resolved
artifact.created
business.message
run.completed
run.failed
run.cancelled
```

当前两个 Profile：

```text
quick -> one-click-quick
deep  -> one-click-cocreate
```

当前 Agent Film 前端已经能够消费动态交互卡片，包括：

```text
confirm_extracted_product_context
review_storyboard_script
confirm_generation_start
component_cards
collect_fields
reveal_card
```

### 2.1 MAA Wire Contract 冻结

MAA 兼容层必须首先兼容当前 Go Client 的真实请求形态，而不是只兼容抽象接口。

请求必须支持以下 Header：

```text
X-User-ID
X-Project-ID
X-Conversation-ID
X-Run-ID
Content-Type: application/json
Accept: application/json | text/event-stream
```

`POST /conversations` 的最小请求：

```json
{
  "title": "商品视频需求",
  "agent_profile_id": "one-click-quick",
  "metadata": {
    "source": "wisecut-agent-film",
    "user_id": 1001,
    "project_id": 2001,
    "mode": "quick",
    "response_language": "zh-CN"
  }
}
```

响应必须直接提供当前客户端读取的字段，不额外包一层与客户端不兼容的 envelope：

```json
{
  "conversation_id": "conv-xxx",
  "langgraph_thread_id": "conv-xxx",
  "status": "created"
}
```

启动 Run 的消息 body：

```json
{
  "type": "message",
  "content": "...序列化后的 Agent Film 输入...",
  "metadata": {}
}
```

普通消息必须支持 `type=message|guidance`；交互答案必须支持：

```json
{
  "type": "interaction_response",
  "interaction_id": "interaction-xxx",
  "action": "approve",
  "content": {},
  "client_action_id": "client-action-xxx",
  "metadata": {
    "value": {},
    "summary": "已确认",
    "response_language": "zh-CN"
  }
}
```

SSE 每条消息必须保持标准格式：

```text
id: event-xxx
event: tool.completed
data: {"seq":12,"payload":{}}

```

所有非 2xx 响应都必须返回可记录的错误 body；所有成功响应都必须满足当前 Go Client 的直接 JSON 解码要求。Wire contract、Schema 和契约测试是后续任何实现工作的前置条件。

## 3. 最终系统架构

```text
Standalone Vue Web ── Product API / SSE ── Product API Adapter ──┐
                                                                │
WiseCut Web ── WiseCut Go ── MAA Protocol ── Compatibility API ──┤
                                                                ▼
                                             Shared Application Core
                                      Project / Conversation / Run / Artifact
                                                                │
                                                                ▼
                                              Agent Application / Event Adapter
                                                                │
                                                                ▼
                                              LangGraph Workflow + Checkpoint
                                                   │                    │
                                                   ▼                    ▼
                                           LangChain Model       Domain Tool Bus
                                                   └─────────┬──────────┘
                                                             ▼
                                            Remote LLM / Material / Video APIs

WiseCut sidecar process (existing Go repository, not this repository):
  wisecut task agent_film_consumer
    -> reads MAA SSE
    -> persists events and business side effects to WiseCut MySQL
    -> wakes WiseCut frontend SSE subscribers

 PostgreSQL: source of truth
 RabbitMQ: durable run commands / retry queues / dead-letter queues
 Redis: locks / notification / short cache / rate-limit counters
 Object Storage: uploads / artifacts / previews
 OpenTelemetry: trace / metric / structured logs
```

### 3.1 服务边界

`wisecut-agent` 负责：

- 独立产品的用户、项目、素材、上传和交付边界。
- Standalone Product API 和 Web SSE。
- WiseCut MAA Compatibility API。
- Agent 会话和 Run 的生命周期。
- LangGraph 执行和 Checkpoint 管理。
- LangChain 模型调用和工具调用。
- 用户交互和工具审批。
- MAA 事件生产、持久化、重放和 SSE 输出。
- 业务 Artifact 生成与查询。
- Profile、Prompt、Tool Policy 和 Provider 配置。

独立 Web 只调用 Product API，不直接伪造 `X-User-ID`、`X-Project-ID` 等 MAA Header。MAA 路由作为兼容适配层存在，不能反向污染独立产品的公开 API 设计。

`wisecut` 继续负责：

- 用户鉴权。
- 业务项目、钱包、素材、数字人和生成记录。
- MAA 事件消费后的业务落库。
- 对前端提供现有 Agent Film API。

`wisecut-agent` 不直接修改 WiseCut MySQL 业务表，所有业务变更通过 MAA 事件和 Artifact 交给 Go 后端处理。

其中 `wisecut task agent_film_consumer` 必须作为独立常驻进程运行。它不是 `wisecut-agent` 的 LangGraph Worker：前者消费 MAA SSE 并写 WiseCut MySQL，后者执行 Agent Graph 并生产 MAA 事件。只启动 Go HTTP API 不会完成 Agent Film 的事件落库链路。

### 3.2 技术选型决策

本项目的核心编排固定采用 LangGraph，不使用自定义 while-loop 代替状态图，也不把 FireClaw 作为运行时依赖。

```text
LangChain 负责：模型、消息、工具、结构化输出、Provider、Callback
LangGraph 负责：StateGraph、节点路由、Checkpoint、Interrupt、Resume、Stream
FastAPI 负责：MAA HTTP/SSE、鉴权、参数校验、错误映射
PostgreSQL 负责：会话、Run、事件、交互、审批、Artifact、审计
RabbitMQ 负责：可靠 Run 命令、重试队列、死信队列
Redis 负责：分布式锁、通知、短缓存、限流计数
```

依赖版本必须通过 `pyproject.toml` 和锁文件固定，并在 CI 中禁止无锁安装。LangChain、LangGraph、LangGraph Checkpoint、FastAPI、Pydantic 和数据库驱动必须在同一兼容矩阵中验证，不允许运行时自动升级。

## 4. 代码目录设计

```text
wisecut-agent/
├── app/
│   ├── main.py
│   ├── settings.py
│   ├── api/
│   │   ├── maa/                  # WiseCut 兼容协议
│   │   ├── product/              # 独立产品公开 API
│   │   └── health.py
│   ├── application/
│   │   ├── conversation_service.py
│   │   ├── run_service.py
│   │   ├── interaction_service.py
│   │   ├── approval_service.py
│   │   └── artifact_service.py
│   ├── graph/
│   │   ├── state.py
│   │   ├── builder.py
│   │   ├── quick_profile.py
│   │   ├── deep_profile.py
│   │   ├── nodes/
│   │   └── routing.py
│   ├── llm/
│   │   ├── factory.py
│   │   ├── profiles.py
│   │   ├── structured_output.py
│   │   └── callbacks.py
│   ├── tools/
│   │   ├── registry.py
│   │   ├── contracts.py
│   │   ├── policy.py
│   │   ├── approval.py
│   │   ├── product.py
│   │   ├── script.py
│   │   ├── storyboard.py
│   │   ├── materials.py
│   │   ├── digital_human.py
│   │   └── video.py
│   ├── events/
│   │   ├── types.py
│   │   ├── envelope.py
│   │   ├── projector.py
│   │   ├── publisher.py
│   │   ├── replay.py
│   │   └── sse.py
│   ├── domain/
│   │   ├── identity.py
│   │   ├── project.py
│   │   ├── asset.py
│   │   ├── agent_film.py
│   │   ├── profiles.py
│   │   ├── interaction.py
│   │   ├── generation.py
│   │   └── artifacts.py
│   ├── providers/
│   │   ├── base.py
│   │   ├── demo.py
│   │   ├── research.py
│   │   ├── materials.py
│   │   ├── digital_human.py
│   │   ├── tts.py
│   │   ├── video_webhook.py
│   │   └── video.py
│   ├── persistence/
│   │   ├── models.py
│   │   ├── repositories.py
│   │   ├── checkpointer.py
│   │   └── unit_of_work.py
│   └── security/
│       ├── auth.py
│       ├── ssrf.py
│       ├── redaction.py
│       └── limits.py
├── web/
│   ├── src/api/
│   ├── src/components/
│   ├── src/stores/
│   ├── src/views/projects/
│   ├── src/views/workbench/
│   ├── src/views/settings/
│   ├── package.json
│   └── vite.config.ts
├── migrations/
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.dev
│   └── entrypoint.sh
├── compose.yaml
├── pyproject.toml
├── .env.example
├── README.md
└── plan.md
```

## 5. 数据模型

### 5.1 核心表

```text
user_account
  id, email, password_hash, display_name, status, created_at, updated_at

workspace
  id, owner_user_id, name, created_at, updated_at

project
  id, workspace_id, owner_user_id, title, mode, status,
  aspect_ratio, duration_seconds, language, created_at, updated_at

asset
  id, project_id, owner_user_id, asset_type, storage_key, public_url,
  mime_type, size_bytes, duration_seconds, metadata_json, created_at

conversation
  id, user_id, project_id, profile_id, title, status, metadata_json,
  created_at, updated_at

run
  id, conversation_id, status, phase, graph_thread_id,
  started_at, finished_at, cancel_requested_at, error_code, error_message

message
  id, conversation_id, run_id, role, type, content_json,
  request_id, created_at

event
  id, conversation_id, run_id, seq, event_type, payload_json,
  visible, source, idempotency_key, created_at

interaction
  id, conversation_id, run_id, status, intent, payload_json,
  answer_json, version, requested_at, resolved_at

approval
  id, conversation_id, run_id, tool_name, arguments_json,
  status, decision_json, expires_at, created_at, resolved_at

artifact
  id, project_id, conversation_id, run_id, artifact_type, uri, metadata_json,
  payload_json, status, created_at

tool_execution
  id, conversation_id, run_id, tool_name, input_json, output_json,
  status, attempt, started_at, finished_at, error_json

checkpoint
  thread_id, checkpoint_id, parent_checkpoint_id, state_json,
  metadata_json, created_at

outbox_event
  id, aggregate_type, aggregate_id, event_type, payload_json,
  published_at, attempt, last_error

audit_log
  id, actor_type, actor_id, action, resource_type, resource_id,
  payload_json, created_at
```

### 5.2 一致性要求

- `conversation_id + request_id` 唯一，保证消息幂等。
- `conversation_id + run_id + seq` 唯一，保证事件幂等。
- `tool_execution` 保存每次工具尝试，不覆盖历史。
- 事件先写数据库，再通过 Outbox 发布。
- LangGraph Checkpoint 与 MAA Run 必须保存明确映射。
- 所有时间统一使用 UTC 存储，API 展示按 Asia/Shanghai 转换。
- 原始用户输入、工具参数和内部路径必须按权限脱敏后才进入前端事件。

### 5.3 LangGraph 与 MAA ID 映射

一条 MAA Run 必须维护以下明确映射，不能只依赖历史字段名推断：

```text
MAA conversation_id  <-> conversation.id
MAA run_id           <-> run.id
LangGraph thread_id  <-> run.graph_thread_id
LangGraph checkpoint <-> checkpoint.checkpoint_id
MAA event seq        <-> event.seq
Tool execution id    <-> tool_execution.id
Artifact id          <-> artifact.id
```

`conversation_id`、`run_id`、`graph_thread_id` 可以在当前实现中使用相同字符串，但数据库字段和代码语义必须保持独立，防止未来替换执行引擎时发生数据迁移困难。

### 5.4 事务边界

每个外部动作遵循以下边界：

```text
业务状态变更 + Event 行 + Outbox 行
                     ↓ 同一 PostgreSQL 事务
               RabbitMQ publish
                     ↓
               publish 标记
```

RabbitMQ 发布失败不能回滚已经提交的业务事实，Outbox Worker 必须可重试；重复发布由 `command_id`、`run_id` 和幂等消费保护。

### 5.5 独立产品所有权边界

- Standalone 请求必须从认证主体解析 `user_id`，禁止使用固定 `1001/2001` 回退值。
- `workspace -> project -> asset/conversation/artifact` 必须形成明确所有权链。
- MAA Compatibility API 可以从受信任 Header 映射到内部主体，但必须使用服务间认证，并隔离于浏览器公开路由。
- Product API 返回资源前必须验证用户和 workspace/project 归属。
- 上传采用预签名或受控代理上传；对象存储 key 不由客户端任意指定。

## 6. Agent 状态设计

```python
class AgentFilmState(TypedDict):
    conversation_id: str
    run_id: str
    profile_id: str
    language: str
    user_request: str
    product_link: str | None
    input_files: list[dict]
    product_context: dict
    creative_strategy: dict
    script: dict
    storyboard: dict
    materials: list[dict]
    digital_human: dict | None
    render_job: dict | None
    artifacts: list[dict]
    pending_interaction: dict | None
    pending_approval: dict | None
    errors: list[dict]
    retry_count: int
```

状态更新必须通过明确的节点输出，不允许工具直接任意修改全局状态。

### 6.1 状态不变量

- `completed`、`failed`、`cancelled` 是终态，终态 Run 不再接受普通消息。
- `waiting_interaction` 必须存在一个 pending interaction，且不占用 Worker 执行槽。
- `waiting_approval` 必须存在一个 pending approval，且审批过期后只能进入失败或取消分支。
- `rendering` 状态必须存在 render job 或可恢复的 Provider task id。
- `artifact.ready=true` 之前不得发出 `final_video` completed 业务消息。
- 每个 Run 只能有一个 active graph execution。
- 任何状态迁移必须产生可审计事件。

## 7. LangGraph 工作流

### 7.1 主图

```text
START
  ↓
normalize_input
  ↓
collect_product_context
  ↓
needs_product_confirmation?
  ├─ yes → request_product_context_review
  │          ↓ interrupt/resume
  └─ no ───────────────────────┐
                               ↓
generate_creative_strategy
  ↓
generate_script
  ↓
review_script_or_storyboard?
  ├─ yes → request_storyboard_review
  │          ↓ interrupt/resume
  └─ no ───────────────────────┐
                               ↓
prepare_generation
  ↓
request_generation_approval
  ↓ interrupt/resume
collect_materials
  ↓
match_digital_human
  ↓
render_video
  ↓
validate_delivery
  ↓
publish_artifacts
  ↓
emit_final_video_message
  ↓
END
```

### 7.2 Quick Profile

Quick 模式以最少交互完成成片：

- 自动提取商品上下文。
- 只在关键事实缺失或生成扣费前请求交互。
- 使用默认视频比例、时长和脚本策略。
- 失败时优先走自动重试和降级工具。

### 7.3 Deep Profile

Deep 模式强调共创和可控性：

- 允许用户确认商品上下文。
- 允许用户选择营销方向。
- 强制展示脚本或分镜审核卡。
- 支持修改、换一批和重新生成。
- 支持用户在执行中发送 guidance。

两个 Profile 使用同一套工具和事件协议，只通过 graph routing、Prompt profile 和交互策略产生行为差异。

### 7.4 Prompt 和结构化输出

Prompt 不散落在节点代码中，统一由 Profile + Prompt Version 管理：

```text
profile_id
prompt_name
prompt_version
language
model_provider
model_name
temperature
max_tokens
output_schema_version
```

模型输出必须优先使用 Pydantic/JSON Schema 结构化解析；解析失败时记录原始响应摘要、执行一次受限修复，超过次数进入明确的 `llm.output_invalid` 错误，不允许静默猜测业务字段。

每次 Run 必须保存实际使用的模型、Prompt 版本、工具集合和关键参数，确保结果可复现和可审计。

### 7.5 运行时闭环要求

以下链路必须由真实集成测试证明，不能以模块单测替代：

```text
Product/MAA API 写入消息和 Run
  -> Outbox 发布 RabbitMQ RunCommand
  -> Worker 获取 Conversation lock
  -> GraphRunner 执行 LangGraph astream/ainvoke
  -> 节点调用真实 LLM/Tool/Provider
  -> interaction 使用 interrupt() 暂停
  -> 用户答案通过 Command(resume=...) 恢复同一 thread/checkpoint
  -> 媒体节点生成真实 Artifact
  -> run.completed terminal event
  -> SSE after_seq 可重放完整轨迹
```

Worker 默认 handler 不允许保留 no-op；`GraphRunner` 不允许保留 stub；交互节点不能通过直接连 `END` 冒充 interrupt/resume。

## 8. 工具系统

### 8.1 工具契约

每个工具必须声明：

```text
name
description
input_schema
output_schema
timeout
retry_policy
security_level
requires_approval
provider
```

工具执行统一经过：

```text
Policy Check
  ↓
Input Validation
  ↓
Approval Check
  ↓
tool.started
  ↓
Provider Execution
  ↓
Output Validation
  ↓
tool.completed / tool.failed
```

### 8.2 领域工具

```text
parse_product_link
extract_product_facts
collect_product_materials
generate_creative_strategy
generate_video_script
generate_storyboard
search_materials
select_materials
match_digital_human
generate_voice_script
render_video
validate_video
publish_artifact
```

### 8.3 Provider 设计

每类工具都必须通过接口访问 Provider：

```text
DemoProductResearchProvider
RealProductResearchProvider

DemoMaterialProvider
RealMaterialProvider

DemoDigitalHumanProvider
RealDigitalHumanProvider

DemoVideoRenderProvider
RealVideoRenderProvider
```

Demo Provider 只用于本地完整联调，不允许隐藏在生产配置中。生产环境必须显式选择真实 Provider 或明确拒绝启动。

独立产品必须至少实现以下非 Demo Provider：

```text
OpenAICompatibleLLMProvider  真实脚本和分镜结构化生成
ObjectStorageAssetProvider   使用用户上传和对象存储素材
RemoteVideoProvider          调用真实视频生成 API，返回远程 task id
RemoteVideoCallbackAdapter   Webhook/轮询、状态映射、幂等回调和产物归档
```

视频 Provider 必须支持异步提交、查询、Webhook 或轮询、取消、超时、幂等回调、错误映射和费用记录。具体供应商通过 Adapter 接入，领域层不得绑定某一家 SDK。

### 8.4 工具执行隔离

工具按照风险分层：

```text
L0: 纯函数和本地格式转换，无外部副作用
L1: 只读 HTTP/素材查询，需要 SSRF 防护
L2: 创建外部任务或上传文件，需要超时、幂等和审批
L3: 扣费、发布、删除或修改业务数据，必须人工审批和审计
```

每个工具必须实现超时、取消、幂等键、重试上限、结果大小限制和敏感字段脱敏。工具不能直接访问数据库 ORM，只能通过领域 Service 或 Provider 接口产生业务结果。

## 9. MAA API 设计

### 9.1 会话

```http
POST /conversations
GET  /conversations/{conversation_id}
GET  /conversations/{conversation_id}/messages
```

创建会话必须保存 `agent_profile_id`、用户、项目、语言和初始输入元数据。

### 9.2 消息

```http
POST /conversations/{conversation_id}/messages
```

支持：

```text
message
guidance
interaction_response
```

消息写入后通过任务队列触发对应 Run，不允许请求线程直接执行长时间视频任务。

消息请求必须携带或生成稳定的 `request_id`；相同 Conversation 下重复 request_id 必须返回第一次处理结果。没有 request_id 的消息使用受限内容指纹作为短期防重复保护，但不能替代正式幂等键。

### 9.3 事件流

```http
GET /runs/{run_id}/events?after_seq=0&live=true
```

要求：

- `text/event-stream`。
- 每条事件有稳定 `id` 和单调递增 `seq`。
- `after_seq` 支持断点续传。
- terminal event 到达后正常结束流。
- 非 terminal 网络断开时客户端可以重新连接。
- 事件已经落库后才能发送给消费者。

### 9.4 Interaction

`interaction.requested` 必须包含前端可直接渲染的 `frontend_interaction`，至少支持：

```json
{
  "intent": "component_cards",
  "interaction_id": "interaction-id",
  "cards": [],
  "actions": [],
  "status": "pending"
}
```

用户答案必须经过状态检查、版本检查和幂等检查，才能调用 LangGraph `Command(resume=...)`。

### 9.5 Artifact

最终视频使用：

```json
{
  "type": "business.message",
  "payload": {
    "message": {
      "business_key": "final_video",
      "status": "completed",
      "payload": {
        "video_url": "https://...",
        "cover_url": "https://..."
      }
    }
  }
}
```

同时写入 Artifact 表，支持通过 `/artifacts/{artifact_id}` 查询完整数据。

### 9.6 Standalone Product API

公开给独立 Web 的 API 使用版本前缀，并与 MAA Compatibility API 分离：

```http
POST   /api/v1/auth/register
POST   /api/v1/auth/login
GET    /api/v1/me
GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{project_id}
PATCH  /api/v1/projects/{project_id}
DELETE /api/v1/projects/{project_id}
POST   /api/v1/projects/{project_id}/assets
GET    /api/v1/projects/{project_id}/assets
POST   /api/v1/projects/{project_id}/runs
GET    /api/v1/runs/{run_id}
GET    /api/v1/runs/{run_id}/events
POST   /api/v1/interactions/{interaction_id}/responses
POST   /api/v1/runs/{run_id}/cancel
GET    /api/v1/projects/{project_id}/artifacts
GET    /api/v1/artifacts/{artifact_id}/download
GET    /api/v1/providers
PUT    /api/v1/provider-settings
```

Product API 必须提供浏览器可用的认证、资源所有权校验、上传限制、分页和稳定错误模型；不能要求浏览器构造 MAA 服务间 Header。

## 10. 运行、任务和恢复

### 10.1 执行模型

API 进程不执行长任务，只负责：

1. 校验请求。
2. 创建或复用 Conversation/Run。
3. 写入消息和 Outbox。
4. 返回当前状态。

Worker 负责：

1. 从 RabbitMQ durable queue 读取 Run command。
2. 获取 Conversation 级分布式锁。
3. 恢复 LangGraph Checkpoint。
4. 执行图节点和工具。
5. 持久化事件和状态。
6. 处理重试、取消、超时和最终收尾。

Redis 只承担锁、通知和短期协调，不承担不可丢失的 Run command source of truth。

### 10.2 恢复策略

- 进程崩溃：从最新 Checkpoint 继续。
- 工具超时：按工具策略重试，超过次数进入 `tool.failed`。
- LLM 临时错误：Provider Failover 或指数退避。
- SSE 断开：事件不丢，客户端从 `after_seq` 继续。
- 用户取消：设置 cancel flag，主动取消当前工具和 Graph Run。
- 服务重启：扫描非终态 Run，恢复或标记为可重试。
- 交互等待：Run 保持 `waiting_interaction`，不占用 Worker。

### 10.3 取消和补偿

取消不是简单把数据库状态改成 `cancelled`：

1. 写入 cancel request 和审计事件。
2. 设置 Redis cancel flag，通知当前 Worker。
3. 调用 Provider 的 cancel 能力；不支持取消的 Provider 进入 orphan task 监控。
4. 停止新的工具调用和 graph 节点推进。
5. 写入 `run.cancelled`，关闭 pending interaction/approval。
6. 对已经创建但未交付的 Artifact 做清理或标记过期。
7. 对外部任务产生的费用、资源和回调执行幂等补偿。

### 10.4 背压和容量

- 每个用户、项目、Conversation 和 Provider 都有并发上限。
- 队列消息必须包含优先级、超时时间和最大尝试次数。
- 长任务和交互等待不能占用相同的 Worker slot。
- SSE 客户端慢消费时只保留数据库事件，不阻塞 Graph Worker。
- 事件和 Artifact payload 设定大小上限，超大内容写对象存储。
- 当 LLM 或媒体 Provider 限流时，系统进入显式 queued/backoff，不无限重试。

## 11. 安全要求

- API Key、模型 Token 和第三方凭证只从环境变量或 Secret 注入。
- 所有外部 URL 做协议、域名、DNS 和内网地址校验，防止 SSRF。
- 文件上传限制大小、类型、数量和下载超时。
- 工具参数全部使用 Pydantic 校验。
- 工具审批采用 allow/deny/ask 三态策略。
- Shell、文件系统和网络工具默认关闭；Agent Film 只开放领域工具。
- 用户输入、Prompt、工具参数和 Artifact URL 做日志脱敏。
- 按 user_id、project_id、conversation_id 做权限校验。
- 事件和 Artifact API 不允许跨用户读取。
- 生产环境关闭 Demo Provider 和调试端点。

## 12. 可观测性

每次请求和 Run 必须携带：

```text
request_id
trace_id
conversation_id
run_id
graph_thread_id
tool_execution_id
```

必须提供：

- 结构化 JSON 日志。
- HTTP 延迟、错误率和状态码指标。
- LLM 请求次数、Token、耗时和费用指标。
- Tool 成功率、重试次数和耗时指标。
- Run 各阶段耗时。
- SSE 连接数、重连数和发送延迟。
- Event Outbox 堆积量。
- 未完成 Run 和超时 Run 数量。
- OpenTelemetry trace，覆盖 API、Graph、LLM、Tool、数据库和 Provider。

## 13. Docker 和部署

### 13.1 本地服务

```text
wise-cut
oss-admin
wisecut-api
wisecut-agent-film-consumer
wisecut-agent-web
wisecut-agent
mysql
redis
rabbitmq
postgres-agent
minio
```

MAA Agent 默认端口：

```text
HTTP API: 10728
健康检查: 10728/health
```

### 13.2 生产部署边界

- API 和 Worker 分开部署。
- Worker 支持水平扩展，但同一 Conversation 同时只允许一个执行者。
- PostgreSQL 使用独立实例和迁移管理。
- Redis 使用高可用配置。
- Artifact 使用对象存储，不把大文件放进数据库。
- 所有服务支持优雅退出。
- 生产配置不能依赖本地文件挂载和开发 Demo 数据。
- 镜像使用非 root 用户运行。
- 健康检查区分 liveness、readiness 和 dependency health。

### 13.3 环境配置

```text
local-demo
  Demo LLM / Demo Material / Demo Digital Human / Demo Video
  允许固定示例数据，禁止真实扣费

local-llm
  使用用户提供的 OpenAI-compatible API
  媒体能力仍可使用 Demo Provider

staging
  真实 LLM + 沙箱媒体 Provider + 完整观测
  所有外部任务带 staging namespace

production
  真实 Provider + Secret Manager + 高可用依赖
  禁止 Demo Provider 和调试接口
```

所有环境必须通过启动时配置校验，缺少必需凭证、队列、数据库或对象存储时 readiness 失败。

### 13.4 Standalone Web

独立前端采用 Vue 3 + TypeScript + Vite，与现有 WiseCut Agent Film 页面保持协议概念一致，但不依赖 WiseCut 的账户、钱包、主题包、上传组件和全局状态。

必须交付以下页面和状态：

```text
登录与本地开发身份
项目列表与新建项目
创作输入与素材上传
Agent 对话和运行时间线
商品信息确认卡
脚本与分镜审核/编辑
生成确认和取消
素材/数字人选择
视频生成进度
最终视频预览、下载和重新生成
运行历史、失败详情和重试
模型与 Provider 设置
```

前端必须使用真实 Product API 和 SSE，不在浏览器内硬编码 Demo 状态。核心布局必须在桌面和移动视口通过 Playwright 截图与交互验证。

## 14. 测试策略

### 14.1 单元测试

- Graph 路由和状态转换。
- Prompt 输入和结构化输出解析。
- Tool schema 和 policy。
- Interaction 状态机。
- Approval 状态机。
- Event seq 和幂等键。
- SSE 编码、续传和 terminal event。
- Artifact 归一化。
- Provider 重试和错误映射。

### 14.2 契约测试

- 对照 WiseCut MAA Client 验证所有 API。
- 校验 HTTP response shape。
- 校验所有事件类型和 payload。
- 校验 `after_seq` 不重复、不跳过已持久化事件。
- 校验 interaction payload 能被现有前端渲染。
- 校验 final video business message 能被 Go 后端落库。

### 14.3 集成测试

- PostgreSQL、Redis、对象存储真实容器。
- LangGraph Checkpoint 恢复。
- API 到 Worker 的异步链路。
- Outbox 到 SSE 的链路。
- Worker 崩溃和重启。
- 工具超时、重试和取消。
- 多 Worker 同一 Conversation 互斥。

### 14.4 端到端测试

完整跑通：

```text
WiseCut 前端
  → Go 后端
  → MAA Agent
  → LangGraph
  → Demo Provider
  → MAA Event
  → Go Consumer
  → MySQL
  → WiseCut 前端
```

### 14.5 Agent 质量评估

除了传统接口测试，还要建立可重复的 Agent 评估集：

- 商品链接解析准确率。
- 商品事实抽取的字段完整率和幻觉率。
- 脚本 JSON Schema 合法率。
- 分镜时长、比例和镜头数量约束通过率。
- 用户交互卡片字段完整率。
- 工具选择准确率和无效工具调用率。
- 失败后恢复成功率。
- 相同输入在固定 Prompt/Model 版本下的结果稳定性。
- Token、延迟和单次 Run 成本。

每个评估样本保存输入、期望约束、实际事件轨迹、最终 Artifact 摘要和模型版本。模型升级、Prompt 变更或工具变更必须重新运行离线评估，禁止只凭人工点页面判断质量。

### 14.6 故障注入

必须在集成环境注入：

- LLM 超时、429、空响应和非法 JSON。
- 工具超时、重复回调和错误结果。
- RabbitMQ 断开、消息重复和死信。
- Redis 锁续租失败。
- PostgreSQL 短暂不可用。
- Worker 在 checkpoint 前后崩溃。
- SSE 客户端反复断线。
- Provider 返回已完成但本地未收到结果。

每种故障都要有预期状态、事件、告警和恢复动作。

### 14.7 独立产品端到端测试

至少覆盖：

1. 注册/登录并创建项目。
2. 上传图片、视频或文档素材。
3. Quick 模式从输入到远程视频 API 产物下载。
4. Deep 模式完成商品确认、脚本/分镜审核和生成确认。
5. 浏览器刷新和 SSE 断线后恢复同一 Run。
6. 用户取消、Provider 失败、重试和重新生成。
7. 两个用户之间的项目、素材、Run 和 Artifact 隔离。
8. WiseCut MAA 兼容链路在独立产品改造后继续通过。

## 15. 完成验收标准

### 15.1 功能验收

- Quick/Deep 都能创建会话。
- 支持文字、链接、图片、音频、视频和文档输入。
- 支持商品信息确认。
- 支持脚本/分镜审核。
- 支持生成确认和工具审批。
- 支持补充消息和 guidance。
- 支持取消、重试和重新生成。
- 支持数字人选择。
- 支持视频渲染和最终 Artifact。
- 支持失败提示和恢复。

### 15.2 系统验收

- Agent 服务重启后未完成 Run 不丢失。
- SSE 重连后事件不重复。
- 重复提交不产生重复扣费语义或重复 Run。
- 同一 Conversation 不会被多个 Worker 并发执行。
- 事件、工具和 Artifact 都能按 Run 查询。
- 日志可以通过 trace_id 串起完整链路。
- Docker Compose 能在新机器初始化后运行。

### 15.3 学习和面试验收

项目最终必须能解释：

- LangChain 和 LangGraph 的边界。
- 为什么要使用 StateGraph 而不是普通 while loop。
- Checkpoint、thread_id 和 run_id 的关系。
- interrupt/resume 如何实现 Human-in-the-loop。
- Tool Calling 如何做 schema、审批和错误恢复。
- SSE 如何做事件持久化、续传和去重。
- API 进程和 Worker 为什么要分离。
- Outbox、幂等、分布式锁和最终一致性如何配合。
- 如何从 Demo Provider 迁移到真实第三方 Provider。
- 如何控制 Agent 成本、权限和数据安全。

### 15.4 服务级目标

最终版必须明确并在 staging 测量：

```text
API 可用性：99.9% 以上
健康检查响应：P95 < 200ms
创建会话接口：P95 < 1s，不等待长任务
事件写入延迟：P95 < 500ms
SSE 续传成功率：> 99%
重复命令副作用：0 次
未处理 Outbox：正常情况下 < 100 条
终态 Run 长时间悬挂：0 条
```

具体数字可根据压测结果调整，但必须在实现前固定指标定义、统计窗口和告警阈值。

## 16. 实施顺序

WP-00 至 WP-10 已产生协议、基础设施和领域模块，但 2026-10-14 重基线审计确认运行链尚未闭环。后续顺序以以下工作包为准：

1. `WP-11`：清零工程质量债，并闭合 API -> Queue -> Worker -> LangGraph -> HITL -> Artifact 运行链。
2. `WP-12`：实现独立产品的用户、workspace、project、asset、Product API 和浏览器认证。
3. `WP-13`：实现独立 Vue 3 Agent Film Web。
4. `WP-14`：接入真实 LLM 和至少一个真实远程视频生成 API Provider。
5. `WP-15`：验证并修复 WiseCut MAA Compatibility API 和 Go Consumer 全链路。
6. `WP-16`：完成独立产品和 WiseCut 双模式 Docker 编排、环境配置与本地启动。
7. `WP-17`：完成单元、契约、真实依赖集成、Playwright E2E、Agent 评估、故障注入和压测。
8. `WP-18`：完成 staging/production 发布、监控、告警、备份、灰度和回滚。

每一步都必须保持前一步的契约兼容，不允许通过临时接口绕过 MAA 协议。

## 17. 仓库和版本策略

- `wisecut-agent` 是独立 Git 仓库。
- 现有三个 WiseCut 仓库只做必要的配置和兼容改动。
- Agent API Schema 与 Go Client 的变更必须同一变更记录。
- 每个功能包含代码、迁移、测试、文档和 Docker 更新。
- 不提交 `.env`、Token、数据库文件、上传文件、模型缓存和运行日志。
- 生产配置、开发配置和 Demo 配置明确分离。
- 重大协议变更使用版本字段，保持旧客户端可读。

## 18. 最终交付物

```text
1. wisecut-agent 源码仓库
2. MAA OpenAPI 和事件 Schema
3. LangGraph Agent Film 工作流
4. 可恢复的 Session / Run / Event / Artifact 系统
5. Tool Registry、Approval 和 Provider 系统
6. 本地 Demo Provider
7. 独立 Product API、用户/项目/素材系统
8. Vue 3 独立 Agent Film Web
9. 真实 OpenAI-compatible LLM Provider
10. 真实远程视频生成 Provider、Webhook/轮询和产物归档
11. 可选第三方模型、素材、数字人和视频 Provider
12. 独立产品与 WiseCut 双模式 Docker 环境
13. PostgreSQL/RabbitMQ/Redis/Object Storage 迁移和初始化脚本
14. 单元、契约、集成、Playwright 和端到端测试
15. 架构、部署、排障和面试学习文档
16. 生产化安全、监控和故障恢复能力
17. 面向其他编程智能体的 `AGENTS.md`、开发流程、协议来源地图、联调指南和启动指令
```

完成这些交付物后，项目才算达到“独立 Agent Film 产品完成，并保持 MAA 兼容”，而不是只完成一个能对话或返回示例视频 URL 的 Agent Demo。

## 19. 实现前置产物和每阶段出口条件

### 19.1 协议阶段出口

必须提交：

- `openapi/maa.openapi.yaml`
- `schemas/events/*.json`
- `schemas/interactions/*.json`
- `schemas/artifacts/*.json`
- `fixtures/maa/*.json`
- Go Client 对照契约测试

出口条件：使用 fixture 启动服务后，当前 Go MAA Client 的每一个方法都能得到合法响应，SSE 能按 `after_seq` 重放。

### 19.2 数据和运行时阶段出口

必须提交：

- 全量数据库迁移和回滚脚本。
- Repository 和 Unit of Work。
- Outbox Publisher。
- RabbitMQ queue/exchange/dead-letter 声明。
- Run recovery scanner。
- Checkpoint 与 MAA Run 映射测试。

出口条件：杀掉 API、Worker、RabbitMQ 或 PostgreSQL 后，系统能按预期恢复，不产生重复终态事件。

### 19.3 Agent 阶段出口

必须提交：

- Quick/Deep graph。
- Prompt registry。
- Model provider factory。
- Tool registry 和 policy。
- Interaction/Approval interrupt 测试。
- Agent trace fixture 和离线评估报告。

出口条件：固定测试集能够得到可验证的结构化脚本、分镜、交互卡片和最终 Artifact，质量指标达到项目设定阈值。

### 19.4 业务联调阶段出口

必须提交：

- Standalone Web 和 Product API。
- 独立用户、项目、素材和 Artifact 数据链。
- 真实远程视频 API 生成、回调/轮询和可下载产物证据。
- `wisecut` 的本地 Agent 配置变更。
- 四仓库 Compose 编排。
- 真实前端操作录屏或测试报告。
- Go Consumer 事件落库验证。
- 失败、取消、重试、断线恢复报告。

出口条件：独立 Web 能完成一次真实 MP4 生成和下载；WiseCut 用户端也能完成一次兼容流程，并在 Go 后端的项目、素材、分镜和最终视频字段中得到正确结果。

### 19.5 生产阶段出口

必须提交：

- staging 镜像和部署清单。
- Secret、网络、权限和数据保留策略。
- Dashboard、告警规则和故障手册。
- 压测和故障注入报告。
- 回滚演练记录。

出口条件：可以在不丢失 Run/Event/Artifact 的前提下发布新版本、回滚版本和扩容 Worker。

## 20. 变更控制

本文件作为实现基线。后续如果需要改变技术路线、MAA wire contract、数据库主键语义、事件语义、队列职责或生产验收标准，必须先更新本文件并增加变更记录，再修改代码。

允许的实现细节调整包括：节点内部 Prompt 写法、Provider SDK 选择、目录内部拆分和具体 SQL 索引优化；这些调整不能改变已冻结的外部协议和状态不变量。

从本文件进入编码阶段后，任何“临时先绕过”的实现都必须标注为待收敛项，不能作为完成状态合并。

## 21. 2026-10-14 正式重基线

### 21.1 重基线原因

WP-01 至 WP-10 已实现大量协议、持久化、Worker、Graph、Tool、领域和安全模块，但完成状态主要由局部单元测试支持。代码审计确认项目尚未形成可执行的端到端 Agent Film 产品，因此从本节起以“独立产品 + MAA 兼容适配器”为新基线。

### 21.2 已确认事实

- `pytest -q`：331 passed，说明已有局部模块测试稳定。
- `mypy app`：187 errors in 35 files，不能声称 type check 通过。
- 当前环境找不到 `ruff`，不能声称 lint 已执行通过。
- `pyproject.toml` 使用宽松 `>=` 依赖且仓库没有锁文件，不能声称依赖已固定。
- Worker 默认使用 no-op handler，没有注入 `GraphRunner`。
- `GraphRunner._execute_graph()` 仍是 stub，没有调用 LangGraph `ainvoke/astream`。
- interaction response 只落库，没有 `Command(resume=...)` 恢复 Graph。
- 当前业务脚本和分镜采用启发式规则，LLM Factory 尚未接入业务节点。
- Real Research/Material/DigitalHuman/Video Provider 均返回 `not_implemented`。
- Demo 视频返回 `example.com` URL，不构成真实视频交付。
- 权限校验函数尚未接入 API 路由，部分 MAA API 缺 Header 时回退固定 `1001/2001`。
- RabbitMQ 本地默认 URL 使用管理端口 `15675`，应按 AMQP 映射核对为 `15676`。
- 当前本地分支比 GitHub `origin/main` 超前 10 个 commit，继续跨环境开发前必须先决定是否推送。

### 21.3 状态解释

历史 commit 和已实现模块继续保留，不回滚、不伪造历史。`execution.md` 中被重新标为 `[~]` 的工作包表示“已有实现，但未满足最终出口条件”，后续在 WP-11 统一闭环和纠偏。

### 21.4 新完成定义

项目只有同时满足以下条件才能称为独立 Agent Film 产品：

1. 独立 Web 不依赖 WiseCut 即可登录、建项目、上传素材并开始 Run。
2. Worker 实际执行 LangGraph，HITL 使用 interrupt/resume 恢复同一 Checkpoint。
3. 脚本和分镜至少可使用一个真实 OpenAI-compatible LLM 生成。
4. 远程视频 Provider 能生成真实、可探测、可播放、可下载的视频产物。
5. Product API 与 MAA Compatibility API 共用同一领域内核且各自鉴权正确。
6. PostgreSQL、RabbitMQ、Redis、对象存储和视频 Provider 沙箱/测试账号完成真实集成验证。
7. 独立 Web 和 WiseCut 兼容链路都通过端到端测试。
8. lint、type check、unit、contract、integration、E2E 均有真实通过输出。
