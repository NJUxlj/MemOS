from memos.configs.chunker import SentenceChunkerConfig
from memos.dependency import require_python_package
from memos.log import get_logger

from .base import BaseChunker, Chunk


logger = get_logger(__name__)


class SentenceChunker(BaseChunker):
    """Sentence-based text chunker."""

    @require_python_package(
        import_name="chonkie",
        install_command="pip install chonkie",
        install_link="https://docs.chonkie.ai/python-sdk/getting-started/installation",
    )
    def __init__(self, config: SentenceChunkerConfig):
        from chonkie import SentenceChunker as ChonkieSentenceChunker

        self.config = config
        self.chunker = ChonkieSentenceChunker(
            # tokenizer_or_token_counter=config.tokenizer_or_token_counter,
            tokenizer=config.tokenizer_or_token_counter,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            min_sentences_per_chunk=config.min_sentences_per_chunk,
        )
        logger.info(f"Initialized SentenceChunker with config: {config}")

    def chunk(self, text: str) -> list[Chunk]:
        """Chunk the given text into smaller chunks based on sentences."""
        chonkie_chunks = self.chunker.chunk(text)

        chunks = []
        for c in chonkie_chunks:
            # chunk = Chunk(text=c.text, token_count=c.token_count, sentences=c.sentences)
            # TODO Extract sentences from chunk text using nltk or basic split
            try:
                import nltk
                nltk.download('punkt', quiet=True)
                sentences = nltk.sent_tokenize(c.text)
            except:
                # Fallback: simple sentence splitting
                sentences = c.text.split('. ')
                # Clean up the sentences
                sentences = [s.strip() + ('.' if not s.endswith('.') and i < len(sentences)-1 else '') 
                           for i, s in enumerate(sentences) if s.strip()]
            
            chunk = Chunk(text=c.text, token_count=c.token_count, sentences=sentences)
            chunks.append(chunk)

        logger.debug(f"Generated {len(chunks)} chunks from input text")
        return chunks
