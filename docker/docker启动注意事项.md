# Docker 启动注意事项

> 本文记录 MemOS 本地开发环境下各 docker-compose 文件的配置说明、启动顺序和常见坑。

---

## 一、文件说明

| 文件 | project name | 用途 |
|------|-------------|------|
| `docker-compose.yml` | `memos-dev` | 主服务栈：memos-api、neo4j、qdrant、milvus（含 etcd/minio）、attu |
| `docker-compose.redis.yml` | `memos-dev` | Redis 扩展栈：redis 本体 + RedisInsight 看板 |
| `docker-compose.rabbitmq.yml` | `memos-dev` | RabbitMQ 扩展栈：rabbitmq 本体（含 Management UI） |

> **注意**：所有文件的 `name` 均为 `memos-dev`，属于同一个 Docker Compose 项目。执行 `docker compose down` 时若不指定 `-f`，默认只操作当前目录下的 `docker-compose.yml`，不会影响其他扩展栈，反之亦然。

---

## 二、服务端口速查

| 服务 | 容器名 | 宿主机端口 | 说明 |
|------|--------|-----------|------|
| memos API | `memos-api-docker` | 8000 | FastAPI 主服务 |
| Neo4j HTTP | `neo4j-docker` | 7474 | Web 管理界面 |
| Neo4j Bolt | `neo4j-docker` | 7687 | SDK 连接地址 |
| Qdrant REST | `qdrant-docker` | 6333 | 向量库 REST API |
| Qdrant gRPC | `qdrant-docker` | 6334 | 向量库 gRPC |
| Milvus | `milvus-standalone` | 19530 | 向量库 SDK |
| Milvus metrics | `milvus-standalone` | 9091 | healthz 端点 |
| Attu | `milvus-attu` | 3000 | Milvus Web 看板 |
| MinIO S3 | `milvus-minio` | 9000 | 对象存储 API |
| MinIO Console | `milvus-minio` | 9001 | MinIO Web 控制台 |
| **Redis** | `redis-docker` | **6379** | Redis 本体 |
| **RedisInsight** | `redis-insight` | **5540** | Redis Web 看板 |
| **RabbitMQ** | `rabbitmq-docker` | **5672** | AMQP 协议端口（应用连接） |
| **RabbitMQ UI** | `rabbitmq-docker` | **15672** | Management Web 看板 |

---

## 三、启动顺序

两个 compose 文件共享 Docker 网络 `memos_network`，该网络由主 stack 负责创建，Redis stack 声明为 `external: true` 引用。因此**必须按以下顺序启动**：

### 方式 A：主 stack 先起，Redis stack 后起（推荐）

```bash
# 1. 启动主服务栈（会自动创建 memos_network）
docker compose -f docker/docker-compose.yml up -d

# 2. 启动 Redis 栈（复用已有网络）
docker compose -f docker/docker-compose.redis.yml up -d
```

### 方式 B：仅需要 Redis，不起主 stack

```bash
# 1. 手动创建共享网络
docker network create memos_network

# 2. 启动 Redis 栈
docker compose -f docker/docker-compose.redis.yml up -d
```

> **坑**：若 `memos_network` 不存在就直接启动 Redis stack，会报错：
> `network memos_network declared as external, but could not be found`

---

## 四、停止与清理

```bash
# 仅停止主 stack（不删 volume）
docker compose -f docker/docker-compose.yml down

# 仅停止 Redis stack
docker compose -f docker/docker-compose.redis.yml down

# 仅停止 RabbitMQ stack
docker compose -f docker/docker-compose.rabbitmq.yml down

# 停止所有 + 清除 volume（危险，数据会丢失）
docker compose -f docker/docker-compose.yml down -v
docker compose -f docker/docker-compose.redis.yml down -v

# 删除共享网络（两个 stack 都停止后才能删）
docker network rm memos_network
```

---

## 五、各看板首次配置

### RedisInsight

1. 浏览器访问 http://localhost:5540
2. 点击 **"Add Redis Database"**
3. 填写连接信息：
   - **Host**：`redis-docker`（容器名，在 Docker 网络内互通）
   - **Port**：`6379`
   - **Password**：（留空，未设密码）
4. 点击 **Add Redis Database** 确认

---

### RabbitMQ Management UI

1. 浏览器访问 http://localhost:15672
2. 登录信息：
   - **用户名**：`memos`
   - **密码**：`memos123`
3. Virtual Host 已默认创建为 `memos`，在页面顶部下拉框可切换查看

`.env` 中对应的连接配置（已填写）：

```
MEMSCHEDULER_RABBITMQ_HOST_NAME=localhost
MEMSCHEDULER_RABBITMQ_USER_NAME=memos
MEMSCHEDULER_RABBITMQ_PASSWORD=memos123
MEMSCHEDULER_RABBITMQ_VIRTUAL_HOST=memos
MEMSCHEDULER_RABBITMQ_PORT=5672
```

---

## 六、本地 Python 脚本连接注意事项

### 坑 1：系统代理导致本地服务连接失败（502 / Connection refused）

本机开启了系统级 HTTP 代理（`127.0.0.1:7897`，如 Clash），Python 的 `httpx` / `urllib` 会读取系统代理设置，但**不会**自动应用 macOS 的 no-proxy 例外规则，导致对 `localhost` 的请求也被转发给代理，进而出现：

- 访问 Qdrant（`localhost:6333`）→ `502 Bad Gateway`
- 访问 Redis（`localhost:6379`）→ `Connection refused`

**解决方案**：运行脚本前设置 `NO_PROXY` 环境变量，或在 `.env` 中添加（已写入）：

```bash
# 临时（命令行前缀）
NO_PROXY=localhost,127.0.0.1,::1 python your_script.py

# 永久（.env 文件，已配置）
NO_PROXY=localhost,127.0.0.1,::1
no_proxy=localhost,127.0.0.1,::1
```

### 坑 2：`CHAT_MODEL_LIST` 指向本地 LLM 端口

`.env` 中 `CHAT_MODEL_LIST` 原始占位配置指向 `http://localhost:1234`（LM Studio 默认端口），本地未启动该服务时会报：

```
httpcore.ConnectError: [Errno 61] Connection refused
openai.APIConnectionError: Connection error.
```

**已修复**：`CHAT_MODEL_LIST` 已改为复用 DashScope（qwen-max）API。

### 坑 3：`MEMSCHEDULER_REDIS_DB` 为空字符串导致 Redis 初始化失败

`.env` 中 `MEMSCHEDULER_REDIS_DB=`（有等号但值为空）时，`os.getenv()` 返回的是空字符串 `""`，而不是触发默认值 `"0"`，导致代码执行 `int("")` 抛出异常：

```
Failed to initialize Redis from environment variables:
  invalid literal for int() with base 10: ''
Failed to start local Redis server: [Errno 2] No such file or directory: 'redis-server'
ConnectionError: Not connected to Redis. Redis connection not available.
```

> **原理**：`os.getenv("KEY", "0")` 的默认值只在变量**完全未定义**时生效；变量已定义但值为空字符串时，返回 `""`，默认值不生效。

**已修复**：`.env` 中已设置 `MEMSCHEDULER_REDIS_DB=0`。

各 Redis 字段留空安全性说明：

| 字段 | 留空是否安全 | 正确处理方式 |
|------|------------|------|
| `MEMSCHEDULER_REDIS_PASSWORD=` | ✅ 安全 | 无密码时传 `None` 即可 |
| `MEMSCHEDULER_REDIS_TIMEOUT=` | ❌ **不安全** | 空字符串不等于 `None`，`float("")` 会在成功路径中崩溃，**应注释掉此行** |
| `MEMSCHEDULER_REDIS_CONNECT_TIMEOUT=` | ❌ **不安全** | 同上，**应注释掉此行** |
| `MEMSCHEDULER_REDIS_DB=` | ❌ **不安全** | `int("")` 无异常捕获，**必须填 `0`** |

> **已修复**：
> - `MEMSCHEDULER_REDIS_DB=0`（填具体值）
> - `MEMSCHEDULER_REDIS_TIMEOUT` 和 `MEMSCHEDULER_REDIS_CONNECT_TIMEOUT` 已注释掉（让 `os.getenv()` 真正返回 `None`）
> - 同时修复了 `redis_service.py` 第 206 行的 bug（成功路径中 `float()` 无保护）

### 坑 4：调度器对象存在但后台消费线程未启动

`API_SCHEDULER_ON=false` 时，`server_router.py` 初始化只创建调度器对象，不调用 `.start()`，导致任务提交后永远堆在队列里无人消费：

```
running=0, remaining=200  ← 任务不动，无限循环
```

**解决方案**：在调用脚本中，注册 handler 后手动调用一次 `mem_scheduler.start()`（已在 `run_async_tasks.py` 中添加）。

---

## 七、快捷命令速查

```bash
# 查看所有容器状态
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 查看 Redis 日志
docker logs redis-docker -f

# 用 redis-cli 连接测试
docker exec -it redis-docker redis-cli ping

# 查看网络中的容器
docker network inspect memos_network --format '{{range .Containers}}{{.Name}} {{end}}'
```
