import time
import os
from groq import Groq 
import logging
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from core.config import get_settings
from groq.types.chat import ChatCompletionMessageParam
from db.chroma_db import get_collection
from typing import List, Optional
import re
from typing import AsyncGenerator
import edge_tts
import json


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
groq_client = Groq(api_key=settings.GROQ_API_KEY)
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
# dg_client = DeepgramClient(settings.DEEPGRAM_API_KEY)
VOICE = "en-IN-NeerjaNeural"

class RAGService:

 @staticmethod
 def generate_daily_recap(history: List[dict]):
    """
    Analyzes the history of the current session to extract 
    Mastered topics and Loopholes for the UI and the Quiz.
    """
    # 1. Prepare the chat history for the AI to analyze
    # We only take the actual text content from the history list
    chat_text = "\n".join([f"{m['role']}: {m['content']}" for m in history])

    recap_prompt = f"""
    You are an educational auditor. Analyze this tutoring session history:
    {chat_text}

    Generate a summary of the student's progress today. 
    Return a JSON object with EXACTLY these two keys:
    1. "mastered": A list of 3 short bullet points of things the student understood well.
    2. "loopholes": A list of 3 specific technical gaps or topics the student struggled with.
    
    Output ONLY valid JSON.
    """

    try:
        response = groq_client.chat.completions.create(
            model="Llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": recap_prompt}],
            response_format={"type": "json_object"}
        )
        
        # 1. Capture the content in a variable
        raw_content = response.choices[0].message.content
        
        # 2. Safety check: ensure raw_content is a string before loading
        if raw_content:
            return json.loads(raw_content)
        
        # 3. Fallback if content is None
        raise ValueError("AI returned empty content")

    except Exception as e:
        logger.error(f"Recap Generation Error: {e}")
        return {"mastered": ["Lesson completed"], "loopholes": []}
    
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
 def get_teacher_response(
    question: str, 
    university: str, 
    branch: str, 
    year: int, 
    subject: str, 
    daily_task: dict,
    history: Optional[List] = None
):
    topic = daily_task.get('topic', 'General Study')
    task = daily_task.get('task', '')
    query_text = f"{topic} {question}" if question.strip() else topic

    collection_name = f"{university}_{branch}_{year}_{subject}".lower()
    collection = get_collection(collection_name)

    logger.info(f"[QUERY] {query_text}")
    logger.info(f"[COLLECTION] {collection_name}")

    context = ""

    # ================== 🔍 VECTOR SEARCH ==================
    try:
        q_embedding = embedding_model.encode(query_text).tolist()

        results = collection.query(
            query_embeddings=[q_embedding],
            n_results=15,
            where={
                "$and": [
                    {"university": university.lower()},
                    {"branch": branch.lower()},
                    {"subject": subject.lower()},
                    {"doc_type": {"$in": ["notes", "syllabus"]}}
                ]
            }
        )

        raw_docs = (results.get("documents") or [[]])[0]
        raw_meta = (results.get("metadatas") or [[]])[0]

        logger.info(f"[RESULT COUNT] {len(raw_docs)} chunks retrieved")

        if not raw_docs:
            context = "NO_TEXTBOOK_DATA_FOUND"
        else:
            context_parts = []

            for i, doc in enumerate(raw_docs):
                source = raw_meta[i].get("file_name", "Unknown Source")
                page = raw_meta[i].get("page", "N/A")

                logger.info(f"[SOURCE USED] File: {source} | Page: {page}")

                context_parts.append(
                    f"--- [SOURCE: {source} | PG: {page}] ---\n{doc}"
                )

            context = "\n\n".join(context_parts)

    except Exception as e:
        logger.error(f"[DB ERROR] {str(e)}")
        return {"answer": f"Database Error: {str(e)}"}

    # ================== 🧠 SYSTEM PROMPT ==================
    system_prompt = f"""
You are the Lead Human AI Tutor.

Teach "{topic}" (Day {daily_task.get('day')}).

Rules:
- Explain one concept at a time
- Be conversational
- Use textbook context strictly
- End with a question
"""

    # ================== 💬 BUILD MESSAGES ==================
    messages: List[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_prompt}
    ]

    if history:
        messages.extend([
            {"role": msg["role"], "content": msg["content"]}
            for msg in history
            if "role" in msg and "content" in msg
        ])

    user_msg = question if question.strip() else "I'm ready to start today's lesson!"

    user_payload = (
        f"[SESSION]\n"
        f"Subject: {subject}\n"
        f"Topic: {topic}\n\n"
        f"Context:\n{context}\n\n"
        f"Student: {user_msg}"
    )

    messages.append({
        "role": "user",
        "content": user_payload
    })

    # ================== 🤖 GROQ CALL ==================
    try:
        response_stream = groq_client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=0.4,
            stream=True
        )

        # 🔥 COLLECT STREAM INTO STRING
        full_text = ""

        for chunk in response_stream:
            content = chunk.choices[0].delta.content
            if content:
                full_text += content

        return {
            "answer": full_text.strip()
        }

    except Exception as e:
        logger.error(f"[GROQ ERROR] {str(e)}")
        return {
            "answer": f"AI Error: {str(e)}"
        }
        
import re
import logging

logger = logging.getLogger(__name__)

async def get_audio_stream(text_generator: AsyncGenerator[str, None]):
    """
    Consumes text chunks from Groq and yields MP3 bytes using Edge-TTS.
    """
    buffer = ""

    async for text_chunk in text_generator:
        buffer += text_chunk

        # Buffer until a full sentence or newline for natural prosody
        if re.search(r'[.!?\n]', text_chunk):
            clean_text = buffer.strip()
            if clean_text:
                try:
                    # Create the communication object
                    communicate = edge_tts.Communicate(clean_text, VOICE)
                    
                    # Iterate through the generated audio chunks
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_data = chunk.get("data")
                            if audio_data:
                                yield audio_data
                            
                except Exception as e:
                    logging.error(f"[Edge-TTS ERROR] {e}")
            
            # Reset buffer for the next sentence
            buffer = ""
            
            
