"""
MemOS 记忆提取链路诊断脚本

逐层验证记忆提取失败的根因：
  Step 1 — LLM 原始调用（glm-4.7 是否能正常返回 JSON）
  Step 2 — JSON 解析（parse_json_result 能否正确提取 key）
  Step 3 — Key 名对比（"memory list" vs "memory_list" 是否匹配）
  Step 4 — Embedder 调用（bge-m3 服务是否可达，embed() 返回什么）
  Step 5 — 端到端链路（完整走一次 _get_llm_response + _make_memory_item）

运行方式：
    cd MemOS
    PYTHONPATH=src python scripts/debug_memory_extraction.py
"""

import json
import os
import sys

# 加载 .env
from dotenv import load_dotenv
load_dotenv(override=True)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

SEP = "=" * 60

# ─────────────────────────────────────────────────────────────
# Step 1  LLM 原始调用
# ─────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("Step 1: 直接调用 LLM（MEMRADER 配置）")
print(SEP)

try:
    from memos.llms.factory import LLMFactory
    from memos.configs.llm import LLMConfigFactory

    llm_cfg = LLMConfigFactory.model_validate({
        "backend": "openai",
        "config": {
            "model_name_or_path": os.getenv("MEMRADER_MODEL", "glm-4.7"),
            "api_key": os.getenv("MEMRADER_API_KEY"),
            "api_base": os.getenv("MEMRADER_API_BASE"),
            "max_tokens": int(os.getenv("MEMRADER_MAX_TOKENS", 5000)),
            "temperature": 0.6,
        }
    })
    llm = LLMFactory.from_config(llm_cfg)

    test_prompt = """You are a memory extraction expert.
Return a single valid JSON object with this structure:
{
  "memory list": [
    {
      "key": "test memory",
      "memory_type": "LongTermMemory",
      "value": "This is a test memory for dump example",
      "tags": ["test"]
    }
  ],
  "summary": "User wrote a test memory."
}

Conversation:
user: This is a test memory for dump example
user: Another memory to demonstrate persistence

Your Output:"""

    messages = [{"role": "user", "content": test_prompt}]
    print(f"[LLM] 模型: {os.getenv('MEMRADER_MODEL')}")
    print(f"[LLM] API Base: {os.getenv('MEMRADER_API_BASE')}")
    raw_response = llm.generate(messages)
    print(f"[LLM] ✅ 调用成功，原始响应 (前 500 字符):\n{str(raw_response)[:500]}")
except Exception as e:
    print(f"[LLM] ❌ 调用失败: {type(e).__name__}: {e}")
    raw_response = None

# ─────────────────────────────────────────────────────────────
# Step 2  JSON 解析
# ─────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("Step 2: parse_json_result 解析")
print(SEP)

parsed = None
if raw_response:
    try:
        from memos.mem_reader.utils import parse_json_result
        parsed = parse_json_result(raw_response)
        print(f"[Parse] ✅ 解析成功，keys = {list(parsed.keys()) if parsed else '(empty)'}")
        print(f"[Parse] 完整结果:\n{json.dumps(parsed, ensure_ascii=False, indent=2)[:800]}")
    except Exception as e:
        print(f"[Parse] ❌ 解析失败: {type(e).__name__}: {e}")
else:
    print("[Parse] ⏭ 跳过（LLM 调用失败）")

# ─────────────────────────────────────────────────────────────
# Step 3  Key 名匹配验证
# ─────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("Step 3: Key 名匹配验证（'memory list' vs 'memory_list'）")
print(SEP)

if parsed:
    has_space_key = "memory list" in parsed       # _process_chat_data 使用
    has_underscore_key = "memory_list" in parsed  # 降级 fallback 返回
    print(f"[Key] 'memory list'  (空格，_process_chat_data 使用) → 存在: {has_space_key}")
    print(f"[Key] 'memory_list'  (下划线，fallback 返回)         → 存在: {has_underscore_key}")

    if has_space_key:
        items = parsed["memory list"]
        print(f"[Key] ✅ 正确 key，共 {len(items)} 条记忆条目")
    elif has_underscore_key:
        print("[Key] ⚠️  BUG: LLM 失败时 fallback 返回 'memory_list'（下划线），")
        print("           但 _process_chat_data 查找 'memory list'（空格），导致静默丢失！")
    else:
        print(f"[Key] ❌ 两种 key 都不存在，LLM 返回了意外结构: {list(parsed.keys())}")
else:
    print("[Key] ⏭ 跳过（解析失败）")

# ─────────────────────────────────────────────────────────────
# Step 4  Embedder 调用
# ─────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("Step 4: Embedder 调用（bge-m3）")
print(SEP)

try:
    from memos.embedders.factory import EmbedderFactory
    from memos.configs.embedder import EmbedderConfigFactory

    emb_cfg = EmbedderConfigFactory.model_validate({
        "backend": "universal_api",
        "config": {
            "provider": os.getenv("MOS_EMBEDDER_PROVIDER", "openai"),
            "api_key": os.getenv("MOS_EMBEDDER_API_KEY", ""),
            "model_name_or_path": os.getenv("MOS_EMBEDDER_MODEL", "bge-m3"),
            "base_url": os.getenv("MOS_EMBEDDER_API_BASE", ""),
        }
    })
    embedder = EmbedderFactory.from_config(emb_cfg)
    print(f"[Embed] API Base: {os.getenv('MOS_EMBEDDER_API_BASE')}")
    print(f"[Embed] 模型: {os.getenv('MOS_EMBEDDER_MODEL')}")
    result = embedder.embed(["This is a test memory"])
    print(f"[Embed] ✅ 调用成功")
    print(f"[Embed] 返回类型: {type(result)}")
    print(f"[Embed] 列表长度: {len(result)}")
    if result:
        item = result[0]
        print(f"[Embed] result[0] 类型: {type(item)}")
        if item is None:
            print("[Embed] ❌ result[0] 是 None！这是 'NoneType' not subscriptable 的根因")
        elif isinstance(item, list):
            print(f"[Embed] result[0] 向量维度: {len(item)}")
        else:
            print(f"[Embed] result[0] 值: {str(item)[:100]}")
except Exception as e:
    print(f"[Embed] ❌ 调用失败: {type(e).__name__}: {e}")

# ─────────────────────────────────────────────────────────────
# Step 5  端到端最小复现
# ─────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("Step 5: 端到端最小复现（模拟 _process_chat_data）")
print(SEP)

if parsed and "memory list" in parsed:
    items = parsed["memory list"]
    print(f"[E2E] 准备处理 {len(items)} 条 LLM 输出记忆...")
    for i, m in enumerate(items):
        if m is None:
            print(f"[E2E] ❌ 第 {i} 条记忆是 None！这会导致 m.get() 出现 AttributeError")
            continue
        value = m.get("value", "")
        print(f"[E2E] 第 {i} 条: value='{value[:50]}...' " if len(value) > 50 else f"[E2E] 第 {i} 条: value='{value}'")
        try:
            from memos.embedders.factory import EmbedderFactory
            from memos.configs.embedder import EmbedderConfigFactory
            emb_cfg = EmbedderConfigFactory.model_validate({
                "backend": "universal_api",
                "config": {
                    "provider": os.getenv("MOS_EMBEDDER_PROVIDER", "openai"),
                    "api_key": os.getenv("MOS_EMBEDDER_API_KEY", ""),
                    "model_name_or_path": os.getenv("MOS_EMBEDDER_MODEL", "bge-m3"),
                    "base_url": os.getenv("MOS_EMBEDDER_API_BASE", ""),
                }
            })
            embedder = EmbedderFactory.from_config(emb_cfg)
            embed_result = embedder.embed([value])
            if embed_result is None:
                print(f"[E2E] ❌ embed() 返回 None → 复现 'NoneType' not subscriptable")
            elif not embed_result:
                print(f"[E2E] ❌ embed() 返回空列表 → IndexError: list index out of range")
            elif embed_result[0] is None:
                print(f"[E2E] ❌ embed()[0] 是 None → 复现 'NoneType' not subscriptable")
            else:
                print(f"[E2E] ✅ embed 成功，向量维度: {len(embed_result[0])}")
        except Exception as e:
            print(f"[E2E] ❌ embed 出错: {type(e).__name__}: {e}")
else:
    print("[E2E] ⏭ 跳过（无可用记忆条目）")

print(f"\n{SEP}")
print("诊断完成")
print(SEP)
