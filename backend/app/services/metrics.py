import re
from typing import Any

from textblob import TextBlob

try:
    import textstat

    HAS_TEXTSTAT = True
except ImportError:
    HAS_TEXTSTAT = False


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s for s in parts if s.strip()]


def compute_metrics(text: str) -> dict[str, Any]:
    words = re.findall(r"\b[a-zA-Z']+\b", text)
    sentences = _sentences(text)
    blob = TextBlob(text)
    unique = set(w.lower() for w in words)

    metrics: dict[str, Any] = {
        "word_count": len(words),
        "unique_words": len(unique),
        "sentence_count": max(len(sentences), 1),
        "avg_word_length": round(sum(len(w) for w in words) / max(len(words), 1), 2),
        "reading_time_min": round(len(words) / 200, 1),
        "subjectivity": round(blob.sentiment.subjectivity, 4),
    }

    metrics["readability_grade"] = None
    metrics["flesch_reading_ease"] = None
    if HAS_TEXTSTAT and len(text) >= 50:
        try:
            metrics["readability_grade"] = round(textstat.flesch_kincaid_grade(text), 1)
            metrics["flesch_reading_ease"] = round(textstat.flesch_reading_ease(text), 1)
        except (KeyError, ValueError, ZeroDivisionError):
            # textstat CMU dict lacks many acronyms (e.g. "nlp", "ai")
            pass

    return metrics
