"""Dense retrieval with sentence-transformers (optional dependency)."""

from __future__ import annotations

import logging
from functools import lru_cache

from app.services.rag import RetrievedChunk, retrieve_tfidf

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
RRF_K = 60

_install_checked = False
_installed = False


def is_available() -> bool:
    global _install_checked, _installed
    if not _install_checked:
        _install_checked = True
        try:
            import sentence_transformers  # noqa: F401

            _installed = True
        except ImportError:
            _installed = False
    return _installed


@lru_cache(maxsize=1)
def _load_model():
    from sentence_transformers import SentenceTransformer

    logger.info("Loading embedding model: %s", MODEL_NAME)
    return SentenceTransformer(MODEL_NAME)


def retrieve_embeddings(chunks: list[str], query: str, top_k: int = 5) -> list[RetrievedChunk]:
    if not chunks:
        return []
    if len(chunks) == 1:
        return [RetrievedChunk(index=0, text=chunks[0], score=1.0)]

    model = _load_model()
    vectors = model.encode(chunks + [query], normalize_embeddings=True)
    query_vec = vectors[-1]
    chunk_vecs = vectors[:-1]
    scores = chunk_vecs @ query_vec

    ranked = sorted(
        ((float(scores[i]), i, chunks[i]) for i in range(len(chunks))),
        reverse=True,
    )
    results: list[RetrievedChunk] = []
    for score, idx, text in ranked[:top_k]:
        if score > 0.05:
            results.append(RetrievedChunk(index=idx, text=text, score=round(score, 4)))
    if not results:
        results = [RetrievedChunk(index=0, text=chunks[0], score=0.0)]
    return results


def _reciprocal_rank_fusion(
    tfidf: list[RetrievedChunk],
    dense: list[RetrievedChunk],
    top_k: int,
) -> list[RetrievedChunk]:
    fused: dict[int, float] = {}
    meta: dict[int, str] = {}

    for rank, chunk in enumerate(tfidf):
        fused[chunk.index] = fused.get(chunk.index, 0.0) + 1.0 / (RRF_K + rank + 1)
        meta[chunk.index] = chunk.text
    for rank, chunk in enumerate(dense):
        fused[chunk.index] = fused.get(chunk.index, 0.0) + 1.0 / (RRF_K + rank + 1)
        meta[chunk.index] = chunk.text

    ranked = sorted(fused.items(), key=lambda item: item[1], reverse=True)[:top_k]
    return [
        RetrievedChunk(index=idx, text=meta[idx], score=round(score, 4))
        for idx, score in ranked
    ]


def retrieve_hybrid(chunks: list[str], query: str, top_k: int = 5) -> list[RetrievedChunk]:
    tfidf = retrieve_tfidf(chunks, query, top_k=top_k * 2)
    dense = retrieve_embeddings(chunks, query, top_k=top_k * 2)
    return _reciprocal_rank_fusion(tfidf, dense, top_k)


def retrieve_hybrid_vectorstore(
    chunks: list[str],
    query: str,
    document_id: int,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Hybrid RAG with dense retrieval from ChromaDB (pre-stored vectors)."""
    from app.services import vector_store

    tfidf = retrieve_tfidf(chunks, query, top_k=top_k * 2)
    dense = vector_store.query(document_id, query, top_k=top_k * 2)
    return _reciprocal_rank_fusion(tfidf, dense, top_k)
