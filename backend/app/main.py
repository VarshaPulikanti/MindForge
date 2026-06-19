from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import documents
from app.schemas import HealthOut
from app.services.metrics import HAS_TEXTSTAT
from app.services.rag import get_retrieval_status


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="MindForge API",
    description="AI-powered text analysis, RAG chat, and document intelligence",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)


@app.get("/api/health", response_model=HealthOut)
async def health() -> HealthOut:
    return HealthOut(
        status="ok",
        ai_provider="local",
        features={
            **get_retrieval_status(),
            "readability_metrics": HAS_TEXTSTAT,
            "file_upload": True,
            "analysis_history": True,
        },
    )
