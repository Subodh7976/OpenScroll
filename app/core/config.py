from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8")

    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    GOOGLE_DEVELOPER_KEY: str
    SEARCH_ENGINE_IDENTIFIER: str
    YOUTUBE_API_KEY: str

settings = Settings()