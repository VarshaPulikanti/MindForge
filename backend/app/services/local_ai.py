import re
from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from textblob import TextBlob

from app.services.metrics import compute_metrics

_STOP = {
    "that", "this", "with", "from", "have", "been", "were", "will",
    "would", "could", "should", "about", "their", "there", "which",
    "when", "what", "your", "they", "them", "than", "then", "into",
    "also", "more", "some", "such", "only", "other", "these", "those",
    "into", "does", "just", "like", "make", "made", "many", "most",
    "who", "how", "why", "where",
}

_TOPIC_ALIASES = {
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "nlp": "natural language processing",
}


def _text_from_rag_context(rag_context: str | None, document: str) -> str:
    if not rag_context:
        return document[:4000]
    parts = re.split(r"\[Excerpt \d+ \| relevance [\d.]+\]\s*\n?", rag_context)
    cleaned = "\n".join(p.strip() for p in parts if p.strip())
    return cleaned or document[:4000]


def _sentences(text: str, min_len: int = 20) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in parts if len(s.strip()) >= min_len]


def _expand_query(question: str) -> str:
    lower = question.lower()
    for short, long_form in _TOPIC_ALIASES.items():
        lower = re.sub(rf"\b{re.escape(short)}\b", long_form, lower)
    return lower


def _keywords(text: str, top_n: int = 8) -> list[str]:
    if len(text.split()) >= 12:
        try:
            vec = TfidfVectorizer(
                stop_words="english",
                max_features=400,
                ngram_range=(1, 1),
                token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9\-]{2,}\b",
            )
            matrix = vec.fit_transform([text])
            scores = matrix.toarray()[0]
            terms = vec.get_feature_names_out()
            ranked = sorted(((float(scores[i]), str(terms[i])) for i in range(len(terms))), reverse=True)
            out = [t.lower() for s, t in ranked if s > 0][:top_n]
            if out:
                return out
        except ValueError:
            pass

    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    filtered = [w for w in words if w not in _STOP]
    return [w for w, _ in Counter(filtered).most_common(top_n)]


def _topics(keywords: list[str]) -> list[str]:
    if not keywords:
        return ["General"]
    return [kw.replace("-", " ").title() for kw in keywords[:4]]


def _rank_sentences(query: str, sentences: list[str], top_n: int = 3) -> list[str]:
    if not sentences:
        return []
    if len(sentences) == 1:
        return sentences

    expanded = _expand_query(query)
    corpus = sentences + [expanded]
    vectorizer = TfidfVectorizer(stop_words="english", max_features=4000)
    matrix = vectorizer.fit_transform(corpus)
    query_vec = matrix[-1]
    sent_matrix = matrix[:-1]
    scores = cosine_similarity(query_vec, sent_matrix).flatten()
    ranked = sorted(
        ((float(scores[i]), sentences[i]) for i in range(len(sentences))),
        reverse=True,
    )
    picked = [s for score, s in ranked[:top_n] if score > 0.04]
    return picked or [s for _, s in ranked[:top_n]]


def _extractive_summary(text: str, max_sentences: int = 3) -> str:
    sentences = _sentences(text)
    if not sentences:
        return text[:280] + ("..." if len(text) > 280 else "")
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    ranked = _rank_sentences("summary overview main points key ideas", sentences, top_n=max_sentences)
    ordered = sorted(ranked, key=lambda x: text.find(x))
    return " ".join(ordered)


def _answer_from_document(question: str, document: str, top_n: int = 2) -> str:
    sentences = _sentences(document)
    if not sentences:
        return document[:400] + ("..." if len(document) > 400 else "")
    hits = _rank_sentences(question, sentences, top_n=top_n)
    return " ".join(hits) if hits else _extractive_summary(document, top_n)


def _sentiment_label(blob: TextBlob) -> str:
    p = blob.sentiment.polarity
    if p > 0.1:
        return "positive"
    if p < -0.1:
        return "negative"
    return "neutral"


def analyze_text(text: str) -> dict:
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    keywords = _keywords(text)
    return {
        "summary": _extractive_summary(text),
        "sentiment": _sentiment_label(blob),
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
    _ = history
    context = _text_from_rag_context(rag_context, document)
    blob = TextBlob(document)
    sentences = _sentences(context) or _sentences(document)
    if not sentences:
        return "I don't have enough document text to answer that. Try adding more content.", rag_chunk_count

    lower_q = question.lower().strip()
    sentiment = _sentiment_label(blob)

    if re.match(r"^(hi|hello|hey)\b", lower_q):
        return (
            "Hi! I'm in local mode — ask about summary, sentiment, keywords, "
            "readability, or anything in your document."
        ), rag_chunk_count

    if any(w in lower_q for w in ("thank", "thanks")):
        return "You're welcome. Ask another question anytime.", rag_chunk_count

    if re.match(r"^(what is|what are|who is|define|explain)\b", lower_q):
        return _answer_from_document(question, document, top_n=2), rag_chunk_count

    if any(w in lower_q for w in ("main idea", "about this", "what is this about", "tell me about")):
        return _answer_from_document(question, document, top_n=2), rag_chunk_count

    if any(w in lower_q for w in ("example", "examples", "instance", "instances")):
        example_sents = [
            s
            for s in _sentences(document)
            if re.search(r"\b(e\.g\.|for example|such as|including|like)\b", s, re.I)
        ]
        if example_sents:
            return "From the document:\n\n" + "\n".join(f"• {s}" for s in example_sents[:4]), rag_chunk_count
        return (
            "The document doesn't list specific examples.\n\n"
            f"Main content: {_extractive_summary(document, 2)}"
        ), rag_chunk_count

    if any(w in lower_q for w in ("summary", "summarize", "overview")):
        return f"Overview ({sentiment} tone):\n\n{_extractive_summary(document, 3)}", rag_chunk_count

    if any(w in lower_q for w in ("sentiment", "feel", "tone", "mood")):
        return (
            f"The document reads as {sentiment} (polarity {blob.sentiment.polarity:.2f}). "
            f"Subjectivity: {blob.sentiment.subjectivity:.2f} (0 = factual, 1 = opinion-heavy)."
        ), rag_chunk_count

    if any(w in lower_q for w in ("keyword", "topic", "theme")):
        kws = _keywords(document)
        return f"Keywords: {', '.join(kws) or 'none detected'}.\nTopics: {', '.join(_topics(kws))}.", rag_chunk_count

    if any(w in lower_q for w in ("readability", "reading level", "grade level", "flesch")):
        m = compute_metrics(document)
        grade = m.get("readability_grade")
        ease = m.get("flesch_reading_ease")
        if grade is not None:
            return (
                f"Readability: grade level ~{grade}, Flesch ease {ease}. "
                f"Reading time ~{m['reading_time_min']} min ({m['word_count']} words)."
            ), rag_chunk_count
        return f"{m['word_count']} words, ~{m['reading_time_min']} min read.", rag_chunk_count

    if any(w in lower_q for w in ("how many word", "word count", "length", "how long")):
        m = compute_metrics(document)
        return (
            f"{m['word_count']} words, {m['unique_words']} unique, "
            f"{m['sentence_count']} sentences, ~{m['reading_time_min']} min read."
        ), rag_chunk_count

    if any(w in lower_q for w in ("list", "bullet", "points", "key point")):
        sents = _sentences(document, min_len=15)[:6]
        if sents:
            body = "\n".join(f"{i}. {s}" for i, s in enumerate(sents, 1))
            return f"Key points from the document:\n\n{body}", rag_chunk_count

    excerpt = " ".join(_rank_sentences(question, sentences, top_n=2))
    if not excerpt.strip():
        return _extractive_summary(document, 2), rag_chunk_count

    return excerpt, rag_chunk_count
