# MemOS 服务启动报错总结

> 记录日期：2026-02-25  
> 环境：macOS + Docker Compose + conda 虚拟环境（memos / Python 3.12）

---

## 一、Docker 服务启动阶段

### 1.1 memos-api-docker 启动时 Neo4j 连接拒绝

**报错信息：**
```
neo4j.exceptions.ServiceUnavailable: Couldn't connect to neo4j-docker:7687
Failed to establish connection to ResolvedIPv4Address(('192.168.117.3', 7687))
(reason [Errno 111] Connection refused)
```

**根因：**  
`docker-compose.yml` 中 `memos` 服务的 `depends_on` 使用了简单列表形式，这只等依赖容器**进程启动**，不等服务**健康就绪**。Neo4j 的 Bolt 端口（7687）需要约 10 秒才能完全就绪，`memos` 容器已经启动并立即尝试连接，导致 `Connection refused`。

**修复方案：**  
将 `memos` 的 `depends_on` 全部改为 `condition: service_healthy`，强制等待所有依赖服务健康检查通过后再启动：

```yaml
# docker-compose.yml
depends_on:
  neo4j:
    condition: service_healthy
  qdrant:
    condition: service_healthy
  milvus:
    condition: service_healthy
```

---

### 1.2 Qdrant 健康检查失败（unhealthy）

**报错信息：**
```
qdrant-docker   Up (unhealthy)
OCI runtime exec failed: exec: "curl": executable file not found in $PATH
```

**根因：**  
给 Qdrant 配置的 `healthcheck` 命令使用了 `curl`，但 `qdrant/qdrant:v1.15.3` 是精简镜像，容器内**既没有 `curl` 也没有 `wget`**。由于 Qdrant 未通过健康检查，`memos` 服务（依赖 `condition: service_healthy`）始终无法启动。

**修复方案：**  
改用 bash 内置的 TCP 端口探测，不依赖任何外部工具：

```yaml
# docker-compose.yml - qdrant 服务
healthcheck:
  test: ["CMD-SHELL", "bash -c ':> /dev/tcp/127.0.0.1/6333' || exit 1"]
  interval: 5s
  timeout: 5s
  retries: 10
  start_period: 5s
```

---

### 1.3 Milvus 相关容器名冲突

**报错信息：**
```
Error response from daemon: Conflict. The container name "/milvus-etcd" is already in use
Error response from daemon: Conflict. The container name "/milvus-minio" is already in use
```

**根因：**  
上一次 `docker compose down` 只清理了当前 compose 项目管理的容器，而 `milvus-etcd`、`milvus-minio` 等是**游离容器**（残留自上一次不完整的启动），Docker Compose 无法覆盖已存在的同名容器。

**修复方案：**  
先用 `--remove-orphans` 清理游离容器，再手动删除残留 Milvus 容器：

```bash
# 清理 compose 管理的容器及游离容器
docker compose down --remove-orphans

# 手动删除残留 Milvus 容器
docker rm -f milvus-etcd milvus-minio milvus-standalone milvus-attu

# 重新启动
docker compose up -d
```

---

## 二、本地 Python 脚本运行阶段

### 2.1 Neo4j Community Edition 不支持多数据库

**报错信息：**
```
neo4j - WARNING - Could not create database 'memosdefault' because this Neo4j instance
(likely Community Edition) does not support administrative commands.
neo4j.exceptions.ClientError: {code: Neo.ClientError.Database.DatabaseNotFound}
{message: Graph not found: memosdefault}
```

**根因：**  
`.env` 中 `NEO4J_BACKEND=neo4j`（企业版模式），代码会尝试创建自定义数据库 `memosdefault`，但 Docker 里运行的是 **Community Edition**，不支持多数据库（只有默认的 `neo4j` 数据库）。

**修复方案：**  
将 `.env` 中的 Neo4j 后端改为 Community 模式：

```bash
# .env
NEO4J_BACKEND=neo4j-community   # neo4j-community | neo4j | nebular | polardb
NEO4J_DB_NAME=neo4j             # Community Edition 只能使用默认数据库
```

---

### 2.2 Qdrant 连接失败（QDRANT_URL 占位符未清空）

**报错信息：**
```
httpx.ConnectError: [Errno 8] nodename nor servname provided, or not known
qdrant_client.http.exceptions.ResponseHandlingException: [Errno 8] ...
```

**根因：**  
`.env` 中存在未清理的占位符：
```bash
QDRANT_URL=your_qdrant_url   # ← 占位符！
```
Qdrant 客户端收到非空的 `url` 参数时会**完全忽略** `host` / `port`，直接用 `url` 发起连接，导致 DNS 解析失败（`your_qdrant_url` 不是合法域名）。

**修复方案：**  
将 `QDRANT_URL` 和 `QDRANT_API_KEY` 置空（仅在使用 Qdrant Cloud 时才需要填写）：

```bash
# .env
QDRANT_URL=
QDRANT_API_KEY=
QDRANT_HOST=localhost   # 本地开发时用 host + port 模式
QDRANT_PORT=6333
```

---

### 2.3 HuggingFace 下载 GPT-2 Tokenizer 超时

**报错信息：**
```
MaxRetryError("HTTPSConnectionPool(host='huggingface.co', port=443):
Max retries exceeded ... Caused by ConnectTimeoutError ... 'Connection to huggingface.co timed out.'")
Retrying in 1s [Retry 1/5] ... Retrying in 2s [Retry 2/5] ...
```

**根因：**  
`SentenceChunker` 使用 `chonkie` 库，配置了 `tokenizer="gpt2"`，`chonkie` 通过 `huggingface_hub` 在首次使用时自动从 HuggingFace 下载 GPT-2 词表文件。国内网络无法直连 `huggingface.co`，导致超时。

**调用链：**
```
SentenceChunker(tokenizer="gpt2")
  └── chonkie.SentenceChunker
        └── huggingface_hub.snapshot_download("gpt2/tokenizer.json")
              └── GET https://huggingface.co/gpt2/... → 超时
```

**修复方案：**  
在 `.env` 中配置 HuggingFace 国内镜像（`huggingface_hub` 原生支持此环境变量）：

```bash
# .env
HF_ENDPOINT=https://hf-mirror.com
```

> **注意**：GPT-2 tokenizer 文件下载成功后会缓存到 `~/.cache/huggingface/`，后续运行不再需要联网。

---

### 2.4 RabbitMQ 连接反复失败（大量 pika ERROR 噪音）

**报错信息：**
```
pika ERROR - TCP Connection attempt failed: ConnectionRefusedError(61, 'Connection refused')
dest=localhost:5672
AMQPConnectionWorkflowFailed: 6 exceptions in all
```

**根因：**  
`init_server()` 中调度器默认自动启动（`API_SCHEDULER_ON` 默认 `true`），`OptimizedScheduler` 内部包含 RabbitMQ 服务模块，启动后会持续尝试连接 AMQP（端口 5672）。`.env` 中 `MEMSCHEDULER_RABBITMQ_HOST_NAME=`（空值），pika 回退到 `localhost:5672`，但本地没有运行 RabbitMQ，触发大量重试日志。

**修复方案（本地开发）：**  
在 `.env` 中关闭调度器自动启动：

```bash
# .env
API_SCHEDULER_ON=false   # 本地开发关闭；生产环境需要异步调度时改为 true 并配置 RabbitMQ
```

> 如果生产环境需要使用调度器，可在 `docker-compose.yml` 中加入 RabbitMQ 服务，并配置 `MEMSCHEDULER_RABBITMQ_HOST_NAME`。

---

### 2.5 记忆提取返回 0 条（LLM 解析异常）

**报错信息：**
```
memos.mem_reader.simple_struct - ERROR - [ChatFine] parse error: 'NoneType' object is not subscriptable
✓ Added 0 memories
✓ Exported 0 nodes
```

**根因：**  
`add_memories()` 调用 `mem_reader` 以 Fine 模式提取记忆，流程如下：

```
add_memories()
  └── mem_reader._process_chat_data()  (Fine 模式)
        └── self._get_llm_response(text)     ← 调用 LLM（MEMRADER_MODEL）
              └── 返回 None 或结构异常的 JSON
                    └── resp.get("memory list", []) 中 m 为 None
                          └── TypeError: 'NoneType' object is not subscriptable
```

LLM（`glm-4.7`）对 mem_reader 的提取 Prompt 返回了 `None` 或格式不符合预期的响应，导致解析崩溃，最终 0 条记忆被写入。

**排查方向：**
1. 确认 `MEMRADER_API_KEY` / `MEMRADER_API_BASE` / `MEMRADER_MODEL` 三者配置正确
2. 检查模型是否支持 mem_reader 所用的 Prompt 格式（要求返回特定 JSON 结构）
3. 开启 DEBUG 日志观察完整 LLM 响应内容

```bash
# .env - 确认这三项配置
MEMRADER_MODEL=glm-4.7
MEMRADER_API_KEY=<your_key>
MEMRADER_API_BASE=https://open.bigmodel.cn/api/paas/v4
```

---

### 2.6 Neo4j 属性键不存在警告（无害）

**报错信息：**
```
Neo.ClientNotification.Statement.UnknownPropertyKeyWarning
The provided property key is not in the database (missing: status / id)
```

**根因：**  
数据库全新，尚未写入任何 `Memory` 节点，图中不存在 `status`、`id` 等属性键，Neo4j 以 WARNING 级别提示查询引用了不存在的属性。

**处理方式：**  
**无需处理**。随着记忆数据写入，这些属性键会自动创建，WARNING 消失。

---

## 三、问题与修复汇总表

| # | 问题 | 严重程度 | 修复变量/文件 |
|---|------|----------|---------------|
| 1.1 | memos 启动时 Neo4j 尚未就绪（连接拒绝） | 🔴 阻断启动 | `docker-compose.yml` - `depends_on` 改为 `service_healthy` |
| 1.2 | Qdrant healthcheck 失败（容器无 curl） | 🔴 阻断启动 | `docker-compose.yml` - healthcheck 改用 bash TCP 探测 |
| 1.3 | Milvus 容器名冲突 | 🔴 阻断启动 | `docker rm -f` 清理残留容器 |
| 2.1 | Neo4j Community 不支持多数据库 | 🔴 崩溃退出 | `.env` - `NEO4J_BACKEND=neo4j-community` |
| 2.2 | Qdrant URL 占位符导致 DNS 失败 | 🔴 崩溃退出 | `.env` - `QDRANT_URL=`（置空） |
| 2.3 | HuggingFace 下载 GPT-2 tokenizer 超时 | 🟡 卡顿等待 | `.env` - `HF_ENDPOINT=https://hf-mirror.com` |
| 2.4 | RabbitMQ 连接失败（大量日志噪音） | 🟡 不影响主流程 | `.env` - `API_SCHEDULER_ON=false` |
| 2.5 | LLM 解析记忆返回 0 条 | 🟡 业务异常 | 排查 `MEMRADER_*` 配置和模型输出格式 |
| 2.6 | Neo4j 属性键不存在（WARNING） | ✅ 无害警告 | 无需处理，写入数据后自动消失 |
