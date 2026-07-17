from app.services import local_ai, llm
from app.services.rag import format_rag_context, retrieve_relevant


async def analyze_text(text: str) -> dict:
    return local_ai.analyze_text(text)


async def chat_with_context(
    document: str,
    history: list[dict],
    question: str,
    chunks: list[str] | None = None,
    document_id: int | None = None,
) -> tuple[str, int]:
    rag_chunk_count = 0
    rag_context = None

    if chunks:
        retrieved = retrieve_relevant(chunks, question, top_k=5, document_id=document_id)
        rag_chunk_count = len(retrieved)
        rag_context = format_rag_context(retrieved)

    generated = await llm.generate_rag_answer(question, rag_context, document, history)
    if generated:
        return generated, rag_chunk_count

    reply, count = local_ai.chat_with_context(
        document, history, question, rag_context, rag_chunk_count
    )
    if llm.get_llm_status()["llm_enabled"]:
        reply = (
            "⚠️ LLM is configured but unavailable (check API key / provider). "
            "Showing extractive answer from your document:\n\n"
            + reply
        )
    return reply, count
