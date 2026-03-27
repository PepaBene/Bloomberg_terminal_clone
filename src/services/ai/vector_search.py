"""Vector search utilities for semantic search operations."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class VectorSearchResult:
    document_id: str
    similarity_score: float
    metadata: dict | None = None


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if len(vec_a) != len(vec_b):
        raise ValueError(f"Vector dimensions don't match: {len(vec_a)} vs {len(vec_b)}")
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def euclidean_distance(vec_a: list[float], vec_b: list[float]) -> float:
    if len(vec_a) != len(vec_b):
        raise ValueError(f"Vector dimensions don't match: {len(vec_a)} vs {len(vec_b)}")
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec_a, vec_b)))


def normalize_vector(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def top_k_similar(
    query_vec: list[float],
    candidates: list[tuple[str, list[float]]],
    k: int = 10,
) -> list[VectorSearchResult]:
    scored = []
    for doc_id, vec in candidates:
        score = cosine_similarity(query_vec, vec)
        scored.append(VectorSearchResult(document_id=doc_id, similarity_score=score))
    scored.sort(key=lambda r: r.similarity_score, reverse=True)
    return scored[:k]


def rerank_by_recency(
    results: list[dict],
    recency_weight: float = 0.1,
    max_age_days: int = 365,
) -> list[dict]:
    for r in results:
        age = r.get("age_days", 0)
        recency_bonus = max(0, 1 - (age / max_age_days)) * recency_weight
        r["combined_score"] = r.get("relevance_score", 0) * (1 - recency_weight) + recency_bonus
    results.sort(key=lambda r: r["combined_score"], reverse=True)
    return results


def chunk_text(
    text: str,
    max_tokens: int = 1000,
    overlap: int = 100,
    chars_per_token: int = 4,
) -> list[str]:
    max_chars = max_tokens * chars_per_token
    overlap_chars = overlap * chars_per_token
    if not text or not text.strip():
        return []
    if len(text) <= max_chars:
        return [text]
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current_chunk = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current_chunk) + len(para) + 2 <= max_chars:
            current_chunk = current_chunk + "\n\n" + para if current_chunk else para
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            if len(para) > max_chars:
                sentences = para.replace(". ", ".\n").split("\n")
                current_chunk = ""
                for sent in sentences:
                    if len(current_chunk) + len(sent) + 1 <= max_chars:
                        current_chunk = current_chunk + " " + sent if current_chunk else sent
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        # If single sentence is still too long, force-split by chars
                        if len(sent) > max_chars:
                            step = max(max_chars // 2, 1)
                            for ci in range(0, len(sent), step):
                                piece = sent[ci:ci + max_chars].strip()
                                if piece:
                                    chunks.append(piece)
                            current_chunk = ""
                        else:
                            current_chunk = sent
            else:
                current_chunk = para
    if current_chunk and current_chunk.strip():
        chunks.append(current_chunk.strip())
    return chunks
