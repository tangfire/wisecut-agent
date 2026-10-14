# 2026-10-14 独立 Agent Film 产品重基线审计

## 1. 审计结论

当前仓库已经形成 MAA 协议、FastAPI、持久化、队列、LangGraph、Tool、领域逻辑、媒体 Artifact、安全与观测等模块，但仍属于“模块化 Demo 后端”，尚未形成可独立运行的 Agent Film 产品。

项目目标从：

```text
WiseCut 所依赖的 MAA 兼容服务
```

升级为：

```text
独立 Agent Film Web + Product API + Agent Runtime
                         +
WiseCut MAA Compatibility API
```

## 2. 已执行验证

```text
git status --short --branch
结果：main 比 origin/main 超前 10 个 commit，工作区在审计前干净

pytest -q
结果：331 passed, 1 warning

ruff check .
结果：当前执行环境找不到 ruff 命令

mypy app
结果：187 errors in 35 files (checked 67 source files)
```

`331 passed` 证明局部模块测试存在且稳定，但测试集中没有 API -> RabbitMQ -> Worker -> LangGraph -> interrupt/resume -> Provider -> Artifact 的真实端到端测试。

## 3. 运行链证据

### Worker 未执行 Graph

- `app/main.py` 调用 `start_worker_thread()` 时没有传入 Graph handler。
- `app/worker/run_worker.py` 在 handler 为空时使用 `_default_handler`。
- `_default_handler` 只把 Run 更新为 `waiting_interaction`。

### GraphRunner 仍是 stub

- `app/graph/runner.py::_execute_graph()` 日志为 `Executing graph (stub)`。
- 该方法没有调用 LangGraph `ainvoke()` 或 `astream()`。
- 当前行为只把 Run 更新为 `waiting_interaction`。

### HITL 未闭环

- Graph review/approval 节点返回 `pending_interaction` / `pending_approval`，但没有真实 `interrupt()`。
- interaction response 会写 Message、更新 Interaction 和写 `interaction.resolved`，但没有 `Command(resume=...)`。
- 生成确认节点之后的媒体路径没有通过 resume 进入执行。

## 4. 模型和 Provider 证据

### LLM 未进入业务节点

- `app/llm/factory.py` 定义 Demo 和 OpenAI-compatible LLM。
- 仓库业务路径没有调用 `create_llm()` / `get_default_llm()`。
- `app/domain/agent_film.py` 明确说明创意策略当前使用 heuristic approach。

### Real Provider 未实现

以下 Provider 在关闭 Demo 后均返回 `not_implemented`：

- `app/providers/research.py`
- `app/providers/materials.py`
- `app/providers/digital_human.py`
- `app/providers/video.py`

Demo 视频 URL 为 `https://example.com/demo-video.mp4`，不能作为真实视频交付证据。

重基线后的视频路线采用真实远程视频生成 API Provider，不要求本地 FFmpeg。Provider contract 必须支持异步 task、Webhook/轮询、取消、超时、幂等回调、错误映射、费用记录和对象存储归档。

## 5. 安全和工程质量证据

- `app/security/authz.py` 定义权限函数，但当前 API 路由没有调用。
- `app/api/conversations.py` 和 `app/api/messages.py` 在 Header 缺失时回退固定 `1001/2001`。
- `pyproject.toml` 依赖使用 `>=`，仓库没有 lock 文件。
- `execution.md` 旧记录声称 lint/type check 通过，与本次验证不一致。
- RabbitMQ 默认 URL 使用 `15675`，这是现有 WiseCut Compose 的管理端口；AMQP 映射端口为 `15676`，必须在 WP-11 核实修正。

## 6. 状态纠正

继续保持完成：

- WP-00：仓库与文档基线。
- WP-01：MAA Wire Contract、Schema、Fixture。
- WP-04：MAA Compatibility API 表面协议；运行闭环不包含在该完成语义中。

重新标记为进行中：

- WP-02：缺锁文件、ruff 输出和 mypy 通过。
- WP-03：缺真实 PostgreSQL、Checkpoint 和 Outbox 恢复测试。
- WP-05：Worker 默认 no-op。
- WP-06：GraphRunner/HITL stub。
- WP-07：Tool/Approval 尚未接入真实 Graph。
- WP-08：业务节点为启发式且没有真实执行链。
- WP-09：只有 Demo Provider，没有真实视频。
- WP-10：安全和观测模块未接入全部真实请求链。

## 7. 新工作顺序

```text
WP-11 运行时闭环与质量纠偏
WP-12 独立产品领域与 Product API
WP-13 独立 Vue Agent Film Web
WP-14 真实 LLM 与视频生成 API
WP-15 WiseCut MAA 兼容联调
WP-16 Docker 和环境
WP-17 测试和质量评估
WP-18 生产交付
```

下一位智能体必须从 WP-11 开始。WP-11 未完成前，不开始前端或真实 Provider 接入。
