import json

import httpx

from app.config import settings
from app.services.metrics import compute_metrics


async def _chat_completion(system: str, user: str) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openai_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.4,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


async def analyze_text(text: str) -> dict:
    system = (
        "You are a text analysis assistant. Respond ONLY with valid JSON, no markdown. "
        'Schema: {"summary": str, "sentiment": "positive"|"negative"|"neutral", '
        '"sentiment_score": float between -1 and 1, "keywords": [str], "topics": [str]}'
    )
    user = f"Analyze this text:\n\n{text[:12000]}"
    raw = await _chat_completion(system, user)
    parsed = json.loads(raw)
    return {
        "summary": parsed["summary"],
        "sentiment": parsed["sentiment"],
        "sentiment_score": float(parsed["sentiment_score"]),
        "keywords": parsed["keywords"][:10],
        "topics": parsed["topics"][:6],
        "metrics": compute_metrics(text),
        "provider": "openai",
    }


async def chat_with_context(
    document: str,
    history: list[dict],
    question: str,
    rag_context: str | None = None,
    rag_chunk_count: int = 0,
) -> tuple[str, int]:
    history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history[-8:])
    context_block = rag_context or document[:12000]
    system = (
        "You answer questions using ONLY the provided document excerpts and conversation. "
        "If the answer is not in the excerpts, say so briefly. Cite which excerpt supports your answer when possible."
    )
    user = (
        f"DOCUMENT EXCERPTS (RAG, {rag_chunk_count or 'full'} chunks):\n{context_block}\n\n"
        f"CONVERSATION:\n{history_text}\n\n"
        f"USER QUESTION: {question}"
    )
    reply = await _chat_completion(system, user)
    return reply, rag_chunk_count
