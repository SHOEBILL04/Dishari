"""Embedding module for /taxonomy supporting multilingual-e5 and local models.

E5 models require explicit 'query: ' and 'passage: ' prefixes for asymmetric retrieval.
"""

from typing import Optional, Sequence
import numpy as np


class QuestionEmbedder:
    """Multilingual text embedder with e5 prefix handling and deterministic fallback."""

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-small",
        dimension: int = 384,
    ):
        self.model_name = model_name
        self.dimension = dimension
        self.is_e5 = "e5" in model_name.lower()
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        """Attempt to load SentenceTransformer; fallback to fast hashing if unavailable."""
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        except Exception:
            self._model = None

    def _prepare_text(self, text: str, is_query: bool) -> str:
        """Apply required e5 prefixes if using an e5 model."""
        clean = text.strip()
        if self.is_e5:
            prefix = "query: " if is_query else "passage: "
            if not clean.startswith(("query: ", "passage: ")):
                return prefix + clean
        return clean

    def _deterministic_hash_vector(self, text: str) -> np.ndarray:
        """Deterministic 384-d L2-normalized vector for testing and offline environments."""
        vec = np.zeros(self.dimension, dtype=np.float32)
        words = text.lower().split()
        if not words:
            return vec

        for w in words:
            # Word unigram
            idx1 = hash(w) % self.dimension
            vec[idx1] += 1.0
            # Character ngrams for subword / morphology capture
            for i in range(len(w) - 2):
                idx2 = hash(w[i:i + 3]) % self.dimension
                vec[idx2] += 0.5

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def embed_text(self, text: str, is_query: bool = False) -> list[float]:
        """Embed a single text string."""
        formatted = self._prepare_text(text, is_query=is_query)
        if self._model is not None:
            emb = self._model.encode(formatted, normalize_embeddings=True)
            return emb.tolist()
        return self._deterministic_hash_vector(formatted).tolist()

    def embed_batch(self, texts: Sequence[str], is_query: bool = False) -> np.ndarray:
        """Embed a batch of text strings."""
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        formatted_list = [self._prepare_text(t, is_query=is_query) for t in texts]
        if self._model is not None:
            embs = self._model.encode(
                formatted_list,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return np.array(embs, dtype=np.float32)

        vectors = [self._deterministic_hash_vector(t) for t in formatted_list]
        return np.vstack(vectors).astype(np.float32)


# Default module-level embedder
_default_embedder: Optional[QuestionEmbedder] = None


def get_embedder(model_name: Optional[str] = None) -> QuestionEmbedder:
    """Get or create singleton QuestionEmbedder instance."""
    global _default_embedder
    if _default_embedder is None or (model_name and _default_embedder.model_name != model_name):
        _default_embedder = QuestionEmbedder(model_name=model_name or "intfloat/multilingual-e5-small")
    return _default_embedder
