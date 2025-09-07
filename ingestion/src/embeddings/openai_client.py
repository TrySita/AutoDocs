"""OpenAI embeddings client for generating vector embeddings."""

import os
import logging
from openai import OpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)

class EmbeddingsClient:
    """Client for generating embeddings."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "text-embedding-3-large",
        embedding_dims: int = 1536,
    ):
        """Initialize the Embeddings client.

        Args:
            api_key: OpenAI API key. If None, will use OPENAI_API_KEY environment variable.
            model: OpenAI embedding model to use (default: text-embedding-3-large)
        """
        self.api_key = api_key or os.getenv("EMBEDDINGS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Embeddings API key is required. Set EMBEDDINGS_API_KEY environment variable or pass api_key parameter."
            )

        self.model = os.getenv("EMBEDDINGS_MODEL", model)
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=os.getenv("EMBEDDINGS_BASE_URL", "https://api.openai.com/v1"),
        )

        # text-embedding-3-large has 1536 dimensions by default
        self.dimensions = embedding_dims

        logger.info(f"Initialized embeddings client with model: {model}")

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=120),
        retry=retry_if_exception_type((Exception,)),
    )
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (one per input text)
        """
        if not texts:
            return []

        try:
            print("generating embeddings trial")
            logger.debug(f"Generating embeddings for {len(texts)} texts")

            response = self.client.embeddings.create(
                input=texts,
                model=self.model,
                dimensions=self.dimensions,
            )

            embeddings = [embedding.embedding for embedding in response.data]

            logger.debug(f"Successfully generated {len(embeddings)} embeddings")
            print(f"generated {len(embeddings)} embeddings")
            return embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text string to embed

        Returns:
            Embedding vector
        """
        return self.embed([text])[0]

    def get_embedding_dimensions(self) -> int:
        """Get the dimensionality of embeddings produced by this client.

        Returns:
            Number of dimensions in embedding vectors
        """
        return self.dimensions
