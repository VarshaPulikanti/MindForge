from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=10, max_length=50000)


class DocumentOut(BaseModel):
    id: int
    title: str
    content: str
    source_type: str = "paste"
    file_name: str | None = None
    chunk_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisMetrics(BaseModel):
    word_count: int
    unique_words: int
    sentence_count: int
    avg_word_length: float
    reading_time_min: float
    subjectivity: float
    readability_grade: float | None = None
    flesch_reading_ease: float | None = None


class AnalysisOut(BaseModel):
    id: int
    document_id: int
    summary: str
    sentiment: str
    sentiment_score: float
    keywords: list[str]
    topics: list[str]
    metrics: AnalysisMetrics | None = None
    provider: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatMessageOut(BaseModel):
    id: int
    document_id: int
    role: str
    content: str
    rag_chunks_used: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class HealthOut(BaseModel):
    status: str
    ai_provider: str
    features: dict[str, Any]
