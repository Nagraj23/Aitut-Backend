import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    # API Keys
    GEMINI_API_KEY: str = ""
    
    # Paths
    CHROMA_DB_PATH: str = "./chroma_data"
    DATA_DIR: str = "./data"
    
    # Model Configs
    EMBEDDING_MODEL: str = "text-embedding-004"
    CHAT_MODEL: str = "gemini-2.0-flash"

    model_config = SettingsConfigDict(env_file=".env")

@lru_cache()
def get_settings():
    return Settings()