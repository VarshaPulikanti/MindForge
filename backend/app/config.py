import os
import shutil
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _default_database_url() -> str:
    """Store DB outside OneDrive/project folder to avoid sync locks."""
    data_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "MindForge"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_file = data_dir / "mindforge.db"

    legacy = _BACKEND_DIR / "mindforge.db"
    if legacy.exists() and not db_file.exists():
        try:
            shutil.copy2(legacy, db_file)
        except OSError:
            pass

    return f"sqlite+aiosqlite:///{db_file.as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    database_url: str = ""
    use_embedding_rag: bool = True
    use_vector_store: bool = True
    chroma_path: str = ""
    jwt_secret: str = "change-me-in-production"
    jwt_expire_hours: int = 72

    # LLM for RAG chat: local (extractive), gemini/groq (free API), ollama (local only)
    llm_provider: str = "local"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def effective_database_url(self) -> str:
        """Use DATABASE_URL if provided, else fall back to local SQLite."""
        return self.database_url.strip() or _default_database_url()

    @property
    def async_database_url(self) -> str:
        """Convert DATABASE_URL to asyncpg form and drop libpq-only query params."""
        from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

        url = self.effective_database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        if "+asyncpg" not in url:
            return url

        # asyncpg via SQLAlchemy rejects sslmode/channel_binding as connect kwargs
        parsed = urlparse(url)
        kept = [
            (k, v)
            for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k.lower()
            not in {
                "sslmode",
                "ssl",
                "channel_binding",
                "sslrootcert",
                "sslcert",
                "sslkey",
            }
        ]
        return urlunparse(parsed._replace(query=urlencode(kept)))

    @property
    def database_connect_args(self) -> dict:
        raw = self.effective_database_url.lower()
        async_url = self.async_database_url.lower()
        if "sqlite" in async_url:
            return {"timeout": 30}
        # Render/Neon external URLs (and any sslmode=require) need SSL for asyncpg
        needs_ssl = any(
            token in raw
            for token in (
                "sslmode=require",
                "sslmode=verify",
                ".render.com",
                ".neon.tech",
                "supabase.co",
            )
        )
        if needs_ssl:
            return {"ssl": True}
        return {}

    @property
    def storage_mode(self) -> str:
        url = self.effective_database_url.lower()
        if url.startswith("postgresql") or url.startswith("postgres"):
            return "persistent"
        if ":///./" in url:
            return "ephemeral"
        return "local"


settings = Settings()
