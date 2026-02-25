# MemOS 项目架构文档

> 版本：2.0.6 (Stardust/星尘)  
> 生成时间：2026-02-25  
> Python 要求：>=3.10  
> 许可证：Apache 2.0

---

## 一、项目概述

**MemOS (Memory Operating System)** 是一个面向 LLM 和 AI Agent 的内存操作系统，旨在统一管理长期记忆的存储、检索和管理。

### 核心特性

| 特性 | 说明 |
|------|------|
| 统一内存 API | 支持添加、检索、编辑、删除记忆的标准接口 |
| 多模态内存 | 支持文本、图像、工具轨迹、用户画像等多种内存类型 |
| 多 Cube 知识库管理 | 支持多个可独立组合的内存 Cube |
| 异步内存调度器 | MemScheduler 支持高并发异步内存操作 |
| CoT 增强聊天 | PRO 模式支持思维链分解复杂问题 |
| 内存反馈与修正 | 支持通过自然语言反馈修正记忆 |
| REST API | 完整的 FastAPI HTTP 接口 |

---

## 二、项目目录结构

```
MemOS/
├── README.md                          # 项目说明文档
├── pyproject.toml                     # Poetry 项目配置（依赖管理）
├── poetry.lock                        # Poetry 锁定文件
├── Makefile                           # 构建脚本
├── LICENSE                            # Apache 2.0 许可证
├── .env.example                       # 环境变量示例
├── .pre-commit-config.yaml            # Pre-commit 配置
│
├── docker/                            # Docker 部署相关
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── requirements-full.txt
│
├── docs/                              # 文档目录
│   ├── README.md
│   ├── openapi.json
│   └── product-api-tests.md
│
├── examples/                          # 示例代码
│   ├── core_memories/
│   ├── mem_chat/
│   ├── mem_scheduler/
│   ├── mem_reader/
│   └── api/
│
├── tests/                             # 测试代码
│   ├── test_*.py                      # 单元测试
│   ├── parsers/                       # 解析器测试
│   ├── vec_dbs/                       # 向量数据库测试
│   ├── chunkers/                      # 分块器测试
│   ├── embedders/                     # 嵌入器测试
│   ├── llms/                          # LLM 测试
│   ├── mem_chat/                      # 内存聊天测试
│   ├── mem_scheduler/                 # 调度器测试
│   ├── configs/                       # 配置测试
│   └── api/                           # API 测试
│
├── scripts/                           # 工具脚本
├── evaluation/                        # 评估相关
│
└── src/memos/                         # 核心源代码
    ├── __init__.py
    ├── mem_os/                        # 内存操作系统核心
    ├── mem_cube/                      # 内存 Cube 模块
    ├── memories/                      # 内存类型实现
    │   ├── textual/                   # 文本内存
    │   ├── activation/                # 激活内存（KV Cache）
    │   └── parametric/                # 参数化内存（LoRA）
    ├── configs/                       # 配置系统
    ├── llms/                          # LLM 集成
    ├── embedders/                     # 嵌入模型
    ├── vec_dbs/                       # 向量数据库
    ├── graph_dbs/                     # 图数据库
    ├── parsers/                       # 文档解析器
    ├── chunkers/                      # 文本分块器
    ├── reranker/                      # 重排序器
    ├── mem_reader/                    # 内存读取器
    ├── mem_scheduler/                 # 内存调度器
    ├── mem_user/                      # 用户管理
    ├── mem_chat/                      # 内存聊天
    ├── mem_feedback/                  # 内存反馈
    ├── mem_agent/                     # 内存 Agent
    ├── api/                           # REST API
    ├── templates/                     # 提示词模板
    ├── types/                         # 类型定义
    ├── context/                       # 上下文管理
    ├── memos_tools/                   # 工具函数
    ├── extras/                        # 扩展功能
    ├── log.py                         # 日志工具
    ├── settings.py                    # 全局设置
    ├── exceptions.py                  # 异常定义
    ├── dependency.py                  # 依赖注入
    └── utils.py                       # 通用工具
```

---

## 三、整体架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                      用户 / 应用层                           │
│          REST API (FastAPI)  /  Python SDK (MOS)            │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    MOS (Memory OS Core)                      │
│     用户管理 │ MemCube 注册 │ 聊天对话 │ 内存 CRUD │ CoT    │
└──┬──────────────────────────────────────────────────────┬───┘
   │                                                      │
┌──▼────────────────────────┐            ┌───────────────▼───┐
│     MemCube × N           │            │   MemScheduler    │
│  ┌────────────────────┐   │            │  (异步任务调度)    │
│  │   TextMemory       │   │            │  Redis / RabbitMQ │
│  │   ActMemory        │   │            └───────────────────┘
│  │   ParaMemory       │   │
│  │   PrefMemory       │   │
│  └────────────────────┘   │
└───────────────────────────┘
         │        │
┌────────▼──┐  ┌──▼────────────────────────────────────────┐
│  LLM 层   │  │           存储后端层                       │
│  OpenAI   │  │  VecDB (Qdrant/Milvus)                    │
│  Ollama   │  │  GraphDB (Neo4j)                           │
│  Qwen     │  │  Embedder (OpenAI/Ollama/ARK)              │
│  DeepSeek │  │  Reranker                                  │
│  HF       │  │  Parser (MarkItDown)                       │
└───────────┘  │  Chunker (SentenceChunker)                 │
               └───────────────────────────────────────────┘
```

---

## 四、核心模块详细说明

### 4.1 mem_os — 内存操作系统核心

**路径：** `src/memos/mem_os/`

**职责：** 统一管理多个 MemCube，提供内存操作的顶层接口。

| 文件 | 类 | 说明 |
|------|----|------|
| `main.py` | `MOS` | 用户接口类，继承自 MOSCore，支持自动配置和 CoT 增强 |
| `core.py` | `MOSCore` | 核心实现类（1200+ 行），管理 MemCube 生命周期和操作 |
| `utils/default_config.py` | - | 默认配置生成工具 |

**MOS 主要接口：**

```python
class MOS(MOSCore):
    def __init__(config: MOSConfig | None = None)

    # 聊天对话（支持 CoT 增强）
    def chat(
        query: str,
        user_id: str | None = None,
        base_prompt: str | None = None
    ) -> str

    # 添加记忆
    def add_memory(
        memories: list[TextualMemoryItem | dict],
        user_id: str | None = None,
        mem_cube_id: str | None = None
    ) -> list[str]  # 返回 memory_ids

    # 搜索记忆
    def search_memory(
        query: str,
        user_id: str | None = None,
        mem_cube_id: str | None = None,
        top_k: int = 5
    ) -> MOSSearchResult

    # MemCube 注册/注销
    def register_mem_cube(mem_cube: GeneralMemCube, user_id: str | None = None)
    def unregister_mem_cube(cube_id: str, user_id: str | None = None)

    # 用户管理
    def add_user(user_id: str, mem_cube_ids: list[str])
    def get_users() -> list[UserInfo]
```

---

### 4.2 mem_cube — 内存 Cube

**路径：** `src/memos/mem_cube/`

**职责：** 封装多种类型的内存，作为独立的知识单元。

| 文件 | 类 | 说明 |
|------|----|------|
| `base.py` | `BaseMemCube` | 抽象基类，定义 Cube 接口 |
| `general.py` | `GeneralMemCube` | 通用实现，包含四种内存类型 |
| `utils.py` | - | Cube 工具函数 |

**GeneralMemCube 接口：**

```python
class GeneralMemCube(BaseMemCube):
    def __init__(config: GeneralMemCubeConfig)
    def load(dir: str, memory_types: list | None = None)
    def dump(dir: str, memory_types: list | None = None)

    @property
    def text_mem() -> BaseTextMemory | None    # 文本记忆
    @property
    def act_mem() -> BaseActMemory | None      # 激活记忆（KV Cache）
    @property
    def para_mem() -> BaseParaMemory | None    # 参数化记忆（LoRA）
    @property
    def pref_mem() -> BaseTextMemory | None    # 偏好记忆
```

---

### 4.3 memories — 内存类型实现

**路径：** `src/memos/memories/`

#### 文本内存（textual/）

| 类 | 后端 | 说明 |
|----|------|------|
| `NaiveTextMemory` | 内存字典 | 简单实现，无向量检索 |
| `GeneralTextMemory` | VecDB + Reranker | 通用实现，支持语义检索 |
| `TreeTextMemory` | Neo4j 图数据库 | 树状结构，支持关系推理 |
| `SimpleTreeTextMemory` | 轻量图结构 | SimpleTree 实现 |
| `PreferenceTextMemory` | VecDB | 偏好记忆专用 |
| `SimplePreferenceTextMemory` | 内存 | 简单偏好记忆 |

**BaseTextMemory 统一接口：**

```python
class BaseTextMemory(BaseMemory):
    # 从对话消息中提取记忆
    def extract(messages: MessageList) -> list[TextualMemoryItem]

    # 添加记忆，返回记忆 ID 列表
    def add(memories: list[TextualMemoryItem | dict]) -> list[str]

    # 语义搜索记忆
    def search(query: str, top_k: int, **kwargs) -> list[TextualMemoryItem]

    # 更新记忆
    def update(memory_id: str, new_memory: TextualMemoryItem | dict)

    # 获取单条记忆
    def get(memory_id: str) -> TextualMemoryItem

    # 批量删除记忆
    def delete(memory_ids: list[str])

    # 获取所有记忆
    def get_all() -> list[TextualMemoryItem]
```

**TextualMemoryItem 数据结构：**

```python
@dataclass
class TextualMemoryItem:
    id: str                        # 记忆唯一 ID
    memory: str                    # 记忆内容文本
    score: float | None = None     # 相关性评分
    metadata: dict = {}            # 元数据（时间戳、来源等）
```

#### 激活内存（activation/）

| 类 | 说明 |
|----|------|
| `KVCacheMemory` | 标准 Transformers KV Cache |
| `VLLMKVCacheMemory` | vLLM 框架 KV Cache |

#### 参数化内存（parametric/）

| 类 | 说明 |
|----|------|
| `LoRAMemory` | LoRA 适配器参数存储 |

---

### 4.4 mem_scheduler — 内存调度器

**路径：** `src/memos/mem_scheduler/`

**职责：** 异步处理内存操作，支持高并发，解耦主流程。

| 文件 | 类 | 说明 |
|------|----|------|
| `base_scheduler.py` | `BaseScheduler` | 调度器抽象基类 |
| `general_scheduler.py` | `GeneralScheduler` | 通用调度器实现 |
| `scheduler_factory.py` | `SchedulerFactory` | 工厂类 |

**子模块：**

```
mem_scheduler/
├── task_schedule_modules/     # 任务调度（Redis Streams）
│   └── handlers/              # 各类型任务处理器
├── memory_manage_modules/     # 内存生命周期管理
├── general_modules/           # 通用基础模块
├── monitors/                  # 监控和健康检查
├── orm_modules/               # ORM 数据持久化
├── base_mixins/               # 功能混入
│   ├── memory_ops.py          # 内存操作混入
│   ├── queue_ops.py           # 队列操作混入
│   └── web_log_ops.py         # Web 日志混入
├── schemas/                   # 数据模型
│   ├── message_schemas.py     # 消息模型
│   └── task_schemas.py        # 任务模型
└── webservice_modules/        # Web 服务接口
```

**任务类型：**

| 任务标签 | 说明 |
|----------|------|
| `ADD_TASK_LABEL` | 添加记忆任务 |
| `QUERY_TASK_LABEL` | 查询任务 |
| `ANSWER_TASK_LABEL` | 回答处理任务 |
| `MEM_READ_TASK_LABEL` | 内存读取任务 |
| `PREF_ADD_TASK_LABEL` | 偏好添加任务 |

**GeneralScheduler 接口：**

```python
class GeneralScheduler(BaseScheduler):
    def __init__(config: GeneralSchedulerConfig)
    def start()                                          # 启动调度器
    def stop()                                           # 停止调度器
    def submit_messages(messages: list[ScheduleMessageItem])  # 提交任务
```

---

### 4.5 api — REST API

**路径：** `src/memos/api/`

**职责：** 提供标准 HTTP REST API 接口，基于 FastAPI 实现。

**路由 — 主要端点：**

| 方法 | 路径 | 处理器 | 说明 |
|------|------|--------|------|
| POST | `/product/add` | `AddHandler` | 添加记忆 |
| POST | `/product/search` | `SearchHandler` | 搜索记忆 |
| POST | `/product/chat` | `ChatHandler` | 聊天对话 |
| POST | `/product/feedback` | `FeedbackHandler` | 反馈记忆 |
| GET | `/product/get` | - | 获取单条记忆 |
| DELETE | `/product/delete` | - | 删除记忆 |

**处理器架构：**

```python
HandlerDependencies (依赖注入容器)
        │
        ├── SearchHandler.handle_search(request)
        ├── AddHandler.handle_add(request)
        ├── ChatHandler.handle_chat(request)
        └── FeedbackHandler.handle_feedback(request)
                │
                └── 调用 MOSCore 对应方法
```

**客户端：**

```python
class MemOSClient:
    def __init__(base_url: str, api_key: str | None = None)
    def add(memories: list, user_id: str, mem_cube_id: str) -> dict
    def search(query: str, user_id: str, mem_cube_id: str) -> dict
    def chat(query: str, user_id: str) -> dict
```

---

### 4.6 configs — 配置系统

**路径：** `src/memos/configs/`

**职责：** 统一管理所有组件配置，支持环境变量、JSON 文件和代码配置。

**配置类层次：**

```
BaseConfig
├── MOSConfig                   # MOS 主配置
│   ├── LLMConfig               # 聊天 LLM 配置
│   ├── MemReaderConfig         # 内存读取器配置
│   ├── SchedulerConfig         # 调度器配置
│   └── UserManagerConfig       # 用户管理配置
│
├── GeneralMemCubeConfig        # MemCube 配置
│   ├── MemoryConfigFactory     # 各内存类型配置
│   │   ├── TextMemoryConfig    # 文本内存配置
│   │   ├── ActMemoryConfig     # 激活内存配置
│   │   └── ParaMemoryConfig    # 参数化内存配置
│   ├── LLMConfig               # 内存提取 LLM
│   ├── EmbedderConfig          # 嵌入模型配置
│   └── VecDBConfig             # 向量数据库配置
│
├── LLMConfig                   # LLM 配置工厂
├── EmbedderConfig              # 嵌入器配置
└── VecDBConfig                 # 向量数据库配置
```

**主要环境变量：**

| 变量名 | 说明 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `MOS_TEXT_MEM_TYPE` | 文本内存类型（naive_text / general_text / tree_text） |
| `MEMOS_BASE_PATH` | MemOS 数据存储路径 |
| `ENABLE_MEM_SCHEDULER` | 是否启用调度器（true/false） |
| `PRO_MODE` | 是否启用 CoT 增强模式（true/false） |

---

### 4.7 llms — LLM 集成

**路径：** `src/memos/llms/`

| 类 | 说明 |
|----|------|
| `BaseLLM` | 抽象基类，定义 LLM 统一接口 |
| `OpenAILLM` | OpenAI（含兼容接口）实现 |
| `OllamaLLM` | Ollama 本地模型实现 |
| `QwenLLM` | 通义千问实现 |
| `DeepSeekLLM` | DeepSeek 实现 |
| `HuggingFaceLLM` | HuggingFace 模型实现 |
| `LLMFactory` | 工厂类，根据配置创建 LLM 实例 |

**BaseLLM 接口：**

```python
class BaseLLM:
    def generate(
        messages: list[dict],
        past_key_values=None,     # KV Cache（激活内存）
        **kwargs
    ) -> str | tuple[str, KVCache]
```

---

### 4.8 embedders — 嵌入模型

**路径：** `src/memos/embedders/`

| 类 | 说明 |
|----|------|
| `BaseEmbedder` | 抽象基类 |
| `OpenAIEmbedder` | OpenAI text-embedding 系列 |
| `OllamaEmbedder` | Ollama 嵌入模型 |
| `ARKEmbedder` | 字节跳动 ARK 嵌入服务 |
| `UniversalAPIEmbedder` | 通用 OpenAI 兼容接口嵌入 |
| `EmbedderFactory` | 工厂类 |

**BaseEmbedder 接口：**

```python
class BaseEmbedder:
    def embed(text: str | list[str]) -> list[float] | list[list[float]]
```

---

### 4.9 vec_dbs — 向量数据库

**路径：** `src/memos/vec_dbs/`

| 类 | 说明 |
|----|------|
| `BaseVecDB` | 抽象基类 |
| `QdrantVecDB` | Qdrant 实现 |
| `MilvusVecDB` | Milvus 实现 |
| `VecDBFactory` | 工厂类 |

**BaseVecDB 接口：**

```python
class BaseVecDB:
    def insert(items: list[VecDBItem]) -> list[str]
    def search(embedding: list[float], top_k: int) -> list[VecDBItem]
    def update(item_id: str, item: VecDBItem)
    def delete(item_ids: list[str])
    def get(item_id: str) -> VecDBItem
```

---

### 4.10 其他模块

| 模块 | 路径 | 说明 |
|------|------|------|
| `graph_dbs` | `src/memos/graph_dbs/` | Neo4j 图数据库，用于 TreeTextMemory |
| `parsers` | `src/memos/parsers/` | 文档解析器（MarkItDown），支持 PDF/Word/HTML 等 |
| `chunkers` | `src/memos/chunkers/` | 文本分块器（SentenceChunker） |
| `reranker` | `src/memos/reranker/` | 搜索结果重排序器 |
| `mem_reader` | `src/memos/mem_reader/` | 内存读取器，负责从文档/多模态内容提取记忆 |
| `mem_user` | `src/memos/mem_user/` | 用户管理（UserManager），基于 SQLAlchemy |
| `mem_chat` | `src/memos/mem_chat/` | 内存聊天封装（BaseMemChat） |
| `mem_feedback` | `src/memos/mem_feedback/` | 内存反馈修正（BaseMemFeedback） |
| `mem_agent` | `src/memos/mem_agent/` | 内存 Agent 集成 |

---

## 五、核心功能调用链

### 5.1 添加记忆

```
POST /product/add
    │ 入参: { user_id, mem_cube_id, memories: [TextualMemoryItem] }
    ▼
AddHandler.handle_add(request)
    ▼
MOSCore.add_memory(memories, user_id, mem_cube_id)
    │
    ├── 1. 验证用户和 Cube 访问权限
    ├── 2. 获取对应 MemCube 实例
    │
    ├── [调度器模式] mem_scheduler.submit_messages(ADD_TASK_LABEL, messages)
    │       └── 异步处理，立即返回
    │
    └── [直接模式] mem_cube.text_mem.add(memories)
            │
            ├── GeneralTextMemory.add():
            │   ├── embedder.embed(memory_text)      # 生成向量
            │   └── vec_db.insert(VecDBItem)          # 写入向量数据库
            │
            └── 返回 memory_ids: list[str]
```

### 5.2 搜索记忆

```
POST /product/search
    │ 入参: { user_id, mem_cube_id, query: str, top_k: int }
    ▼
SearchHandler.handle_search(request)
    ▼
MOSCore.search_memory(query, user_id, mem_cube_id, top_k)
    │
    ├── 1. 验证用户和 Cube 访问权限
    ├── 2. 获取对应 MemCube 实例
    └── 3. mem_cube.text_mem.search(query, top_k)
            │
            ├── embedder.embed(query)                 # 生成查询向量
            ├── vec_db.search(embedding, top_k * 2)   # 向量近邻检索（扩大候选集）
            └── reranker.rerank(query, candidates)    # 精排重排序
            │
            └── 返回: list[TextualMemoryItem]
                    出参: { memories: [{ id, memory, score, metadata }] }
```

### 5.3 聊天对话（标准模式）

```
POST /product/chat
    │ 入参: { user_id, query: str, base_prompt: str }
    ▼
ChatHandler.handle_chat(request)
    ▼
MOSCore.chat(query, user_id, base_prompt)
    │
    ├── 1. 获取用户可访问的 MemCube 列表
    ├── 2. 注册/获取聊天历史（mem_chat）
    │
    ├── 3. [TextMemory 已启用]
    │   ├── mem_cube.text_mem.search(query, top_k)    # 检索相关记忆
    │   └── _build_system_prompt(memories, base_prompt)  # 构建含记忆的系统提示
    │
    ├── 4. [ActMemory 已启用]
    │   └── mem_cube.act_mem.get_all()                # 获取 KV Cache
    │
    ├── 5. 构建消息列表：
    │   ├── system_prompt（含检索到的记忆）
    │   ├── chat_history（历史对话）
    │   └── user_query（当前问题）
    │
    ├── 6. chat_llm.generate(messages, past_key_values)  # 调用 LLM
    ├── 7. 更新聊天历史
    └── 8. [调度器已启用] 异步提交消息更新记忆

    出参: { reply: str }
```

### 5.4 聊天对话（CoT 增强模式，PRO_MODE=True）

```
MOS.chat(query)
    ▼
_chat_with_cot_enhancement(query, user_id, base_prompt)
    │
    ├── 1. cot_decompose(query)
    │       └── LLM 生成 JSON：
    │           {
    │             "is_complex": true/false,
    │             "sub_questions": ["子问题1", "子问题2", ...]
    │           }
    │
    ├── 2. [is_complex=True] 复杂问题路径：
    │   ├── get_sub_answers(sub_questions)
    │   │   ├── 并行搜索每个子问题的相关记忆
    │   │   └── 并行为每个子问题生成答案
    │   │
    │   └── _generate_enhanced_response_with_context()
    │       ├── 搜索原始查询的相关记忆
    │       ├── 构建包含子问答对的增强系统提示
    │       └── LLM 生成综合回答
    │
    └── 3. [is_complex=False] 退回标准聊天流程

    出参: { reply: str }
```

### 5.5 内存反馈修正

```
POST /product/feedback
    │ 入参: { user_id, memory_id: str, feedback: str }
    ▼
FeedbackHandler.handle_feedback(request)
    ▼
MOSCore.feedback_memory(memory_id, feedback, user_id)
    │
    ├── 1. 获取原始记忆: mem_cube.text_mem.get(memory_id)
    ├── 2. LLM 根据反馈生成修正后的记忆内容
    └── 3. mem_cube.text_mem.update(memory_id, new_memory)

    出参: { success: bool, updated_memory: TextualMemoryItem }
```

---

## 六、依赖关系图

```
MOS (Memory Operating System)
│
├── MOSConfig
│   ├── LLMConfig ──────────────────→ OpenAI/Ollama/Qwen/DeepSeek/HF
│   ├── MemReaderConfig
│   ├── SchedulerConfig ─────────────→ Redis / RabbitMQ
│   └── UserManagerConfig ───────────→ SQLAlchemy (SQLite/PostgreSQL)
│
├── UserManager
│   └── SQLAlchemy Engine
│
├── MemReader
│   ├── LLM（记忆提取）
│   ├── Parser（文档解析：PDF/Word/HTML）
│   └── Chunker（文本分块）
│
├── MemCube × N
│   ├── text_mem: TextMemory
│   │   ├── LLM（记忆提取/更新）
│   │   ├── Embedder ────────────────→ OpenAI/Ollama/ARK
│   │   ├── VecDB ───────────────────→ Qdrant / Milvus
│   │   ├── GraphDB [可选] ──────────→ Neo4j
│   │   └── Reranker [可选]
│   │
│   ├── act_mem: ActMemory [可选]
│   │   └── KV Cache（Transformers/vLLM）
│   │
│   ├── para_mem: ParaMemory [可选]
│   │   └── LoRA 适配器文件
│   │
│   └── pref_mem: PrefMemory [可选]
│       ├── Embedder
│       └── VecDB
│
├── ChatLLM
│   └── OpenAI/Ollama/Qwen/DeepSeek/HuggingFace
│
└── MemScheduler [可选]
    ├── Redis Streams（任务队列）
    ├── RabbitMQ [可选]
    └── Task Handlers
        ├── AddTaskHandler
        ├── QueryTaskHandler
        ├── AnswerTaskHandler
        └── PrefAddTaskHandler
```

---

## 七、数据流

### 记忆写入流
```
用户输入 / 文档
    → MemReader（Parser + Chunker）
    → LLM 提取结构化记忆
    → Embedder 生成向量
    → VecDB / GraphDB 持久化存储
```

### 记忆检索流
```
用户查询
    → Embedder 生成查询向量
    → VecDB 近邻检索（召回）
    → Reranker 精排（重排序）
    → 返回 TextualMemoryItem 列表
```

### 聊天推理流
```
用户问题
    → 检索相关记忆（向量检索）
    → 构建增强系统提示（记忆 + 指令）
    → [可选] 加载 KV Cache（激活内存）
    → LLM 生成回复
    → 异步更新记忆库（调度器）
    → 返回回复
```

---

## 八、设计模式

| 模式 | 应用场景 |
|------|----------|
| **工厂模式** | `MemoryFactory`, `LLMFactory`, `EmbedderFactory`, `VecDBFactory` 等，根据配置动态创建实例 |
| **策略模式** | 不同内存后端（naive/general/tree）实现相同接口，可按需切换 |
| **依赖注入** | API 处理器通过 `HandlerDependencies` 容器注入所需依赖 |
| **模板方法** | `BaseTextMemory`, `BaseScheduler` 等基类定义算法骨架，子类实现具体步骤 |
| **装饰器模式** | `MOS` 对 `MOSCore` 进行功能增强（CoT 增强、自动配置） |
| **观察者模式** | MemScheduler 监控任务队列，异步响应事件 |

---

## 九、关键配置说明

### MOSConfig 核心字段

```yaml
# MOS 主配置示例
mos_config:
  user_id: "default_user"            # 默认用户 ID
  chat_llm:                          # 聊天 LLM 配置
    backend: "openai"                # llm 后端类型
    model: "gpt-4o"                  # 模型名称
    api_key: "${OPENAI_API_KEY}"
  enable_textual_memory: true        # 启用文本记忆
  enable_activation_memory: false    # 启用激活记忆
  enable_parametric_memory: false    # 启用参数化记忆
  enable_mem_scheduler: false        # 启用异步调度器
  pro_mode: false                    # 启用 CoT 增强

mem_cubes:
  - cube_id: "my_cube"
    user_id: "default_user"
    text_mem:
      mem_type: "general_text"       # naive_text | general_text | tree_text
      embedder:
        backend: "openai"
        model: "text-embedding-3-small"
      vec_db:
        backend: "qdrant"
        collection_name: "my_memories"
```

---

## 十、快速上手

### Python SDK 方式

```python
from memos.mem_os.main import MOS
from memos.configs.mem_os import MOSConfig

# 初始化（自动从环境变量加载配置）
mos = MOS()

# 或显式指定配置文件
config = MOSConfig.from_json_file("config.json")
mos = MOS(config=config)

# 添加记忆
memory_ids = mos.add_memory([
    {"memory": "用户喜欢喝绿茶", "metadata": {"source": "chat"}}
])

# 搜索记忆
results = mos.search_memory("用户的饮品偏好", top_k=5)
for mem in results.memories:
    print(f"[{mem.score:.3f}] {mem.memory}")

# 聊天对话（自动检索相关记忆增强回复）
reply = mos.chat("我今天想喝点什么好？")
print(reply)
```

### REST API 方式

```bash
# 启动 API 服务
uvicorn memos.api.server_api:app --host 0.0.0.0 --port 8000

# 搜索记忆
curl -X POST http://localhost:8000/product/search \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user1", "mem_cube_id": "cube1", "query": "饮品偏好", "top_k": 5}'

# 聊天
curl -X POST http://localhost:8000/product/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user1", "query": "今天喝什么好？"}'
```

---

*本文档由自动分析生成，描述 MemOS v2.0.6 (Stardust) 的项目架构。*
