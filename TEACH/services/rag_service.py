import time
from groq import Groq 
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from core.config import get_settings
from db.chroma_db import get_collection
from typing import List, Optional

settings = get_settings()
groq_client = Groq(api_key=settings.GROQ_API_KEY)

# Local embedding model (STABLE & FREE)
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

class RAGService:

    # ==============================
    # 1️⃣ INGEST PDF (Added doc_type parameter)
    # ==============================
    @staticmethod
    def ingest_pdf(file_path: str, subject: str, doc_type: str = "notes"): # Added doc_type
        loader = PyPDFLoader(file_path)
        pages = loader.load()

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = splitter.split_documents(pages)

        collection = get_collection(subject)
        stored_count = 0

        for i, chunk in enumerate(chunks):
            try:
                embedding = embedding_model.encode(chunk.page_content).tolist()

                collection.add(
                    ids=[f"{subject}_{doc_type}_{i}"], # Unique ID includes type
                    embeddings=[embedding],
                    documents=[chunk.page_content],
                    metadatas=[{
                        "source": file_path,
                        "page": chunk.metadata.get("page", 0),
                        "doc_type": doc_type  # <--- Added this metadata tag
                    }]
                )
                stored_count += 1
            except Exception as e:
                print(f"Embedding failed: {e}")

        return f"Stored {stored_count} {doc_type} chunks successfully."

    # ==============================
    # 2️⃣ QUESTION ANSWERING (In-depth Prompt Added)
    # ==============================
    @staticmethod
    def get_teacher_response(question: str, subject: str, history: Optional[List] = None):
        collection = get_collection(subject)
        
        try:
            q_embedding = embedding_model.encode(question).tolist()
            # Added "where" filter to only search within actual study notes
            results = collection.query(
                query_embeddings=[q_embedding],
                n_results=3,
                where={"doc_type": "notes"} 
            )
            documents = results.get("documents")
            context = "\n\n".join(documents[0]) if documents and documents[0] else "No relevant notes found."
        except Exception as e:
            return f"Error: {str(e)}"

        # --- THIS IS YOUR IN-DEPTH SYSTEM PROMPT ---
        system_prompt = """You are a patient and professional AI Tutor for the Ai-Tut platform. 
        Your goal is to help students understand complex engineering concepts.
        
        RULES:
        1. Use the 'CONTEXT FROM NOTES' strictly to answer. 
        2. If the answer isn't there, use your knowledge but mention it's outside the provided notes.
        3. Break down complex math or logic step-by-step.
        4. Use a supportive, encouraging tone.
        
        STRUCTURE YOUR OUTPUT:
        ## 🎓 Concept Overview
        ## 📘 Detailed Explanation
        ## 💡 Practical Example
        ## 📝 Key Takeaways (Bullet points)
        """

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": f"CONTEXT FROM NOTES:\n{context}\n\nUSER QUESTION: {question}"})

        chat_completion = groq_client.chat.completions.create(
            messages=messages, # type: ignore
            model="llama-3.1-8b-instant",
            temperature=0.3
        )
        return chat_completion.choices[0].message.content