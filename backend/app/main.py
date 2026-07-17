from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import auth, documents
from app.schemas import HealthOut
from app.services.llm import get_llm_status
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

app.include_router(auth.router)
app.include_router(documents.router)


@app.get("/api/health", response_model=HealthOut)
async def health() -> HealthOut:
    db_ok = False
    db_error = None
    try:
        from sqlalchemy import text

        from app.database import async_session

        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception as exc:
        db_error = f"{exc.__class__.__name__}: {exc}"

    llm_status = get_llm_status()
    ai_provider = str(llm_status["llm_provider"]) if llm_status["llm_enabled"] else "local"
    return HealthOut(
        status="ok" if db_ok else "degraded",
        ai_provider=ai_provider,
        features={
            **get_retrieval_status(),
            **llm_status,
            "storage_mode": settings.storage_mode,
            "database_ok": db_ok,
            "database_error": db_error,
            "auth": True,
            "readability_metrics": HAS_TEXTSTAT,
            "file_upload": True,
            "analysis_history": True,
        },
    )
