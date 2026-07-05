from qdrant_client import QdrantClient, models
from core.config import get_settings

settings = get_settings()

EMBEDDING_DIMENSION = 384

qdrant_client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY,
)


def create_collection_if_not_exists(collection_name: str):
    """
    Create a collection only if it doesn't already exist.
    """

    collections = qdrant_client.get_collections().collections

    if collection_name not in [c.name for c in collections]:
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=EMBEDDING_DIMENSION,
                distance=models.Distance.COSINE,
            ),
        )


def upsert_points(collection_name: str, points: list):
    """
    Upload vectors to Qdrant.
    """

    create_collection_if_not_exists(collection_name)

    qdrant_client.upsert(
        collection_name=collection_name,
        wait=True,
        points=points,
    )


def search_points(
    collection_name: str,
    query_vector: list,
    subject: str,
    doc_type: str = "notes",
    limit: int = 3,
):
    """
    Search similar vectors using metadata filters.
    """

    create_collection_if_not_exists(collection_name)

    result = qdrant_client.query_points(
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

    return result.points


def delete_collection(collection_name: str):
    """
    Delete a collection.
    """

    qdrant_client.delete_collection(collection_name=collection_name)