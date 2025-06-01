from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8")

    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None

    GOOGLE_DEVELOPER_KEY: str
    SEARCH_ENGINE_IDENTIFIER: str
    YOUTUBE_API_KEY: str

    GOOGLE_SEARCH_RESULTS: int = 20
    YOUTUBE_SEARCH_RESULTS: int = 20
    DDG_SEARCH_RESULTS: int = 20
    RESEARCH_WEB_RESULTS: int = 5
    RESEARCH_WIKI_RESULTS: int = 5

    CONTENT_RESEARCH_MODEL: str = "gemini-2.0-flash"
    SUMMARIZER_MODEL: str = "gemini-2.0-flash-lite"
    PLANNER_MODEL: str = "gemini-2.0-flash"
    WRITER_MODEL: str = "gemini-2.0-flash"
    IMAGE_MODEL: str = "gemini-2.0-flash-preview-image-generation"

    BASE_IMAGE_PATH: str = "/data/images"


settings = Settings()
