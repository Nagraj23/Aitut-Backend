from qdrant_client import QdrantClient, models
from django.conf import settings

client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY,
)


def search_points(
    collection_name: str,
    query_vector: list,
    subject: str,
    doc_type: str = "notes",
    limit: int = 5,
):
    """
    Search vectors from Qdrant Cloud.
    """

    collections = client.get_collections().collections

    if collection_name not in [c.name for c in collections]:
        return []

    try:
        result = client.query_points(
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

    except Exception as e:
        print("Qdrant Search Error:", e)
        return []