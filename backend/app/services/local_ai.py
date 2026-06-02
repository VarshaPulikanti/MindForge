import json
import re

from textblob import TextBlob

from app.services.metrics import compute_metrics
from app.services.rag import format_rag_context


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in parts if len(s.strip()) > 20]


def _keywords(text: str, top_n: int = 8) -> list[str]:
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    stop = {
        "that", "this", "with", "from", "have", "been", "were", "will",
        "would", "could", "should", "about", "their", "there", "which",
        "when", "what", "your", "they", "them", "than", "then", "into",
        "also", "more", "some", "such", "only", "other", "these", "those",
    }
    filtered = [w for w in words if w not in stop]
    from collections import Counter

    return [w for w, _ in Counter(filtered).most_common(top_n)]


def _topics(keywords: list[str]) -> list[str]:
    if not keywords:
        return ["general"]
    return [kw.capitalize() for kw in keywords[:4]]


def _extractive_summary(text: str, max_sentences: int = 3) -> str:
    sentences = _sentences(text)
    if not sentences:
        return text[:280] + ("..." if len(text) > 280 else "")
    if len(sentences) <= max_sentences:
        return " ".join(sentences)
    blob = TextBlob(text)
    scored: list[tuple[float, str]] = []
    for sent in sentences:
        sb = TextBlob(sent)
        overlap = len(set(sb.words) & set(blob.words)) / max(len(set(blob.words)), 1)
        scored.append((overlap + len(sent.split()) * 0.01, sent))
    scored.sort(reverse=True)
    top = sorted([s for _, s in scored[:max_sentences]], key=lambda x: text.find(x))
    return " ".join(top)


def analyze_text(text: str) -> dict:
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    if polarity > 0.1:
        sentiment = "positive"
    elif polarity < -0.1:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    keywords = _keywords(text)
    return {
        "summary": _extractive_summary(text),
        "sentiment": sentiment,
        "sentiment_score": round(polarity, 4),
        "keywords": keywords,
        "topics": _topics(keywords),
        "metrics": compute_metrics(text),
        "provider": "local",
    }


def chat_with_context(
    document: str,
    history: list[dict],
    question: str,
    rag_context: str | None = None,
    rag_chunk_count: int = 0,
) -> tuple[str, int]:
    context = rag_context or document[:4000]
    blob = TextBlob(document)
    q_blob = TextBlob(question)
    sentences = _sentences(context)
    if not sentences:
        return "I don't have enough document text to answer that. Try adding more content.", rag_chunk_count

    q_words = {w.lower() for w in q_blob.words if len(w) > 3}
    ranked: list[tuple[float, str]] = []
    for sent in sentences:
        s_words = {w.lower() for w in TextBlob(sent).words if len(w) > 3}
        overlap = len(q_words & s_words) / max(len(q_words), 1)
        ranked.append((overlap, sent))
    ranked.sort(reverse=True)
    best = [s for score, s in ranked[:3] if score > 0] or sentences[:2]

    sentiment = "positive" if blob.sentiment.polarity > 0.1 else "negative" if blob.sentiment.polarity < -0.1 else "neutral"
    excerpt = " ".join(best)

    lower_q = question.lower()
    if any(w in lower_q for w in ("summary", "summarize", "overview")):
        return (
            f"Here's a quick overview ({sentiment} tone): {_extractive_summary(document, 2)}",
            rag_chunk_count,
        )
    if any(w in lower_q for w in ("sentiment", "feel", "tone", "mood")):
        return (
            f"The document reads as {sentiment} (polarity {blob.sentiment.polarity:.2f}). "
            f"Subjectivity is {blob.sentiment.subjectivity:.2f}.",
            rag_chunk_count,
        )
    if any(w in lower_q for w in ("keyword", "topic", "theme")):
        kws = ", ".join(_keywords(document))
        return (
            (f"Key themes and terms: {kws}." if kws else "No strong keywords detected."),
            rag_chunk_count,
        )
    if any(w in lower_q for w in ("readability", "reading level", "grade level")):
        m = compute_metrics(document)
        grade = m.get("readability_grade")
        ease = m.get("flesch_reading_ease")
        if grade is not None:
            return (
                f"Readability: grade level ~{grade}, Flesch ease {ease}. "
                f"Estimated reading time {m['reading_time_min']} min.",
                rag_chunk_count,
            )
        return f"Word count: {m['word_count']}, ~{m['reading_time_min']} min read.", rag_chunk_count

    rag_note = f" (RAG retrieved {rag_chunk_count} chunks)" if rag_chunk_count else ""
    return (
        f"Based on the most relevant excerpts{rag_note}: {excerpt} "
        f"Ask about summary, sentiment, keywords, or readability for structured answers.",
        rag_chunk_count,
    )
