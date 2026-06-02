from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, DocumentChunk
from app.services.rag import chunk_text


async def index_document(db: AsyncSession, document: Document) -> int:
    await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    chunks = chunk_text(document.content)
    for i, text in enumerate(chunks):
        db.add(DocumentChunk(document_id=document.id, chunk_index=i, content=text))
    await db.flush()
    return len(chunks)


async def get_chunk_texts(db: AsyncSession, document_id: int) -> list[str]:
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    rows = list(result.scalars().all())
    return [r.content for r in rows]
