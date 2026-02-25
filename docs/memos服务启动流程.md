# MemOS 服务启动流程

> 版本：2.0.6 (Stardust/星尘)  
> 更新时间：2026-02-25  
> 部署方式：Docker Compose

---

## 一、服务总览

MemOS 通过 `docker/docker-compose.yml` 编排以下 **7 个容器**，共同构成完整的运行环境：

| 容器名 | 镜像 | 对外端口 | 作用 |
|--------|------|----------|------|
| `memos-api-docker` | 本地构建 | `8000` | MemOS 主 API 服务（FastAPI） |
| `neo4j-docker` | `neo4j:5.26.4` | `7474`(HTTP) / `7687`(Bolt) | 图数据库，支持 TreeTextMemory |
| `qdrant-docker` | `qdrant/qdrant:v1.15.3` | `6333`(REST) / `6334`(gRPC) | 向量数据库（Qdrant） |
| `milvus-etcd` | `quay.io/coreos/etcd:v3.5.18` | — | Milvus 元数据存储 |
| `milvus-minio` | `minio/minio` | `9000`(S3) / `9001`(Console) | Milvus 对象存储 |
| `milvus-standalone` | `milvusdb/milvus:v2.5.4` | `19530`(SDK) / `9091`(metrics) | 向量数据库（Milvus） |
| `milvus-attu` | `zilliz/attu:v2.4` | `3000` | Milvus Web 管理看板 |

---

## 二、启动顺序与依赖关系

容器之间存在严格的启动依赖，Docker Compose 会按以下顺序拉起服务：

```
第 1 批（无依赖，并行启动）
  ├── milvus-etcd     ← Milvus 元数据存储
  ├── milvus-minio    ← Milvus 对象存储
  ├── neo4j-docker    ← 图数据库
  └── qdrant-docker   ← 向量数据库（Qdrant）

第 2 批（等待 etcd + minio 健康检查通过后启动）
  └── milvus-standalone

第 3 批（等待 milvus 健康检查通过后启动）
  └── milvus-attu     ← Milvus Web 看板

第 4 批（等待 neo4j + qdrant + milvus 启动后启动）
  └── memos-api-docker ← MemOS 主服务
```

> **注意**：`milvus-standalone` 配置了 `start_period: 90s`，首次启动初始化时间较长，请耐心等待。

---

## 三、快速启动

### 前置条件

- 已安装 Docker Desktop（或 Docker Engine + Docker Compose v2）
- 项目根目录存在 `.env` 文件（可参考 `.env.example`）

### 启动所有服务

```bash
cd MemOS/docker
docker compose up -d
```

### 查看启动状态

```bash
docker compose ps
```

所有容器的 `STATUS` 应显示为 `running` 或 `healthy`。

### 查看实时日志

```bash
# 查看所有服务日志
docker compose logs -f

# 只看 MemOS 主服务
docker compose logs -f memos

# 只看 Milvus
docker compose logs -f milvus
```

### 停止所有服务

```bash
docker compose down
```

### 停止并清除所有数据卷（慎用，数据不可恢复）

```bash
docker compose down -v
```

---

## 四、各服务详细说明

### 4.1 MemOS 主服务（memos-api-docker）

- **访问地址**：http://localhost:8000
- **API 文档**：http://localhost:8000/docs（Swagger UI）
- **源码挂载**：`../src` → `/app/src`（支持热更新）
- **配置来源**：读取项目根目录的 `.env` 文件

**关键环境变量（在 docker-compose.yml 中注入）：**

| 变量名 | 值 | 说明 |
|--------|----|------|
| `PYTHONPATH` | `/app/src` | Python 模块路径 |
| `HF_ENDPOINT` | `https://hf-mirror.com` | HuggingFace 镜像（国内加速） |
| `QDRANT_HOST` | `qdrant-docker` | Qdrant 容器内主机名 |
| `QDRANT_PORT` | `6333` | Qdrant REST API 端口 |
| `NEO4J_URI` | `bolt://neo4j-docker:7687` | Neo4j Bolt 连接地址 |
| `MILVUS_URI` | `http://milvus-standalone:19530` | Milvus SDK 连接地址 |
| `MILVUS_USER_NAME` | `root` | Milvus 用户名 |
| `MILVUS_PASSWORD` | `12345678` | Milvus 密码 |

---

### 4.2 Neo4j 图数据库（neo4j-docker）

- **Web 控制台**：http://localhost:7474
- **Bolt 连接**：`bolt://localhost:7687`
- **默认账号**：`neo4j` / `12345678`
- **用途**：支持 `TreeTextMemory`，存储记忆节点之间的关系图谱
- **数据持久化**：`neo4j_data` 卷（数据） + `neo4j_logs` 卷（日志）

---

### 4.3 Qdrant 向量数据库（qdrant-docker）

- **REST API**：http://localhost:6333
- **Web 控制台**：http://localhost:6333/dashboard
- **gRPC**：`localhost:6334`
- **用途**：支持 `GeneralTextMemory` 和 `PreferenceTextMemory` 的向量检索
- **数据持久化**：`qdrant_data` 卷

---

### 4.4 Milvus 向量数据库（milvus-standalone）

Milvus Standalone 模式依赖两个基础服务：

#### etcd（元数据存储）
- 容器名：`milvus-etcd`
- 存储 Milvus 的集合元信息、Schema 等
- 数据持久化：`etcd_data` 卷

#### MinIO（对象存储）
- 容器名：`milvus-minio`
- **MinIO Web Console**：http://localhost:9001（账号：`minioadmin` / `minioadmin`）
- 存储 Milvus 的向量数据段文件（Segment）
- 数据持久化：`minio_data` 卷

#### Milvus 主服务
- **SDK 连接地址**：`localhost:19530`
- **健康检查**：http://localhost:9091/healthz
- **用途**：支持 `PreferenceTextMemory`（偏好记忆）的向量存储与检索
- **配置来源**（见 `src/memos/api/config.py` → `get_milvus_config()`）：
  ```python
  {
      "uri": "http://milvus-standalone:19530",
      "user_name": "root",
      "password": "12345678",
      "collection_name": ["explicit_preference", "implicit_preference"],
      "vector_dimension": 1024,
      "distance_metric": "cosine"
  }
  ```
- 数据持久化：`milvus_data` 卷

---

### 4.5 Attu — Milvus Web 看板（milvus-attu）

- **访问地址**：http://localhost:3000
- **连接配置**：
  - Milvus Address：`milvus-standalone:19530`
  - 用户名：`root`
  - 密码：`12345678`
- **功能**：可视化管理 Milvus 集合、查看向量数据、执行查询、监控集群状态

---

## 五、数据卷说明

| 卷名 | 挂载路径 | 说明 |
|------|----------|------|
| `neo4j_data` | `/data`（neo4j 容器内） | Neo4j 图数据库数据 |
| `neo4j_logs` | `/logs`（neo4j 容器内） | Neo4j 运行日志 |
| `qdrant_data` | `/qdrant/storage`（qdrant 容器内） | Qdrant 向量数据 |
| `etcd_data` | `/etcd`（etcd 容器内） | Milvus 元数据 |
| `minio_data` | `/minio_data`（minio 容器内） | Milvus 向量段文件 |
| `milvus_data` | `/var/lib/milvus`（milvus 容器内） | Milvus 本地缓存数据 |

---

## 六、网络说明

所有容器均连接到同一个 bridge 网络 `memos_network`，容器间通过**容器名**互相访问（DNS 自动解析），无需暴露内部端口到宿主机。

```
memos_network (bridge)
  ├── memos-api-docker   → 访问 qdrant-docker:6333 / neo4j-docker:7687 / milvus-standalone:19530
  ├── milvus-standalone  → 访问 milvus-etcd:2379 / milvus-minio:9000
  └── milvus-attu        → 访问 milvus-standalone:19530
```

---

## 七、常见问题

### Milvus 启动很慢？

正常现象。Milvus 首次启动需要初始化数据目录，配置了 `start_period: 90s` 作为健康检查宽限期。可通过以下命令观察进度：

```bash
docker compose logs -f milvus
```

待日志出现 `Milvus Proxy successfully started` 即表示启动完成。

### 端口冲突怎么办？

如果宿主机上已有服务占用相关端口，修改 `docker-compose.yml` 中对应服务的宿主机端口映射（冒号左侧的数字）：

```yaml
ports:
  - "19531:19530"  # 将宿主机端口改为 19531
```

### 如何只启动部分服务？

```bash
# 只启动 Qdrant 和 Neo4j，不启动 Milvus 相关服务
docker compose up -d neo4j qdrant
```

### 如何重置某个服务的数据？

```bash
# 以重置 Milvus 数据为例
docker compose stop milvus attu
docker volume rm memos-dev_milvus_data memos-dev_etcd_data memos-dev_minio_data
docker compose up -d milvus attu
```
