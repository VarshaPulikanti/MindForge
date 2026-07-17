import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, DocumentChunk
from app.services.rag import chunk_text

logger = logging.getLogger(__name__)


async def index_document(db: AsyncSession, document: Document) -> int:
    await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    chunks = chunk_text(document.content)
    for i, text in enumerate(chunks):
        db.add(DocumentChunk(document_id=document.id, chunk_index=i, content=text))
    await db.flush()

    try:
        from app.config import settings
        from app.services import vector_store

        if settings.use_vector_store and vector_store.is_available():
            vector_store.index_chunks(document.id, chunks)
    except Exception as exc:
        logger.warning("Vector store indexing failed for doc %s: %s", document.id, exc)

    return len(chunks)


async def get_chunk_texts(db: AsyncSession, document_id: int) -> list[str]:
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    rows = list(result.scalars().all())
    return [r.content for r in rows]
