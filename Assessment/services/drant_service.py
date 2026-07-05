from qdrant_client import QdrantClient, models
from django.conf import settings


# ==========================================
# Qdrant Client
# ==========================================

qdrant_client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY,
)


# ==========================================
# Search syllabus vectors
# ==========================================

def search_points(
    collection_name: str,
    query_vector: list,
    subject: str,
    doc_type: str = "syllabus",
    limit: int = 25,
):
    """
    Search syllabus chunks from Qdrant.

    Parameters
    ----------
    collection_name : str
        Qdrant collection name.

    query_vector : list
        Embedding vector of user query.

    subject : str
        Subject metadata filter.

    doc_type : str
        syllabus / notes / pyq etc.

    limit : int
        Number of chunks.
    """

    try:
        response = qdrant_client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="subject",
                        match=models.MatchValue(value=subject),
                    ),
                    models.FieldCondition(
                        key="doc_type",
                        match=models.MatchValue(value=doc_type),
                    ),
                ]
            ),
        )

        return response.points

    except Exception as e:
        print(f"❌ Qdrant Search Error: {e}")
        return []


# ==========================================
# Collection exists check
# ==========================================

def collection_exists(collection_name: str):
    try:
        collections = qdrant_client.get_collections().collections
        return collection_name in [c.name for c in collections]
    except Exception:
        return False