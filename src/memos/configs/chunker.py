from typing import Any, ClassVar

from pydantic import Field, field_validator, model_validator

from memos.configs.base import BaseConfig


class BaseChunkerConfig(BaseConfig):
    """Base configuration class for chunkers."""

    tokenizer_or_token_counter: str = Field(
        default="gpt2", description="Tokenizer model name or a token counting function"
    )
    chunk_size: int = Field(default=512, description="Maximum tokens per chunk")
    chunk_overlap: int = Field(default=128, description="Overlap between chunks")
    min_sentences_per_chunk: int = Field(default=1, description="Minimum sentences in each chunk")
    save_rawfile: bool = Field(default=True, description="Whether to save rawfile")  # TODO



class SentenceChunkerConfig(BaseChunkerConfig):
    """Configuration for sentence-based text chunker."""


class MarkdownChunkerConfig(BaseChunkerConfig):
    """Configuration for markdown-based text chunker."""

    headers_to_split_on: list[tuple[str, str]] = Field(
        default=[("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")],
        description="Headers to split on",
    )
    strip_headers: bool = Field(default=True, description="Strip headers from the text")
    recursive: bool = Field(
        default=False, description="Whether to use recursive character text splitter"
    )


class ChunkerConfigFactory(BaseConfig):
    """Factory class for creating chunker configurations."""

    backend: str = Field(..., description="Backend for chunker")
    config: dict[str, Any] = Field(..., description="Configuration for the chunker backend")

    backend_to_class: ClassVar[dict[str, Any]] = {
        "sentence": SentenceChunkerConfig,
        "markdown": MarkdownChunkerConfig,
    }

    @field_validator("backend")
    @classmethod
    def validate_backend(cls, backend: str) -> str:
        """
        验证后端字段的有效性
        
        Args:
            backend (str): 用户指定的后端名称
            
        Returns:
            str: 验证通过的后端名称
            
        Raises:
            ValueError: 当后端名称不在预定义的后端列表中时抛出异常
            
        说明:
            此方法确保用户只能使用系统中已预定义的分块器后端，
            防止因输入无效后端名称而导致的运行时错误。
            backend_to_class字典定义了所有可用的后端选项。
        """
        if backend not in cls.backend_to_class:
            raise ValueError(f"Invalid backend: {backend}")
        return backend

    @model_validator(mode="after")
    def create_config(self) -> "ChunkerConfigFactory":
        config_class = self.backend_to_class[self.backend]
        self.config = config_class(**self.config)
        return self
