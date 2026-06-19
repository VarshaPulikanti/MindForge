import os
import shutil
from pathlib import Path

from pydantic import Field
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
    database_url: str = Field(default_factory=_default_database_url)
    use_embedding_rag: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
