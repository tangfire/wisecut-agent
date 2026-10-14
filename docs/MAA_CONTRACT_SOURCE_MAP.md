# MAA 协议来源地图

当前 MAA 协议不是凭空设计，必须对照 WiseCut 三个仓库中的真实来源。

## 1. Go Client 主来源

仓库：`D:\dx\wisecut`

| 目标 | 来源 |
| --- | --- |
| MAA Client 类型和请求 | `internal/third_party/maa/agent/types.go` |
| Conversation/Message/Interaction/Approval/Artifact API | `internal/third_party/maa/agent/client.go` |
| SSE 解析、重连和 `after_seq` | `internal/third_party/maa/agent/client.go` |
| MAA 请求 Header | `internal/third_party/maa/agent/client.go` 的 `setAgentFilmHeaders` |
| Remote message content | `internal/third_party/maa/agent/client.go` 的 `buildAgentFilmRemoteMessageContent` |
| Command content | `internal/third_party/maa/agent/client.go` 的 `buildAgentFilmRemoteCommandContent` |
| 事件模型 | `internal/third_party/maa/agent/types.go`、`parseMAAAgentFilmEvent` |
| Agent URL 配置 | `config-dev.toml`、`config-docker.toml` 的 `[agent_film]` |

## 2. Go Service 业务来源

| 目标 | 来源 |
| --- | --- |
| Session/Run 创建 | `internal/service/agent_film.go` |
| 输入归一化和附件清洗 | `internal/service/agent_film_input.go` |
| Interaction 提交和状态 | `internal/service/agent_film_interaction.go` |
| Agent 事件消费和副作用 | `internal/service/agent_film_consumer_*.go` |
| Artifact 和 final video | `internal/service/agent_film_artifact.go` |
| 需求里程碑事件 | `internal/service/agent_film_requirement_event.go` |
| 自动确认和扣费协作 | `internal/service/agent_film_generation_auto_approve.go` |
| MAA Client 抽象 | `internal/service/agent_film_remote.go` |

## 3. Go Consumer 来源

这是必须独立运行的 WiseCut 进程，不是 `wisecut-agent` 内部 Worker：

```text
wisecut task agent_film_consumer
```

| 目标 | 来源 |
| --- | --- |
| 进程入口 | `internal/task/agent_film_consumer.go` |
| 任务注册 | `internal/task/tasks.go`、`internal/di/wire_gen.go` |
| 本地开发命令 | `Makefile` 的 `run-consumer-dev` |
| 全局单例和会话租约 | `internal/service/agent_film_consumer.go`、`agent_film_consumer_collector.go` |
| SSE 消费循环 | `internal/service/agent_film_consumer_loop.go` |
| 批量写事件 | `internal/service/agent_film_consumer_batch_writer.go` |
| 事件副作用 | `internal/service/agent_film_consumer_pipeline.go` |

## 4. 数据和业务来源

| 目标 | 来源 |
| --- | --- |
| MAA 对应数据库状态 | `docs/v1.5.2/agent-film-数据库与状态模型.md` |
| 对外请求和响应契约 | `docs/v1.5.2/agent-film-接口与数据契约.md` |
| 完整业务流程 | `docs/v1.5.2/agent-film-业务流程与代码地图.md` |
| 故障和恢复行为 | `docs/v1.5.2/agent-film-排障手册与风险清单.md` |
| 最终视频字段映射 | `docs/v1.5/agent-film-maa-artifact-field-mapping.md` |
| 数据库迁移 | `sql/v1.5_agent_film.sql` 和后续 `sql/*agent_film*.sql` |

## 5. 前端来源

仓库：`D:\dx\wise-cut`

| 目标 | 来源 |
| --- | --- |
| Agent API 类型和请求 | `src/api/agent-film*`、`src/api/*agent-film*` |
| 会话状态和事件流 | `src/views/creation/agent-film-workbench/detail/hooks/` |
| Interaction 卡片解析 | `src/views/creation/agent-film-workbench/detail/hooks/detailData.ts` |
| Interaction 提交 | `src/views/creation/agent-film-workbench/detail/hooks/useAgentFilmInteractions.ts` |
| 卡片组件 | `src/views/creation/agent-film-workbench/detail/components/cards/` |
| 前端 intent 文案 | `src/locale/bundles/route-agent-film-workbench-detail/` |

## 6. 事实核对顺序

当文档、测试和代码不一致时，按以下顺序核对：

1. 当前 Go Client 的实际 JSON 序列化和反序列化。
2. 当前 Go Service 的状态判断和副作用。
3. 当前前端 TypeScript 类型和组件实际读取字段。
4. 已运行的契约/E2E 测试。
5. 说明文档。

发现差异必须记录在 `execution.md`，不能直接选择对实现最方便的版本。
