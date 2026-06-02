import re
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class RetrievedChunk:
    index: int
    text: str
    score: float


def chunk_text(text: str, chunk_size: int = 480, overlap: int = 80) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

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


def retrieve_relevant(chunks: list[str], query: str, top_k: int = 5) -> list[RetrievedChunk]:
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


def format_rag_context(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[Excerpt {i} | relevance {c.score:.2f}]\n{c.text}")
    return "\n\n".join(parts)
