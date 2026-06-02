import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Analysis, ChatMessage, Document, DocumentChunk
from app.schemas import AnalysisMetrics, AnalysisOut, ChatMessageOut, ChatRequest, DocumentCreate, DocumentOut
from app.services import ai
from app.services.indexing import get_chunk_texts, index_document

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".txt", ".md", ".csv"}


def _analysis_out(row: Analysis) -> AnalysisOut:
    metrics = None
    if row.metrics:
        metrics = AnalysisMetrics(**json.loads(row.metrics))
    return AnalysisOut(
        id=row.id,
        document_id=row.document_id,
        summary=row.summary,
        sentiment=row.sentiment,
        sentiment_score=row.sentiment_score,
        keywords=json.loads(row.keywords),
        topics=json.loads(row.topics),
        metrics=metrics,
        provider=row.provider,
        created_at=row.created_at,
    )


async def _document_out(db: AsyncSession, doc: Document) -> DocumentOut:
    result = await db.execute(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc.id)
    )
    chunk_count = result.scalar() or 0
    return DocumentOut(
        id=doc.id,
        title=doc.title,
        content=doc.content,
        source_type=doc.source_type or "paste",
        file_name=doc.file_name,
        chunk_count=chunk_count,
        created_at=doc.created_at,
    )


@router.get("", response_model=list[DocumentOut])
async def list_documents(db: AsyncSession = Depends(get_db)) -> list[DocumentOut]:
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    docs = list(result.scalars().all())
    return [await _document_out(db, d) for d in docs]


@router.post("", response_model=DocumentOut, status_code=201)
async def create_document(payload: DocumentCreate, db: AsyncSession = Depends(get_db)) -> DocumentOut:
    doc = Document(
        title=payload.title.strip(),
        content=payload.content.strip(),
        source_type="paste",
    )
    db.add(doc)
    await db.flush()
    await index_document(db, doc)
    await db.commit()
    await db.refresh(doc)
    return await _document_out(db, doc)


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Supported formats: .txt, .md, .csv")

    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be UTF-8 text") from exc

    content = content.strip()
    if len(content) < 10:
        raise HTTPException(status_code=400, detail="File must contain at least 10 characters")

    doc_title = (title or file.filename.rsplit(".", 1)[0]).strip()[:255]
    doc = Document(
        title=doc_title,
        content=content,
        source_type="upload",
        file_name=file.filename,
    )
    db.add(doc)
    await db.flush()
    await index_document(db, doc)
    await db.commit()
    await db.refresh(doc)
    return await _document_out(db, doc)


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)) -> DocumentOut:
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return await _document_out(db, doc)


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: int, db: AsyncSession = Depends(get_db)) -> None:
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(doc)
    await db.commit()


@router.post("/{document_id}/index")
async def reindex_document(document_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    count = await index_document(db, doc)
    await db.commit()
    return {"document_id": document_id, "chunks_indexed": count}


@router.post("/{document_id}/analyze", response_model=AnalysisOut)
async def analyze_document(document_id: int, db: AsyncSession = Depends(get_db)) -> AnalysisOut:
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await index_document(db, doc)
    result = await ai.analyze_text(doc.content)
    row = Analysis(
        document_id=doc.id,
        summary=result["summary"],
        sentiment=result["sentiment"],
        sentiment_score=result["sentiment_score"],
        keywords=json.dumps(result["keywords"]),
        topics=json.dumps(result["topics"]),
        metrics=json.dumps(result.get("metrics")) if result.get("metrics") else None,
        provider=result["provider"],
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _analysis_out(row)


@router.get("/{document_id}/analyses", response_model=list[AnalysisOut])
async def list_analyses(document_id: int, db: AsyncSession = Depends(get_db)) -> list[AnalysisOut]:
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    result = await db.execute(
        select(Analysis).where(Analysis.document_id == document_id).order_by(Analysis.created_at.desc())
    )
    return [_analysis_out(a) for a in result.scalars().all()]


@router.delete("/{document_id}/messages", status_code=204)
async def clear_messages(document_id: int, db: AsyncSession = Depends(get_db)) -> None:
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.execute(delete(ChatMessage).where(ChatMessage.document_id == document_id))
    await db.commit()


@router.get("/{document_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(document_id: int, db: AsyncSession = Depends(get_db)) -> list[ChatMessage]:
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.document_id == document_id).order_by(ChatMessage.created_at)
    )
    return list(result.scalars().all())


@router.post("/{document_id}/chat", response_model=list[ChatMessageOut])
async def chat(
    document_id: int,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessage]:
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
        .options(selectinload(Document.messages))
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = await get_chunk_texts(db, doc.id)
    if not chunks:
        await index_document(db, doc)
        chunks = await get_chunk_texts(db, doc.id)

    user_msg = ChatMessage(document_id=doc.id, role="user", content=payload.message.strip())
    db.add(user_msg)
    await db.flush()

    history = [{"role": m.role, "content": m.content} for m in doc.messages]
    reply, rag_used = await ai.chat_with_context(doc.content, history, user_msg.content, chunks)
    assistant_msg = ChatMessage(
        document_id=doc.id,
        role="assistant",
        content=reply,
        rag_chunks_used=rag_used or None,
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)
    return [user_msg, assistant_msg]
