import logging
import re
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    index: int
    text: str
    score: float


def _split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_text(text: str, chunk_size: int = 480, overlap: int = 80) -> list[str]:
    raw = text.strip()
    if not raw:
        return []

    paragraphs = [re.sub(r"\s+", " ", p.strip()) for p in re.split(r"\n\s*\n", raw) if p.strip()]
    if not paragraphs:
        paragraphs = [re.sub(r"\s+", " ", raw)]

    chunks: list[str] = []
    for para in paragraphs:
        if len(para) <= chunk_size:
            chunks.append(para)
        else:
            chunks.extend(_split_long_text(para, chunk_size, overlap))

    return chunks if chunks else [re.sub(r"\s+", " ", raw)]


def retrieve_tfidf(chunks: list[str], query: str, top_k: int = 5) -> list[RetrievedChunk]:
    if not chunks:
        return []
    if len(chunks) == 1:
        return [RetrievedChunk(index=0, text=chunks[0], score=1.0)]

    corpus = chunks + [query]
    vectorizer = TfidfVectorizer(stop_words="english", max_features=8000)
    matrix = vectorizer.fit_transform(corpus)
    query_vec = matrix[-1]
    chunk_matrix = matrix[:-1]
    scores = cosine_similarity(query_vec, chunk_matrix).flatten()

    ranked = sorted(
        ((float(scores[i]), i, chunks[i]) for i in range(len(chunks))),
        reverse=True,
    )
    results: list[RetrievedChunk] = []
    for score, idx, text in ranked[:top_k]:
        if score > 0.01:
            results.append(RetrievedChunk(index=idx, text=text, score=round(score, 4)))
    if not results:
        results = [RetrievedChunk(index=0, text=chunks[0], score=0.0)]
    return results


def retrieve_relevant(
    chunks: list[str],
    query: str,
    top_k: int = 5,
    document_id: int | None = None,
) -> list[RetrievedChunk]:
    from app.config import settings

    if settings.use_embedding_rag:
        try:
            from app.services import embedding_rag

            if embedding_rag.is_available():
                if document_id is not None:
                    from app.services import vector_store

                    if (
                        settings.use_vector_store
                        and vector_store.is_available()
                        and vector_store.has_document(document_id)
                    ):
                        return embedding_rag.retrieve_hybrid_vectorstore(
                            chunks, query, document_id, top_k
                        )
                return embedding_rag.retrieve_hybrid(chunks, query, top_k)
        except Exception as exc:
            logger.warning("Hybrid retrieval failed, falling back to TF-IDF: %s", exc)

    return retrieve_tfidf(chunks, query, top_k)


def get_retrieval_status() -> dict[str, str | bool | None]:
    from app.config import settings
    from app.services import embedding_rag, vector_store

    embeddings_installed = embedding_rag.is_available()
    if settings.use_embedding_rag and embeddings_installed:
        mode = "hybrid"
    else:
        mode = "tfidf"

    return {
        "retrieval_mode": mode,
        "rag_tfidf": True,
        "rag_embeddings": embeddings_installed,
        "embedding_model": embedding_rag.MODEL_NAME if embeddings_installed else None,
        **vector_store.get_vector_store_status(),
    }


def format_rag_context(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[Excerpt {i} | relevance {c.score:.2f}]\n{c.text}")
    return "\n\n".join(parts)
