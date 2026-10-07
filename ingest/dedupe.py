"""Embedding-based question deduplication for /ingest.

Flags questions with cosine similarity > 0.92 as possible duplicates.
Duplicates are never automatically deleted; they are flagged for human review.
"""

import math
from typing import Optional, Sequence
import numpy as np

from ingest.models import IngestQuestionRecord


def _simple_text_embedding(text: str, dim: int = 384) -> list[float]:
    """Deterministic token/ngram hash embedding fallback for offline use and tests."""
    vec = np.zeros(dim, dtype=np.float32)
    words = text.lower().split()
    if not words:
        return vec.tolist()

    for word in words:
        # 1-gram and 2-grams
        h = hash(word) % dim
        vec[h] += 1.0
        for i in range(len(word) - 2):
            ng = word[i:i + 3]
            h_ng = hash(ng) % dim
            vec[h_ng] += 0.5

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec.tolist()


def generate_embedding(text: str, model_name: Optional[str] = None) -> list[float]:
    """Generate 384-dimensional vector embedding for question text."""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        emb = model.encode(text)
        return emb.tolist()
    except Exception:
        # Fallback to deterministic n-gram hash vector
        return _simple_text_embedding(text, dim=384)


def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
    """Compute cosine similarity between two vector lists."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def deduplicate_questions(
    questions: list[IngestQuestionRecord],
    existing_questions: Optional[list[IngestQuestionRecord]] = None,
    threshold: float = 0.92,
) -> list[IngestQuestionRecord]:
    """Identify and flag questions with cosine similarity > threshold.
    
    Never auto-deletes; appends 'possible_duplicate' flag and retains all questions.
    """
    # 1. Compute embeddings for any questions missing them
    for q in questions:
        if q.embedding is None:
            q.embedding = generate_embedding(q.stem)

    all_reference = list(existing_questions or [])

    # 2. Compare within current batch
    n = len(questions)
    for i in range(n):
        q1 = questions[i]
        # Check against previously approved / existing questions
        for ex in all_reference:
            if ex.id == q1.id:
                continue
            if ex.embedding is not None and q1.embedding is not None:
                sim = cosine_similarity(q1.embedding, ex.embedding)
                if sim > threshold:
                    flag_msg = f"possible_duplicate: {sim:.3f} with existing Q{ex.q_no} ({ex.stem[:30]}...)"
                    if flag_msg not in q1.flags:
                        q1.flags.append(flag_msg)
                        q1.status = "needs_review"

        # Check against other questions in the current batch
        for j in range(i + 1, n):
            q2 = questions[j]
            if q1.embedding is not None and q2.embedding is not None:
                sim = cosine_similarity(q1.embedding, q2.embedding)
                if sim > threshold:
                    flag1 = f"possible_duplicate: {sim:.3f} with batch Q{q2.q_no}"
                    flag2 = f"possible_duplicate: {sim:.3f} with batch Q{q1.q_no}"
                    if flag1 not in q1.flags:
                        q1.flags.append(flag1)
                        q1.status = "needs_review"
                    if flag2 not in q2.flags:
                        q2.flags.append(flag2)
                        q2.status = "needs_review"

    return questions
