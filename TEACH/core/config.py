import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    # API Keys
    GEMINI_API_KEY: str = "AIzaSyC9_P4osvu8kXe3lN3q104Wbz4vO-e4bUs"
    GROQ_API_KEY: str = "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"  # 👈 Add this for the new Groq service

    # Paths
    CHROMA_DB_PATH: str = "./chroma_data"
    DATA_DIR: str = "./data"
    
    # Model Configs
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2" # Updated to match your RAG script
    
    # We keep Gemini settings in case you want to switch back, 
    # but our main tutor now uses Groq.
    CHAT_MODEL: str = "llama-3.1-8b-instant" 

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache()
def get_settings():
    return Settings()