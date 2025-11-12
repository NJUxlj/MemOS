from memos.configs.memory import MemoryConfigFactory
from memos.memories.factory import MemoryFactory
from dotenv import load_dotenv
import os, sys

load_dotenv()
config = MemoryConfigFactory(
    backend="general_text",
    config={
        "extractor_llm": {
            "backend": "openai",
            "config": {
                "model_name_or_path": os.getenv("ZHIPU_MODEL_ID"),
                "temperature": 0.0,
                "max_tokens": 8192,
                "top_p": 0.9,
                "top_k": 50,
                "api_key": os.getenv("ZHIPU_API_KEY"),
                "api_base": os.getenv("ZHIPU_ENDPOINT"),
            },
        },
        "vector_db": {
            "backend": "qdrant",
            "config": {
                "collection_name": "test_textual_memory",
                "distance_metric": "cosine",
                "vector_dimension": 768,
            },
        },
        "embedder": {
            "backend": "sentence_transformer",
            "config": {
                "model_name_or_path": "/Users/xiniuyiliao/Desktop/code/models/Qwen3-Embedder-0.6B",
            },
        },
    },
)

m = MemoryFactory.from_config(config)





# config = LLMConfigFactory.model_validate(
#     {
#         "backend": "openai",
#         "config": {
#             "model_name_or_path": "gpt-4.1-nano",
#             "temperature": 0.8,
#             "max_tokens": 1024,
#             "top_p": 0.9,
#             "top_k": 50,
#             "api_key": "sk-xxxx",
#             "api_base": "https://api.openai.com/v1",
#         },
#     }
# )





memories = m.extract(
    [
        {"role": "user", "content": "I love tomatoes."},
        {"role": "assistant", "content": "Great! Tomatoes are delicious."},
    ]
)
print("Extracted:", memories)


m.add(memories)
m.add([
    {
        "id": "a19b6caa-5d59-42ad-8c8a-e4f7118435b4",
        "memory": "User is Chinese.",
        "metadata": {"type": "opinion"},
    }
])


