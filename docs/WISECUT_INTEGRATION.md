# WiseCut 四仓库联调指南

## 1. 服务拓扑

```text
wise-cut :8080 -> wisecut API :10620 -> MAA Agent :10728
wisecut API -> MySQL :13306 / Redis :16381
wisecut task agent_film_consumer -> MAA SSE -> WiseCut MySQL
oss-admin :8082 -> wisecut API :10620
```

`agent_film_consumer` 与 MAA Agent 是两个不同的角色：

- `wisecut-agent` 的 Worker 执行 LangGraph，并产生 MAA 事件。
- `wisecut task agent_film_consumer` 消费 MAA SSE，并把事件落到 WiseCut MySQL，供用户端和运营后台读取。
- 只启动 Go API 不会消费 MAA 事件；只启动 MAA Agent 也不会更新 WiseCut 项目状态。

## 2. 本地服务清单

| 服务 | 地址或说明 |
| --- | --- |
| wise-cut | `http://localhost:8080` |
| wisecut API | `http://localhost:10620` |
| wisecut consumer | 独立后台进程，无浏览器端口 |
| oss-admin | `http://localhost:8082` |
| wisecut-agent | `http://localhost:10728` |
| PostgreSQL | `localhost:15432` |
| RabbitMQ | `localhost:15675` / `localhost:15676` |
| Redis | `localhost:16381` |
| MinIO | `localhost:19000` / `localhost:19001` |
| MySQL | `localhost:13306` |

实际端口以最终 `compose.yaml` 和 WiseCut `docker-compose.yml` 为准；文档中的端口不能替代配置检查。

## 3. 启动顺序

### 3.1 Agent

在 `D:\dx\wisecut-agent` 执行 `docker compose --profile local-demo up -d --build`，然后访问 `http://localhost:10728/health`。

### 3.2 WiseCut API 和 Consumer

在 `D:\dx\wisecut` 启动 MySQL、Redis、RabbitMQ 和 API。`agent_film_consumer` 必须作为独立常驻服务运行，不能只启动 Go API。

当前 Go Consumer 入口是 `wisecut task agent_film_consumer`，本地 Make 目标是 `make run-consumer-dev`。最终四仓库 Compose 必须包含独立的 `agent-film-consumer` 服务，并配置 API 健康依赖。

如果 CLI 不接受配置参数透传，则使用项目实际支持的 `APP_ENV` 或配置启动方式，并在 `execution.md` 记录真实命令，不能保留无法运行的伪命令。

### 3.3 前端

在 `D:\dx\wisecut` 执行 `docker compose up -d --build wise-cut oss-admin`，然后访问用户端和运营后台。

## 4. 联调配置

WiseCut API 的本地 `[agent_film]` 必须关闭 mock，并指向 Docker 网络中的 Agent 服务：`mock = false`、`python_base_url = "http://maa-agent:10728"`，路径保持 `/conversations`、`/runs`、`/approvals` 和 `/events`。

如果 API 在宿主机直接运行，使用 `http://localhost:10728`；如果 API 在 Compose 网络中运行，使用服务名，不要使用容器内的 `localhost`。

## 5. 最小验收路径

1. 登录用户端并打开 Agent Film 工作台。
2. 输入商品描述或示例链接。
3. 确认 `conversation_id` 和 `run_id` 已创建。
4. 确认 Agent 服务出现 `run.started`。
5. 确认 Consumer 收到 SSE 并写入 `agent_film_event`。
6. 确认页面出现商品上下文交互卡片并提交答案。
7. 确认 Graph 通过 Checkpoint 恢复，并出现脚本/分镜卡片。
8. 确认最终出现 `business.message` 且 `business_key=final_video`。
9. 确认 Go Consumer 将最终视频写入 `creative_project`。
10. 断开浏览器后用 `after_seq` 重连，确认事件不重复。

## 6. 排障路径

页面无进度时，依次检查 MAA `/health`、`maa-agent` 日志、`agent-film-consumer` 日志、Redis 单例锁和 MySQL 的 `agent_film_run.remote_last_seq`。

会话创建成功但没有事件时，检查 MAA 是否创建 Run、Agent 事件存储是否增长、Consumer 游标是否推进，以及容器内 MAA URL 是否错误地使用了 `localhost`。

事件重复时，检查 `conversation_id + run_id + seq` 唯一约束、Consumer 是否多实例运行、SSE `after_seq` 的序列域和 Outbox/RabbitMQ 幂等键。

最终视频没有回写时，检查 `business.message` 的 `business_key=final_video`、视频 URL 交付校验、Go Consumer terminal event 和 `creative_project` 状态。

## 7. 联调证据

完成四仓库联调时，必须在 `execution.md` 记录各容器和进程的启动命令、`/health`/`/ready`/Go `/api/health` 输出、Conversation/Run/Event/Artifact ID、Consumer 日志、MySQL 查询结果、SSE 断线重连结果，以及所有关联仓库的 commit。
