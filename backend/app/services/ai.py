from app.config import settings
from app.services import local_ai, openai_ai
from app.services.rag import format_rag_context, retrieve_relevant


async def analyze_text(text: str) -> dict:
    if settings.has_openai:
        try:
            return await openai_ai.analyze_text(text)
        except Exception:
            pass
    return local_ai.analyze_text(text)


async def chat_with_context(
    document: str,
    history: list[dict],
    question: str,
    chunks: list[str] | None = None,
) -> tuple[str, int]:
    rag_chunk_count = 0
    rag_context = None
    if chunks:
        retrieved = retrieve_relevant(chunks, question, top_k=5)
        rag_chunk_count = len(retrieved)
        rag_context = format_rag_context(retrieved)

    if settings.has_openai:
        try:
            return await openai_ai.chat_with_context(
                document, history, question, rag_context, rag_chunk_count
            )
        except Exception:
            pass
    return local_ai.chat_with_context(
        document, history, question, rag_context, rag_chunk_count
    )
