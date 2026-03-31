import time
import os
from groq import Groq 
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from core.config import get_settings
from groq.types.chat import ChatCompletionMessageParam
from db.chroma_db import get_collection
from typing import List, Optional


settings = get_settings()
groq_client = Groq(api_key=settings.GROQ_API_KEY)
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

class RAGService:


 @staticmethod
 def ingest_pdf(file_path: str, university: str, branch: str, year: int, subject: str, doc_type: str = "notes"):
    loader = PyPDFLoader(file_path)
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.split_documents(pages)

    collection_name = f"{university}_{branch}_{year}_{subject}".lower()
    collection = get_collection(collection_name)
    
    file_name = os.path.basename(file_path)

    ids, embeddings, documents, metadatas = [], [], [], []

    for i, chunk in enumerate(chunks):
        try:
            # Generate embedding
            embedding = embedding_model.encode(chunk.page_content).tolist()
            
            # Use a unique ID that includes a timestamp or hash to prevent overwriting 
            # if multiple people upload files with the same name
            unique_id = f"{collection_name}_{doc_type}_{i}_{int(time.time())}"
            
            ids.append(unique_id)
            embeddings.append(embedding)
            documents.append(chunk.page_content)
            metadatas.append({
                "university": university.lower(),
                "branch": branch.lower(),
                "year": str(year),
                "subject": subject.lower(),
                "doc_type": doc_type.lower(),
                "file_name": file_name,
                "page": chunk.metadata.get("page", 0)
            })
        except Exception as e:
            print(f"Chunking Error: {e}")

    # --- BATCH UPLOAD LOGIC ---
    if ids:
        try:
            # Break into smaller batches of 100 to avoid API timeouts
            for j in range(0, len(ids), 100):
                collection.add(
                    ids=ids[j:j+100],
                    embeddings=embeddings[j:j+100],
                    documents=documents[j:j+100],
                    metadatas=metadatas[j:j+100]
                )
            return f"Success: {len(ids)} chunks added to {collection_name}"
        except Exception as e:
            return f"Storage Error: {str(e)}"
            
    return "Failed: No content processed."
    
 @staticmethod
 def get_teacher_response(question: str, university: str, branch: str, year: int, subject: str, history: Optional[List] = None):
        collection_name = f"{university}_{branch}_{year}_{subject}".lower()
        collection = get_collection(collection_name)
        
        try:
            q_embedding = embedding_model.encode(question).tolist()
            
            results = collection.query(
                query_embeddings=[q_embedding],
                n_results=5,
                where={
                    "$and": [
                        {"university": university.lower()},
                        {"branch": branch.lower()},
                        {"subject": subject.lower()},
                        {"doc_type": {"$in": ["notes", "syllabus"]}}
                    ]
                }
            )

            raw_docs = results.get("documents")
            raw_meta = results.get("metadatas") 
            
            documents = raw_docs[0] if raw_docs and len(raw_docs) > 0 else []
            metadatas = raw_meta[0] if raw_meta and len(raw_meta) > 0 else []
            
            if not documents:
                context = "No relevant notes found for this specific query."
            else:
                context_parts = []
                for i, doc in enumerate(documents):
                    source = metadatas[i].get("file_name", "Unknown PDF")
                    page = metadatas[i].get("page", "N/A")
                    context_parts.append(f"--- [Source: {source} | Page: {page}] ---\n{doc}")
                
                context = "\n\n".join(context_parts)

        except Exception as e:
            return f"Error: {str(e)}"

        system_prompt = f"""You are a patient and professional AI Tutor for the Ai-Tut platform. 
        You are currently teaching: {subject.upper()} for {university.upper()} ({branch.upper()}, Year {year}).

        RULES:
        1. Use the 'CONTEXT FROM NOTES' strictly to answer. 
        2. If the answer is NOT in the notes, use your internal knowledge but start by saying: 
           "I couldn't find this specific detail in your notes, but based on standard {subject} principles..."
        3. Break down complex math, logic, or chemical reactions step-by-step.
        4. Use a supportive, encouraging, and academic tone.
        5. NEVER use Physics concepts to explain Chemistry (or vice-versa).

        STRUCTURE YOUR OUTPUT:
        ## 🎓 Concept Overview
        ## 📘 Detailed Explanation
        ## 💡 Practical Example
        ## 📝 Key Takeaways (Bullet points)
        """

        messages: List[ChatCompletionMessageParam] = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(history)

        user_payload = (
            f"UNIVERSITY: {university}\nBRANCH: {branch}\nYEAR: {year}\nSUBJECT: {subject}\n"
            f"CONTEXT FROM UPLOADED NOTES:\n{context}\n\n"
            f"STUDENT QUESTION: {question}"
        )
        
        messages.append({"role": "user", "content": user_payload})

        try:
            chat_completion = groq_client.chat.completions.create(
                messages=messages,
                model="llama-3.1-8b-instant",
                temperature=0.3
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            return f"Error: {str(e)}"