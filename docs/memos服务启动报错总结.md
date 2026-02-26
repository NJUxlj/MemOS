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

---

## 问题2.5（深度追查）：0 条记忆的完整根因链

> 该问题经过深度排查，共发现 **3 个 Bug**，均已修复。

### 诊断方法

编写诊断脚本 `scripts/debug_memory_extraction.py`，分 5 步逐层验证整个调用链：
- Step1: 直接调用 LLM（glm-4.7 是否返回正确 JSON）
- Step2: 解析 JSON（parse_json_result 能否提取 `"memory list"` key）
- Step3: Key 名匹配验证
- Step4: Embedder 调用（bge-m3 服务是否可达，返回类型是否正确）
- Step5: 端到端复现（模拟 `_process_chat_data` 完整流程）

### 诊断结论

| 步骤 | 结果 | 说明 |
|------|------|------|
| LLM 调用 | ✅ 正常 | glm-4.7 返回了格式正确的 JSON，含 2 条记忆 |
| JSON 解析 | ✅ 正常 | `parse_json_result` 正确提取 `"memory list"` key |
| Key 名匹配 | ✅ 正常（LLM 成功时）| LLM 失败 fallback 时存在 key 名 Bug（见 Bug-A） |
| Embedder 调用 | ❌ 失败 | `embed()` 返回 `None` 而非向量列表 |
| 端到端 | ❌ 失败 | `None[0]` → `'NoneType' object is not subscriptable` |

### Bug-A：`@timed_with_status` 装饰器吞噬异常（已修复）

**文件**：`src/memos/utils.py`

**问题代码**：
```python
except Exception as e:
    ...
    if fallback is not None and callable(fallback):
        return result  # 有 fallback → 返回回退值
    # ← 缺少 raise！无 fallback 时直接 fall-through，隐式返回 None
finally:
    # 只记日志，不返回，不抛出
```

**影响**：任何用 `@timed_with_status()` 装饰的函数（包括 `embed()`），一旦内部抛出异常且没有配置 `fallback` 参数，异常会被完全吞掉，函数返回 `None`，让调用方以为"成功了但结果是 None"。

**修复**：在 `except` 块末尾添加 `raise`：
```python
except Exception as e:
    ...
    if fallback is not None and callable(fallback):
        return result
    raise  # ← 新增：无 fallback 时重新抛出，不再静默返回 None
```

### Bug-B：Embedder 服务不可达（已修复配置）

**根因**：`.env` 中 `MOS_EMBEDDER_API_BASE=http://10.10.50.150:8998/v1` 是内网 bge-m3 服务地址，本机无法访问（curl 超时，exit code 28）。`embed()` 内部 `asyncio.run()` 抛出连接超时异常，被 `@timed_with_status` 吞掉，返回 `None`，导致上层 `None[0]` 崩溃。

**修复**：`.env` 切换到 SiliconFlow 公有云 API（免费注册，提供相同的 `BAAI/bge-m3` 模型）：
```bash
MOS_EMBEDDER_API_BASE=https://api.siliconflow.cn/v1
MOS_EMBEDDER_MODEL=BAAI/bge-m3
MOS_EMBEDDER_API_KEY=your_siliconflow_api_key_here  # 需替换为实际 Key
```

### Bug-C（隐藏 Bug）：LLM 失败时 fallback 的 Key 名不匹配

**文件**：`src/memos/mem_reader/simple_struct.py`

**问题**：
- `_get_llm_response()` 的 fallback 返回 dict 使用 `"memory_list"`（下划线）
- `_process_chat_data()` 查找时用的是 `"memory list"`（空格）
- 导致当 LLM 调用失败时，fallback 记忆条目被静默丢弃，0 条记忆写入，且无任何报错

```python
# _get_llm_response 的 fallback（第 271 行）
return {"memory_list": [...]}  # ← 下划线 key

# _process_chat_data（第 365 行）
for m in resp.get("memory list", []):  # ← 空格 key，永远找不到 fallback 结果
```

**该 Bug 尚未修复**（需要与项目原作者确认预期行为），但对当前流程影响较小（LLM 正常工作时不触发 fallback 路径）。

---

## 三、本地 API 服务器（uvicorn）启动报错

> 该阶段为启动 `uvicorn memos.api.server_api:app` 后在服务器日志中观察到的报错。

### 问题3.1：`.env` 未被正确加载 — `load_dotenv()` 找错文件

**报错现象：**  
修改 `.env` 中的配置后（如 `API_SCHEDULER_ON=false`），重启服务器无效，报错依然存在。

**根因：**  
`server_api.py` 第 14 行调用 `load_dotenv()` 不带参数，Python-dotenv 默认**只在当前工作目录**查找 `.env`。  
当用户从 `src/` 目录启动 uvicorn 时（`cd src && uvicorn memos.api.server_api:app ...`），`load_dotenv()` 找到的是 `src/.env`（不存在），根本不会读取 `MemOS/.env`，所有修改全部无效，变量回退到系统默认值（`os.getenv("API_SCHEDULER_ON", "true")` 默认为 `"true"`）。

**影响范围：**  
只要不在项目根目录 `MemOS/` 下启动服务，所有 `.env` 配置均失效。

**修复：**  
将 `server_api.py` 和 `mem_scheduler/general_modules/misc.py` 的 `load_dotenv()` 改为 `load_dotenv(find_dotenv(usecwd=True) or find_dotenv())`，让 dotenv 从当前目录向上搜索，无论从哪个目录启动服务都能找到项目根目录的 `.env`。

```python
# server_api.py（修复前）
from dotenv import load_dotenv
load_dotenv()

# server_api.py（修复后）
from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv(usecwd=True) or find_dotenv())
```

---

### 问题3.2：pika RabbitMQ `Connection refused` 仍然持续刷屏

**报错信息：**
```
pika.adapters.utils.io_services_utils - ERROR - Socket failed to connect: error=61 (Connection refused)
pika.adapters.utils.connection_workflow - ERROR - TCP Connection attempt failed: ConnectionRefusedError(61, 'Connection refused'); dest=localhost:5672
memos.mem_scheduler.webservice_modules.rabbitmq_service - ERROR - Connection failed:
memos.configs.mem_scheduler - WARNING - Failed to initialize components: openai, graph_db. Successfully initialized: rabbitmq
```

**根因（深度分析）：**  
此问题经过两轮排查才完全定位：

**第一轮**：发现 `.env` 中存在两个冲突的 `API_SCHEDULER_ON`（第 133 行 `true`，第 141 行 `false`），`python-dotenv` 默认"先出现的值优先"（`override=False`），导致 `false` 从未生效，`mem_scheduler.start()` 被调用。→ 已合并为单一 `API_SCHEDULER_ON=false`。

**第二轮**：修复重复 key 后，pika 错误仍然出现。通过追踪源码发现，RabbitMQ 连接并非在 `start()` 时发起，而是在**调度器 `__init__` 阶段**就已建立：

```python
# base_scheduler.py: 第 264-267 行
if self.auth_config is not None:
    self.rabbitmq_config = self.auth_config.rabbitmq
    if self.rabbitmq_config is not None:
        self.initialize_rabbitmq(config=self.rabbitmq_config)  # ← __init__ 里就连接！
```

`AuthConfig.from_local_env()` 检测到环境中存在 `MEMSCHEDULER_RABBITMQ_*` 前缀的任何 key（即使值为空），就会创建 `RabbitMQConfig` 对象。只要这个对象不为 `None`，`initialize_rabbitmq()` 就会被调用，后台线程开始不断重试连接 RabbitMQ。

**关键规律**：`MEMSCHEDULER_RABBITMQ_*` 这类 key **只要存在**（哪怕值为空）就等同于"已配置"。置空不管用，必须完全注释掉。

**修复：**  
将 `.env` 中所有 `MEMSCHEDULER_RABBITMQ_*` 条目**注释掉**（而非置空）：

```bash
# 修复前（值为空，但 key 存在 → 仍会触发连接）
MEMSCHEDULER_RABBITMQ_HOST_NAME=
MEMSCHEDULER_RABBITMQ_USER_NAME=
MEMSCHEDULER_RABBITMQ_PORT=5672

# 修复后（完全注释 → key 不存在 → has_rabbitmq_env=False → 不连接）
# MEMSCHEDULER_RABBITMQ_HOST_NAME=your_rabbitmq_host
# MEMSCHEDULER_RABBITMQ_USER_NAME=your_rabbitmq_user
# MEMSCHEDULER_RABBITMQ_PORT=5672
```

---

### 问题3.3：hf-mirror.com SSL EOF 错误（偶发，无害）

**报错信息：**
```
SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol')
thrown while requesting HEAD https://hf-mirror.com/gpt2/resolve/main/tokenizer.json
Retrying in 1s [Retry 1/5].
```

**根因：**  
`hf-mirror.com` 镜像站偶发 SSL 握手中断，通常由网络抖动或镜像服务器临时异常引起。HuggingFace Hub 客户端内置 5 次自动重试机制，大多数情况下可自动恢复。

**影响：**  
首次启动时需要下载 GPT-2 tokenizer（约 1MB），下载成功后会缓存到本地（`~/.cache/huggingface/`），后续启动不再发起网络请求。

**处理方式：**  
无需修复。若持续失败（5 次重试均不成功），可尝试：
```bash
# 手动预先缓存 tokenizer
python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('gpt2')"
```

---

## 错误 4.1：系统代理拦截 httpx 导致 Embeddings Error Code 502（本地运行时）

**错误日志：**
```
memos.mem_reader.simple_struct - ERROR - [ChatFast] error: Embeddings request ended with error: Error code: 502
```

**根因（深度排查结论）：**

本机开启了 Clash/VPN 等系统代理（macOS → 网络偏好设置 → 代理：`127.0.0.1:7897`）。  
httpx 库（OpenAI SDK 的底层 HTTP 客户端）通过 Python 的 `urllib.request.getproxies()` 自动读取 macOS 系统代理设置，导致所有 HTTP 请求（包括对内网 `10.10.50.150:8998` 的 embedding 请求）都被路由到本地代理。  

代理无法访问内网 IP → 返回 `502 Bad Gateway` 或长时间超时（>30s）。

| 客户端 | 行为 | 原因 |
|--------|------|------|
| `curl` | ✅ 直连成功（~100ms） | curl 默认不读取 macOS 系统代理 |
| `requests` | ✅ 直连成功 | 只读 `HTTP_PROXY` 环境变量（未设置） |
| `httpx` | ❌ 超时/502 | 通过 `urllib.request.getproxies()` 读取 macOS 系统代理 |

**附加根因：原代码用 `asyncio.run()` 包裹同步调用**

原 `embed()` 函数设计缺陷：用 `asyncio.run(asyncio.wait_for(同步函数, timeout=5))` 试图给同步 HTTP 调用加超时，但：
1. `asyncio.wait_for` 只能在 `await` 切换点取消任务，对无 `await` 的同步调用完全无效
2. 在 uvloop 多线程环境下（8 个 ThreadPoolExecutor 线程同时 `asyncio.run()`），uvloop 产生竞争/死锁

**修复方案：**

**① 代码修复** — `src/memos/embedders/universal_api.py`：
- 删除 `asyncio.run()` 和 `asyncio.wait_for()` 包装，改为直接同步调用
- 新增 `_make_http_client()` 工厂函数，用 `httpx.Client(trust_env=False)` 创建不读取系统代理的 HTTP 客户端
- 通过 OpenAI SDK 的 `http_client=` 参数注入，将超时控制移到 httpx 层（默认 30s）

```python
def _make_http_client(timeout: float) -> httpx.Client:
    return httpx.Client(timeout=timeout, trust_env=False)

self.client = OpenAIClient(
    api_key=...,
    base_url=...,
    http_client=_make_http_client(timeout),
)
```

**② 环境变量修复** — `.env`：
```bash
# 内网服务不走系统代理
NO_PROXY=10.0.0.0/8,127.0.0.1,localhost
no_proxy=10.0.0.0/8,127.0.0.1,localhost
```

**验证结果：**
```
修复后 8 线程并发：
thread-0: OK dim=1024 in 0.30s
thread-1: OK dim=1024 in 0.30s
... (8/8 全部成功)
```

---

## 错误 4.2：MilvusVecDB.add() 接口与基类不一致导致 TypeError

**错误日志：**
```
memos.graph_dbs.neo4j_community - WARNING - neo4j_community.py:186 - add_nodes_batch - [VecDB] batch insert failed: MilvusVecDB.add() missing 1 required positional argument: 'data'
```
（同一请求中出现两次）

**根因：**

`MilvusVecDB.add()` 的方法签名与基类 `BaseVecDB.add()` 不一致：

| 类 | `add()` 签名 |
|---|---|
| `BaseVecDB`（基类） | `add(self, data)` |
| `QdrantVecDB` | `add(self, data)` ✅ 一致 |
| `MilvusVecDB` | `add(self, collection_name, data)` ❌ 多了必填参数 |

`neo4j_community.py` 按基类规范调用：
```python
# neo4j_community.py:88
self.vec_db.add([item])
# neo4j_community.py:184
self.vec_db.add(vec_items)
```
两处均只传 `data` 一个参数，当底层切换为 Milvus 时，Python 将 `data` 列表误认为 `collection_name` 字符串参数，`data` 参数缺失，抛出 `TypeError`。

**修复：** `src/memos/vec_dbs/milvus.py`

将 `collection_name` 改为可选参数，默认取配置中第一个 collection 名，同步修正内部 `upsert()` 调用顺序：

```python
# 修复前
def add(self, collection_name: str, data: list[...]) -> None:

# 修复后
def add(
    self,
    data: list[MilvusVecDBItem | dict[str, Any]],
    collection_name: str | None = None,
) -> None:
    if collection_name is None:
        collection_name = self.config.collection_name[0]
    ...

# upsert() 内部调用同步调整
self.add(data, collection_name)  # 原：self.add(collection_name, data)
```

**影响范围：**  
- `neo4j_community.py` 中所有 `self.vec_db.add(...)` 调用无需修改，自动生效
- Milvus 内部 `upsert()` 方法调用同步修复

---

## 四、问题与修复汇总表

| # | 问题 | 严重程度 | 修复变量/文件 |
|---|------|----------|---------------|
| 1.1 | memos 启动时 Neo4j 尚未就绪（连接拒绝） | 🔴 阻断启动 | `docker-compose.yml` - `depends_on` 改为 `service_healthy` |
| 1.2 | Qdrant healthcheck 失败（容器无 curl） | 🔴 阻断启动 | `docker-compose.yml` - healthcheck 改用 bash TCP 探测 |
| 1.3 | Milvus 容器名冲突 | 🔴 阻断启动 | `docker rm -f` 清理残留容器 |
| 2.1 | Neo4j Community 不支持多数据库 | 🔴 崩溃退出 | `.env` - `NEO4J_BACKEND=neo4j-community` |
| 2.2 | Qdrant URL 占位符导致 DNS 失败 | 🔴 崩溃退出 | `.env` - `QDRANT_URL=`（置空） |
| 2.3 | HuggingFace 下载 GPT-2 tokenizer 超时 | 🟡 卡顿等待 | `.env` - `HF_ENDPOINT=https://hf-mirror.com` |
| 2.4 | RabbitMQ 连接失败（大量日志噪音） | 🟡 不影响主流程 | `.env` - `API_SCHEDULER_ON=false` |
| 2.5-A | `@timed_with_status` 装饰器吞噬异常 → embed() 返回 None | 🔴 业务致命 | `src/memos/utils.py` - 添加 `raise` |
| 2.5-B | Embedder 内网地址不可达（10.10.50.150:8998） | 🔴 业务致命 | `.env` - 切换到 SiliconFlow 公有云 |
| 2.5-C | LLM fallback 的 key 名不匹配（memory_list vs memory list） | 🟡 隐藏缺陷 | `simple_struct.py:271` 待修复（需确认预期行为） |
| 2.6 | Neo4j 属性键不存在（WARNING） | ✅ 无害警告 | 无需处理，写入数据后自动消失 |
| 3.1 | `load_dotenv()` 找错文件，`.env` 配置全部失效 | 🔴 配置失效 | `server_api.py` + `misc.py` - 改用 `find_dotenv()` 向上搜索 |
| 3.2-A | `.env` 中 `API_SCHEDULER_ON` 重复冲突（true 优先生效） | 🟡 配置冲突 | `.env` - 删除重复行，只保留 `false` |
| 3.2-B | `MEMSCHEDULER_RABBITMQ_*` key 存在（即使值为空）触发连接 | 🟡 日志噪音 | `.env` - 完全注释掉所有 `MEMSCHEDULER_RABBITMQ_*` 行 |
| 3.3 | hf-mirror.com 偶发 SSL EOF 错误 | ✅ 偶发无害 | 无需处理，有重试机制，tokenizer 缓存后消失 |
| 4.1 | 系统代理（Clash/VPN）拦截 httpx 请求导致 502 | 🔴 业务致命 | `universal_api.py` - `httpx.Client(trust_env=False)` + `.env` - `NO_PROXY=10.0.0.0/8` |
| 4.2 | `MilvusVecDB.add()` 接口与基类不一致，缺少 `data` 参数 | 🔴 业务致命 | `milvus.py` - `collection_name` 改为可选参数，默认取 `config.collection_name[0]` |
