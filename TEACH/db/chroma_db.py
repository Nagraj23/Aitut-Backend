import chromadb
from core.config import get_settings

settings = get_settings()

# Initialize the Persistent Client (Saves data to disk)
chroma_client = chromadb.PersistentClient(path=settings.CHROMA_DB_PATH)

def get_collection(subject_name: str):
    """Gets or creates a collection for a specific subject (e.g., 'physics')"""
    return chroma_client.get_or_create_collection(name=subject_name)