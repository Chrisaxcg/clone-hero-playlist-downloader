import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Directorio base del proyecto (donde está este archivo)
_PROJECT_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    apple_music_developer_token: str = ""
    download_dir: str = str(_PROJECT_DIR / "downloads")
    fuzzy_match_threshold: int = 70
    max_results_per_song: int = 5
    enchor_rate_limit_delay: float = 0.5
    rhythmverse_rate_limit_delay: float = 1.0

    def resolved_download_dir(self) -> str:
        """Resuelve rutas relativas respecto al directorio del proyecto."""
        p = Path(self.download_dir)
        if not p.is_absolute():
            return str(_PROJECT_DIR / p)
        return str(p)


settings = Settings()
