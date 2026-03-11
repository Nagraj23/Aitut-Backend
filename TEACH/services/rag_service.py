import time
from groq import Groq # Standard Groq client for 2026
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from core.config import get_settings
from db.chroma_db import get_collection

settings = get_settings()

groq_client = Groq(api_key=settings.GROQ_API_KEY)

# Local embedding model (STABLE & FREE)
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

class RAGService:

    # ==============================
    # 1️⃣ INGEST PDF (Kept Original Logic)
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
                # Local Embedding
                embedding = embedding_model.encode(chunk.page_content).tolist()

                collection.add(
                    ids=[f"{subject}_{i}"],
                    embeddings=[embedding],
                    documents=[chunk.page_content],
                    metadatas=[{
                        "source": file_path,
                        "page": chunk.metadata.get("page", 0)
                    }]
                )
                stored_count += 1
            except Exception as e:
                print(f"Embedding failed for chunk {i}: {e}")

        return f"Stored {stored_count} chunks successfully."

    # ==============================
    # 2️⃣ QUESTION ANSWERING (Groq + Structured)
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

        # Step 3: Build Prompt with Strict Structure
        # We enforce Intro, Theory, Examples, Summary here
        system_prompt = """You are a patient and professional AI Tutor. 
Explain topics using the provided context. If the answer isn't in the context, use your knowledge but mention it's a general explanation.

Follow this EXACT structure:
## 🎓 Introduction
(Brief overview)

## 📘 Theory
(Detailed explanation from the notes)

## 💡 Examples
(Use examples from notes or simple analogies)

## 📝 Summary
(Key takeaways in bullet points)
"""

        user_content = f"Context:\n{context}\n\nQuestion: {question}"

        # Step 4: Generate response with Groq (Fast & Structured)
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                model="llama-3.1-8b-instant",
                temperature=0.3, # Low temperature keeps it factual
                max_tokens=2048
            )

            return chat_completion.choices[0].message.content

        except Exception as e:
            # Simple retry logic for 429 errors (Rate Limits)
            if "429" in str(e):
                return "Error: Rate limit reached. Please wait a moment and try again."
            return f"Generation error: {str(e)}"