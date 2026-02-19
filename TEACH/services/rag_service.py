from google import genai
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from core.config import get_settings
from db.chroma_db import get_collection

settings = get_settings()

# Gemini client (ONLY for generation)
client = genai.Client(
    api_key=settings.GEMINI_API_KEY,
    http_options={"api_version": "v1"}
)

# Local embedding model (FREE + STABLE)
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


class RAGService:

    # ==============================
    # 1️⃣ INGEST PDF
    # ==============================
    @staticmethod
    def ingest_pdf(file_path: str, subject: str):

        loader = PyPDFLoader(file_path)
        pages = loader.load()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100
        )
        chunks = splitter.split_documents(pages)

        collection = get_collection(subject)
        stored_count = 0

        for i, chunk in enumerate(chunks):
            try:
                # 🔥 LOCAL EMBEDDING (NO GEMINI)
                embedding = embedding_model.encode(
                    chunk.page_content
                ).tolist()

                collection.add(
                    ids=[f"{subject}_{i}"],
                    embeddings=[embedding],
                    documents=[chunk.page_content],
                    metadatas=[{
                        "source": file_path,
                        "page": chunk.metadata.get("page")
                    }]
                )

                stored_count += 1

            except Exception as e:
                print(f"Embedding failed for chunk {i}: {e}")

        return f"Stored {stored_count} chunks successfully."

    # ==============================
    # 2️⃣ QUESTION ANSWERING
    # ==============================
    @staticmethod
    def get_teacher_response(question: str, subject: str):

        collection = get_collection(subject)

        # Step 1: Embed question (LOCAL)
        try:
            q_embedding = embedding_model.encode(question).tolist()

        except Exception as e:
            return f"Embedding error: {str(e)}"

        # Step 2: Query Chroma
        try:
            results = collection.query(
                query_embeddings=[q_embedding],
                n_results=3
            )

            documents = results.get("documents") if results else None

            if documents and len(documents) > 0 and documents[0]:
                context = "\n\n".join(documents[0])
            else:
                context = "No relevant notes found."

        except Exception as e:
            return f"Chroma query error: {str(e)}"

        # Step 3: Build prompt
        prompt = f"""
You are a patient teacher.

Context:
{context}

Question:
{question}

Explain clearly in simple words.
Use tables if needed.
"""

        # Step 4: Generate response (Gemini 2.5 Flash)
        try:
            response = client.models.generate_content(
                model=settings.CHAT_MODEL,
                contents=prompt
            )

            return response.text if response.text else "No response."

        except Exception as e:
            return f"Generation error: {str(e)}"
