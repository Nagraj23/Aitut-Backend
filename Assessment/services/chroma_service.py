import chromadb
from django.conf import settings
import os

def get_collection(collection_name):
    """
    Safely connects to a ChromaDB collection using the path from Django settings.
    """
    # 1. Validation Guard: Stop the "NoneType" crash before it starts
    if not collection_name or str(collection_name).lower() == "none":
        raise ValueError("❌ Chroma Error: Collection name is empty or None.")

    # 2. Standardize name (remove spaces, lowercase)
    clean_name = str(collection_name).replace(" ", "").lower().strip()
    
    # 3. Use the linked path from settings.py
    # If settings.CHROMA_DB_PATH is missing, it defaults to './chroma_data'
    db_path = getattr(settings, 'CHROMA_DB_PATH', './chroma_data')
    
    try:
        # 4. Initialize the Persistent Client
        client = chromadb.PersistentClient(path=db_path)
        
        # 5. Return the collection
        collection = client.get_collection(name=clean_name)
        print(f"✅ Successfully linked to collection: {clean_name} at {db_path}")
        return collection

    except Exception as e:
        # LOG THE ACTUAL PATH FOR DEBUGGING in your terminal
        print(f"❌ Chroma Look-up Failed at: {os.path.abspath(db_path)}")
        print(f"❌ Actual Error: {str(e)}")
        
        # Raise a readable error for the UI
        raise ValueError(
            f"Collection '{clean_name}' not found. "
            f"Check if the PDF was uploaded to the TEACH module and if the path {db_path} is correct."
        )