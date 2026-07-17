"""Optional LLM generation for RAG chat (Gemini, Groq, or local Ollama)."""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You answer questions about a user's document using only the provided excerpts.
Rules:
- Use only information from the excerpts below.
- If the answer is not in the excerpts, say you cannot find it in the document.
- Be concise, clear, and accurate.
- Do not invent facts or cite content not in the excerpts."""

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def get_llm_status() -> dict[str, str | bool | None]:
    provider = settings.llm_provider.lower()
    if provider == "gemini" and settings.gemini_api_key:
        return {
            "llm_enabled": True,
            "llm_provider": "gemini",
            "llm_model": settings.gemini_model,
        }
    if provider == "groq" and settings.groq_api_key:
        return {
            "llm_enabled": True,
            "llm_provider": "groq",
            "llm_model": settings.groq_model,
        }
    if provider == "ollama":
        return {
            "llm_enabled": True,
            "llm_provider": "ollama",
            "llm_model": settings.ollama_model,
        }
    return {
        "llm_enabled": False,
        "llm_provider": "local",
        "llm_model": None,
    }


def _build_messages(
    question: str,
    rag_context: str | None,
    document: str,
    history: list[dict],
) -> list[dict[str, str]]:
    context = (rag_context or document[:6000]).strip()
    user_content = f"Document excerpts:\n\n{context}\n\nQuestion: {question.strip()}"

    messages: list[dict[str, str]] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for turn in history[-6:]:
        role = turn.get("role", "user")
        if role in ("user", "assistant"):
            content = str(turn.get("content", "")).strip()
            if content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_content})
    return messages


async def _call_gemini(messages: list[dict[str, str]]) -> str:
    model = settings.gemini_model
    url = f"{_GEMINI_BASE}/{model}:generateContent"

    system_text = _SYSTEM_PROMPT
    contents: list[dict] = []
    for msg in messages:
        if msg["role"] == "system":
            system_text = msg["content"]
            continue
        gemini_role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": gemini_role, "parts": [{"text": msg["content"]}]})

    payload = {
        "systemInstruction": {"parts": [{"text": system_text}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(url, params={"key": settings.gemini_api_key}, json=payload)
        if res.status_code >= 400:
            logger.warning("Gemini API error %s: %s", res.status_code, res.text[:300])
        res.raise_for_status()
        data = res.json()

    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini returned no candidates")
    parts = candidates[0].get("content", {}).get("parts") or []
    if not parts:
        raise ValueError("Gemini returned empty content")
    return str(parts[0].get("text", "")).strip()


async def _call_groq(messages: list[dict[str, str]]) -> str:
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.groq_model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 600,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(_GROQ_URL, headers=headers, json=payload)
        if res.status_code >= 400:
            logger.warning("Groq API error %s: %s", res.status_code, res.text[:300])
        res.raise_for_status()
        data = res.json()
    return str(data["choices"][0]["message"]["content"]).strip()


async def _call_ollama(messages: list[dict[str, str]]) -> str:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.post(url, json=payload)
        res.raise_for_status()
        data = res.json()
    return str(data["message"]["content"]).strip()


async def generate_rag_answer(
    question: str,
    rag_context: str | None,
    document: str,
    history: list[dict],
) -> str | None:
    """Return LLM answer, or None to fall back to local extractive chat."""
    status = get_llm_status()
    if not status["llm_enabled"]:
        return None

    messages = _build_messages(question, rag_context, document, history)
    provider = status["llm_provider"]

    try:
        if provider == "gemini":
            return await _call_gemini(messages)
        if provider == "groq":
            return await _call_groq(messages)
        if provider == "ollama":
            return await _call_ollama(messages)
    except Exception as exc:
        logger.warning("LLM generation failed (%s), falling back to local: %s", provider, exc)
        return None

    return None
