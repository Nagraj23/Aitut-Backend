import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str =""
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str =""
    CHROMA_DB_PATH: str = "./chroma_data"
    DATA_DIR: str = "./data"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CHAT_MODEL: str = "Llama-3.3-70b-versatile"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache()
def get_settings():
    return Settings()