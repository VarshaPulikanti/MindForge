import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user, get_user_document
from app.models import Analysis, ChatMessage, Document, DocumentChunk, User
from app.schemas import AnalysisMetrics, AnalysisOut, ChatMessageOut, ChatRequest, DocumentCreate, DocumentOut
from app.services import ai
from app.services.indexing import get_chunk_texts, index_document
from app.services import vector_store

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
async def list_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentOut]:
    result = await db.execute(
        select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc())
    )
    docs = list(result.scalars().all())
    return [await _document_out(db, d) for d in docs]


@router.post("", response_model=DocumentOut, status_code=201)
async def create_document(
    payload: DocumentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    doc = Document(
        user_id=user.id,
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
    user: User = Depends(get_current_user),
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
        user_id=user.id,
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
async def get_document(doc: Document = Depends(get_user_document), db: AsyncSession = Depends(get_db)) -> DocumentOut:
    return await _document_out(db, doc)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    doc: Document = Depends(get_user_document),
    db: AsyncSession = Depends(get_db),
) -> None:
    vector_store.delete_document(doc.id)
    await db.delete(doc)
    await db.commit()


@router.post("/{document_id}/index")
async def reindex_document(
    doc: Document = Depends(get_user_document),
    db: AsyncSession = Depends(get_db),
) -> dict:
    count = await index_document(db, doc)
    await db.commit()
    return {"document_id": doc.id, "chunks_indexed": count}


@router.post("/{document_id}/analyze", response_model=AnalysisOut)
async def analyze_document(
    doc: Document = Depends(get_user_document),
    db: AsyncSession = Depends(get_db),
) -> AnalysisOut:
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
async def list_analyses(
    doc: Document = Depends(get_user_document),
    db: AsyncSession = Depends(get_db),
) -> list[AnalysisOut]:
    result = await db.execute(
        select(Analysis).where(Analysis.document_id == doc.id).order_by(Analysis.created_at.desc())
    )
    return [_analysis_out(a) for a in result.scalars().all()]


@router.delete("/{document_id}/messages", status_code=204)
async def clear_messages(
    doc: Document = Depends(get_user_document),
    db: AsyncSession = Depends(get_db),
) -> None:
    await db.execute(delete(ChatMessage).where(ChatMessage.document_id == doc.id))
    await db.commit()


@router.get("/{document_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(
    doc: Document = Depends(get_user_document),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessage]:
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.document_id == doc.id).order_by(ChatMessage.created_at)
    )
    return list(result.scalars().all())


@router.post("/{document_id}/chat", response_model=list[ChatMessageOut])
async def chat(
    payload: ChatRequest,
    doc: Document = Depends(get_user_document),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessage]:
    result = await db.execute(
        select(Document).where(Document.id == doc.id).options(selectinload(Document.messages))
    )
    document = result.scalar_one()

    chunks = await get_chunk_texts(db, document.id)
    if not chunks:
        await index_document(db, document)
        chunks = await get_chunk_texts(db, document.id)

    user_msg = ChatMessage(document_id=document.id, role="user", content=payload.message.strip())
    db.add(user_msg)
    await db.flush()

    history = [{"role": m.role, "content": m.content} for m in document.messages]
    reply, rag_used = await ai.chat_with_context(
        document.content, history, user_msg.content, chunks, document_id=document.id
    )
    assistant_msg = ChatMessage(
        document_id=document.id,
        role="assistant",
        content=reply,
        rag_chunks_used=rag_used or None,
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)
    return [user_msg, assistant_msg]
