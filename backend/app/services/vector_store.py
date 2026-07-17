"""Persistent vector store (ChromaDB) — embeddings saved at index time, searched at chat time."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from app.services.rag import RetrievedChunk

logger = logging.getLogger(__name__)

COLLECTION_NAME = "mindforge_chunks"

_install_checked = False
_installed = False


def is_available() -> bool:
    global _install_checked, _installed
    if not _install_checked:
        _install_checked = True
        try:
            import chromadb  # noqa: F401
            from app.services import embedding_rag

            _installed = embedding_rag.is_available()
        except ImportError:
            _installed = False
    return _installed


def _chroma_path() -> str:
    from app.config import settings

    if settings.chroma_path.strip():
        path = Path(settings.chroma_path)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    data_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "MindForge" / "chroma"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir)


@lru_cache(maxsize=1)
def _get_collection():
    import chromadb

    client = chromadb.PersistentClient(path=_chroma_path())
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def get_vector_store_status() -> dict[str, str | bool | None]:
    from app.config import settings

    active = settings.use_vector_store and is_available()
    return {
        "vector_store": active,
        "vector_store_backend": "chromadb" if active else None,
    }


def delete_document(document_id: int) -> None:
    if not is_available():
        return
    try:
        coll = _get_collection()
        coll.delete(where={"document_id": document_id})
    except Exception as exc:
        logger.warning("Vector store delete failed for doc %s: %s", document_id, exc)


def index_chunks(document_id: int, chunks: list[str]) -> int:
    """Encode chunks with MiniLM and persist vectors in ChromaDB."""
    if not is_available() or not chunks:
        return 0

    from app.services.embedding_rag import _load_model

    delete_document(document_id)
    model = _load_model()
    vectors = model.encode(chunks, normalize_embeddings=True)
    coll = _get_collection()
    ids = [f"doc{document_id}_chunk{i}" for i in range(len(chunks))]
    coll.add(
        ids=ids,
        embeddings=vectors.tolist(),
        documents=chunks,
        metadatas=[{"document_id": document_id, "chunk_index": i} for i in range(len(chunks))],
    )
    logger.info("Indexed %s chunks in ChromaDB for document %s", len(chunks), document_id)
    return len(chunks)


def has_document(document_id: int) -> bool:
    if not is_available():
        return False
    try:
        coll = _get_collection()
        result = coll.get(where={"document_id": document_id}, limit=1)
        return bool(result and result.get("ids"))
    except Exception:
        return False


def query(document_id: int, query_text: str, top_k: int = 5) -> list[RetrievedChunk]:
    """Similarity search in ChromaDB — no re-encoding of stored chunks."""
    if not is_available():
        return []

    from app.services.embedding_rag import _load_model

    model = _load_model()
    query_vec = model.encode([query_text], normalize_embeddings=True)[0]
    coll = _get_collection()
    results = coll.query(
        query_embeddings=[query_vec.tolist()],
        n_results=min(top_k, 20),
        where={"document_id": document_id},
        include=["documents", "distances", "metadatas"],
    )

    if not results["ids"] or not results["ids"][0]:
        return []

    out: list[RetrievedChunk] = []
    for i, _chunk_id in enumerate(results["ids"][0]):
        text = results["documents"][0][i]
        meta = results["metadatas"][0][i]
        chunk_index = int(meta.get("chunk_index", i))
        dist = float(results["distances"][0][i])
        score = round(max(0.0, 1.0 - dist), 4)
        if score > 0.05:
            out.append(RetrievedChunk(index=chunk_index, text=text, score=score))

    if not out and results["documents"][0]:
        meta = results["metadatas"][0][0]
        out = [
            RetrievedChunk(
                index=int(meta.get("chunk_index", 0)),
                text=results["documents"][0][0],
                score=0.0,
            )
        ]
    return out
