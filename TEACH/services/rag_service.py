import time
import os
from groq import Groq 
import uuid
import logging
from langchain_community.document_loaders import PyPDFLoader
from typing import List, cast
from groq.types.chat import ChatCompletionMessageParam
from langchain_text_splitters import RecursiveCharacterTextSplitter
from groq.types.chat import ChatCompletionMessageParam
from typing import Any, AsyncGenerator, List
from starlette.concurrency import run_in_threadpool
import json
from sqlalchemy.orm import Session
from db.models import ChatSession, Message, Subject
from sentence_transformers import SentenceTransformer
from core.config import get_settings
from groq.types.chat import ChatCompletionMessageParam
from db.chroma_db import get_collection
from datetime import datetime
from typing import Optional, List, Generator
from sqlalchemy.orm import Session
from typing import List, Optional
import re
from typing import AsyncGenerator
import edge_tts
import json


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
groq_client = Groq(api_key=settings.GROQ_API_KEY)
embedding_model = SentenceTransformer("all-MiniLM-L6-v2",local_files_only=True)
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
 async def get_teacher_response(
    db: Session,
    user_id: str,
    university: str,
    branch: str,
    year: int,
    subject_name: str,
    day: int,
    question: str
) -> AsyncGenerator[str, None]:

    # -------------------------------
    # 1. SUBJECT FETCH (WITH FALLBACK)
    # -------------------------------
    subject_record = db.query(Subject).filter(
        Subject.name.ilike(subject_name),
        Subject.year == year,
        Subject.dept_id == branch.lower()
    ).first()

    topic = "General Study"
    task = "Reviewing concepts"

    if subject_record:
        subject_id = subject_record.id
        s_sub = str(subject_record.name).lower()
    else:
        subject_id = None
        s_sub = subject_name.lower() if subject_name else "general"

    s_univ = str(university).lower()
    s_branch = str(branch).lower()
    s_year = str(year)

    # -------------------------------
    # 2. SESSION MANAGEMENT (NO BREAK)
    # -------------------------------
    session_record = db.query(ChatSession).filter(
        ChatSession.user_id == user_id,
        ChatSession.day_number == day
    ).first()

    if not session_record:
        session_record = ChatSession(
            user_id=user_id,
            subject_id=subject_id,
            day_number=day,
            daily_topic=topic,
            daily_task_json={"day": day, "topic": topic, "task": task},
            is_completed=False
        )
        db.add(session_record)
        db.commit()
        db.refresh(session_record)

    # -------------------------------
    # 3. HISTORY
    # -------------------------------
    history = []
    past_messages = db.query(Message).filter(
        Message.session_id == session_record.id
    ).order_by(Message.timestamp.desc()).limit(10).all()

    for msg in reversed(past_messages):
        msg_data: Any = {
            "role": "assistant" if str(msg.role).lower() == "assistant" else "user",
            "content": str(msg.content)
        }
        history.append(msg_data)

    # -------------------------------
    # 4. VECTOR DB (SAFE FALLBACK)
    # -------------------------------
    context = "NO_TEXTBOOK_DATA_FOUND"

    if subject_record:
        try:
            if subject_record.vector_collection is not None:
                collection_name = str(subject_record.vector_collection)
            else:
                collection_name = f"{s_univ}_{s_branch}_{s_year}_{s_sub}"

            collection = get_collection(collection_name)

            query_text = f"{topic} {question}" if question.strip() else topic

            q_embedding = await run_in_threadpool(
                embedding_model.encode, query_text
            )
            q_embedding = q_embedding.tolist()

            results = collection.query(
                query_embeddings=[q_embedding],
                n_results=3,
                where={
                    "$and": [
                        {"university": s_univ},
                        {"branch": s_branch},
                        {"subject": s_sub},
                        {"doc_type": "notes"}
                    ]
                }
            )

            raw_docs = (results.get("documents") or [[]])[0]
            raw_meta = (results.get("metadatas") or [[]])[0]

            if raw_docs:
                context = "\n\n".join([
                    f"--- [SOURCE: {m.get('file_name')}] ---\n{d[:900]}"
                    for d, m in zip(raw_docs, raw_meta)
                ])

        except Exception as e:
            logger.error(f"[DB ERROR] {str(e)}")
            context = "NO_TEXTBOOK_DATA_FOUND"

    # -------------------------------
    # 5. SYSTEM PROMPT (UNCHANGED)
    # -------------------------------
    system_prompt = f"""
Role: Lead AI Tutor for Ai-Tut. Goal: Teach "{topic}" (Day {day}). Task: {task}.

TUTOR PROTOCOL:
- Start: If user says "hi"/"start", introduce Day {day} warmly.
- Chunking: Explain ONE concept at a time.
- Interact: Always end with a question or mini-quiz to check understanding.
- Tone: Supportive, academic mentor. Professional, not a search engine.

UI & FORMATTING RULES (CRITICAL):
- Paragraphs: Use EXACTLY two newlines (\\n\\n) between every paragraph.
- Bolding: Use **BOLD** for every technical term, law, or key definition.
- Lists: Use bullet points (-) for features, types, or steps.
- Emojis: Start each response with a 🎓 or 💡 emoji and sprinkle relevant ones throughout.

KNOWLEDGE RULES:
- Merge: Compare/merge best analogies & definitions from textbook context.
- Grounding: Context below is primary truth.
- Missing Data: If context is 'NO_TEXTBOOK_DATA_FOUND', start response EXACTLY with:
  "⚠️ **Note: This information is not in your uploaded textbooks. This response is auto-generated based on general {subject_name} principles.**"
- Partial Data: If details are missing from books, say: "I checked your books, but they don't detail this. Based on general principles..."
- Focus: Keep student on "{topic}".
"""

    # -------------------------------
    # 6. USER INPUT CONTROL (ONLY FIX)
    # -------------------------------
    no_data = (context == "NO_TEXTBOOK_DATA_FOUND")

    if no_data:
        user_msg_content = f"I'm ready to start today's lesson on {topic}"
    else:
        user_msg_content = question if question.strip() else "I'm ready to start today's lesson!"

    user_payload = (
        f"[CONTEXT FROM NOTES]\n{context}\n\n"
        f"Student says: {user_msg_content}"
    )

    messages: List = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_payload})

    # -------------------------------
    # 7. STREAMING
    # -------------------------------
    full_ai_response = ""

    try:
        response_stream = groq_client.chat.completions.create(
            messages=messages,
            model="llama-3.1-8b-instant",
            temperature=0.4,
            stream=True
        )

        for chunk in response_stream:
            token = chunk.choices[0].delta.content
            if token:
                full_ai_response += token
                yield f"data: {token}\n\n"

        db.add(Message(session_id=session_record.id, role="user", content=user_msg_content))
        db.add(Message(session_id=session_record.id, role="assistant", content=full_ai_response))
        db.commit()

    except Exception as e:
        logger.error(f"[GROQ ERROR] {str(e)}")
        yield f"data: Error: {str(e)}\n\n"
        
 @staticmethod
 def get_chat_history(db: Session, user_id: str, subject_name: str, day: int, skip: int = 0, limit: int = 20):
    # 1. First, find the subject to get the ID
    subj = db.query(Subject).filter(
        Subject.name.ilike(subject_name)
    ).first()

    if not subj:
        return []

    # 2. Find the Session
    # Use 'ChatSession' directly
    session = db.query(ChatSession).filter(
        ChatSession.user_id == user_id,
        ChatSession.subject_id == subj.id,
        ChatSession.day_number == day
    ).first()

    if not session:
        return []

    # 3. Fetch messages using 'Message' directly
    past_messages = db.query(Message).filter(
        Message.session_id == session.id
    ).order_by(Message.timestamp.desc()).offset(skip).limit(limit).all()
    
    # 4. Format and REVERSE
    formatted = [
        {
            "id": f"msg_{msg.id}", 
            "role": str(msg.role).lower(), 
            "text": str(msg.content),
            "timestamp": msg.timestamp.isoformat() if getattr(msg, 'timestamp', None) else None
        } 
        for msg in past_messages
    ]
    
    return formatted[::-1]
    
    
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
            
            
