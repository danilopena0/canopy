"""Vector embeddings service using sentence-transformers."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Lazy-loaded model to avoid loading on import
_model = None

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


def get_model():
    """Get or create the sentence transformer model (lazy loaded).

    The model is ~90MB and downloaded on first use.

    Returns:
        SentenceTransformer model instance.
    """
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model loaded successfully")
    return _model


class EmbeddingService:
    """Service for generating text embeddings."""

    def __init__(self):
        pass

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: The text to embed. Truncated to ~256 words to avoid token limits.

        Returns:
            List of floats (384 dimensions for all-MiniLM-L6-v2).
        """
        model = get_model()
        # Truncate to avoid token limits
        words = text.split()[:256]
        truncated = " ".join(words)
        embedding = model.encode(truncated)
        return embedding.tolist()

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        model = get_model()
        # Truncate each text
        truncated = [" ".join(t.split()[:256]) for t in texts]
        embeddings = model.encode(truncated)
        return [e.tolist() for e in embeddings]

    def job_to_text(self, job: dict[str, Any]) -> str:
        """Convert a job record to embeddable text.

        Combines title, company, description, and requirements into a single
        text block suitable for embedding.

        Args:
            job: Job data dictionary.

        Returns:
            Combined text for embedding.
        """
        parts = [
            job.get("title") or "",
            job.get("company") or "",
            job.get("description") or "",
            job.get("requirements") or "",
        ]
        return " ".join(p for p in parts if p)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector.
        b: Second embedding vector.

    Returns:
        Cosine similarity score between -1 and 1.
    """
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
