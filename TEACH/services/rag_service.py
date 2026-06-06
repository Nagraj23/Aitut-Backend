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
    subject_name: str, # From URL
    day: int,          # From URL
    topic: str,        # From UI Data
    task: str,         # From UI Data
    question: str      # From UI Data
) -> AsyncGenerator[str, None]:

    # -------------------------------
    # 1. SUBJECT FETCH (WITH FALLBACK)
    # -------------------------------
    subject_record = db.query(Subject).filter(
        Subject.name.ilike(subject_name),
        Subject.year == year,
        Subject.dept_id == branch.lower()
    ).first()

    if subject_record:
        subject_id = subject_record.id
        s_sub = str(subject_record.name).lower()
    else:
        subject_id = None
        s_sub = subject_name.lower() if subject_name else "general"

    s_univ = str(university).lower()
    s_branch = str(branch).lower()
    s_year = str(year)

    
    session_record = db.query(ChatSession).filter(
    ChatSession.user_id == user_id,
    ChatSession.day_number == day
    ).first()

    print("=" * 50)
    print("RAG LOOKUP")
    print("USER:", user_id)
    print("DAY:", day)
    print("SUBJECT ID:", subject_id)

    if session_record:
        print("RAG SESSION:", session_record.id)
    else:
        print("RAG SESSION: NONE")
    print("=" * 50)

    if not session_record:
        session_record = ChatSession(
        user_id=user_id,
        subject_id=subject_id,
        day_number=day,
        daily_topic=topic,
        daily_task_json={
            "day": day,
            "topic": topic,
            "task": task
        },
        is_completed=False
    )

        db.add(session_record)
        db.commit()
        db.refresh(session_record)

    print("🚨 NEW SESSION CREATED:", session_record.id)

    # -------------------------------
    # 3. HISTORY
    # -------------------------------
    history = []
    past_messages = db.query(Message).filter(
        Message.session_id == session_record.id
    ).order_by(Message.timestamp.desc()).limit(10).all()

    for msg in reversed(past_messages):
        history.append({
            "role": "assistant" if str(msg.role).lower() == "assistant" else "user",
            "content": str(msg.content)
        })

    # -------------------------------
    # 4. RAG CONTEXT FETCH
    # -------------------------------
    context = "NO_TEXTBOOK_DATA_FOUND"
    if subject_record:
        try:
           if subject_record.vector_collection is not None:
            collection_name = str(subject_record.vector_collection)
            collection = get_collection(collection_name)
            
            query_text = f"{topic} {question}" if question.strip() else topic
            q_embedding = await run_in_threadpool(embedding_model.encode, query_text)
            
            results = collection.query(
                query_embeddings=[q_embedding.tolist()],
                n_results=3,
                where={
                    "$and": [
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
            logger.error(f"[RAG ERROR] {str(e)}")

    # -------------------------------
    # 5. SYSTEM PROMPT (STRICTLY UNCHANGED)
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
    # 6. USER INPUT CONTROL (FIXED)
    # -------------------------------
    # Ensure the AI always sees the actual question or topic focus
    if question and question.strip():
        user_msg_content = question
    else:
        user_msg_content = f"I'm ready to start today's lesson on {topic}."

    user_payload = (
        f"[CONTEXT FROM NOTES]\n{context}\n\n"
        f"Student says: {user_msg_content}"
    )

    messages: List[Any] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_payload})

    full_ai_response = ""

    def clean_text(text: str) -> str:
        if not text:
         return ""
    # Only fix spaces directly preceding standard closing punctuation characters
        text = re.sub(r'\s+([.,!?])', r'\1', text)
    # Reduce horizontal spaces without crushing structural paragraph breaks (\n\n)
        text = re.sub(r'[ \t]{2,}', ' ', text)
        return text

    try:
        response_stream = groq_client.chat.completions.create(
        messages=messages,
        model="llama-3.1-8b-instant",
        temperature=0.4,
        stream=True
    )

        buffer = ""

        for chunk in response_stream:
            token = chunk.choices[0].delta.content if chunk.choices else None

            if token:
                buffer += token

                # ✅ Only send when safe break
                if any(buffer.endswith(x) for x in [" ", ".", "\n", ":", "!", "?"]):
                    clean_chunk = clean_text(buffer)
                    full_ai_response += clean_chunk
                    yield f"data: {clean_chunk}\n\n"
                    buffer = ""

        # ✅ flush remaining buffer
        if buffer:
            clean_chunk = clean_text(buffer)
            full_ai_response += clean_chunk
            yield f"data: {clean_chunk}\n\n"

        # ✅ final cleanup
        full_ai_response = clean_text(full_ai_response)

        # ✅ Save to DB
        print("=" * 50)
        print("SAVING TO SESSION:", session_record.id)
        print("USER MESSAGE:", user_msg_content[:100])
        print("AI RESPONSE LENGTH:", len(full_ai_response))
        print("=" * 50)

        db.add(Message(
        session_id=session_record.id,
        role="user",
        content=user_msg_content
        ))

        db.add(Message(
        session_id=session_record.id,
        role="assistant",
        content=full_ai_response
        ))

        db.commit()

        print("✅ MESSAGES COMMITTED")

    except Exception as e:
     logger.error(f"[GROQ ERROR] {str(e)}")
     yield "data: Error generating response. Please try again.\n\n"
  
     
 @staticmethod
 def generate_daily_recap(history: List[dict]):
   
    """
    Analyze a completed tutoring session and extract:
    - mastered topics
    - loopholes (revision areas)
    """

    history = history[-20:]   # last 20 messages only

    chat_text = "\n".join(
        [f"{m['role']}: {m['content']}" for m in history]
    )
    
    system_prompt = """
You are an educational auditor.

Your task is to analyze a tutoring conversation and determine:

1. mastered
   - Concepts the student demonstrated understanding of.
   - Concepts the student answered correctly.
   - Concepts the student appeared comfortable with.

2. loopholes
   - Concepts requiring further revision.
   - Concepts where confusion remained.
   - Concepts that needed repeated explanation.

Rules:
- Return ONLY valid JSON.
- No markdown.
- No explanations outside JSON.
- Use short topic names.
- Both mastered and loopholes must be arrays.
- Base conclusions only on evidence from the conversation.
"""

    user_prompt = f"""
Analyze the tutoring session below.

SESSION:

{chat_text}

Return JSON with this structure:

{{
  "mastered": [],
  "loopholes": []
}}
"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        raw_content = response.choices[0].message.content
        
        print("=" * 50)
        print("RAW RECAP RESPONSE:")
        print(raw_content)
        print("=" * 50)

        if not raw_content:
            raise ValueError("Empty recap response")

        print("========== DAILY RECAP ==========")
        print(raw_content)
        print("=================================")

        result = json.loads(raw_content)

        print("PARSED RECAP:")
        print(result)
        mastered = result.get("mastered", [])
        loopholes = result.get("loopholes", [])

        if not isinstance(mastered, list):
            mastered = []

        if not isinstance(loopholes, list):
            loopholes = []

        return {
            "mastered": mastered,
            "loopholes": loopholes
        }

    except Exception as e:
        logger.error(f"Recap Generation Error: {e}")

        return {
            "mastered": [],
            "loopholes": []
        }
            
 @staticmethod
 def get_chat_history(db: Session, user_id: str, subject_name: str, day: int, skip: int = 0, limit: int = 20):
    # 1. Clean frontend url hyphen strings natively
    clean_subject_name = subject_name.replace('-', ' ').strip().lower()

    # 2. ✅ ULTRA ACCURATE SEARCH:
    # Fetch ALL session IDs belonging to this user for this day number.
    # This prevents column type mismatches or string casing splits from breaking the query.
    session_ids = db.query(ChatSession.id).filter(
        ChatSession.user_id == user_id,
        ChatSession.day_number == day
    ).all()

    # Convert the list of tuple values into a flat list of strings: ['uuid-1', 'uuid-2']
    flat_session_ids = [s[0] for s in session_ids]

    # 3. If there are no sessions at all recorded in the database, return empty array safely
    if not flat_session_ids:
        print(f"ℹ️ [RAG CORE LOG] Zero chat session profiles found for user {user_id} on Day {day}")
        return []

    print(f"🔍 [RAG CORE LOG] Found active session rows: {flat_session_ids}. Extracting matching chat logs...")

    # 4. ✅ THE BULLETPROOF FIX:
    # Query the messages table directly using an IN constraint check against all active session IDs.
    # This ensures that even if /ask created a duplicate session, your old chats are pulled instantly!
    past_messages = db.query(Message).filter(
        Message.session_id.in_(flat_session_ids)
    ).order_by(Message.timestamp.asc()).offset(skip).limit(limit).all()
    
    print(f"📝 [RAG CORE LOG] Directly retrieved {len(past_messages)} message records from SQL table.")

    # 5. Format JSON array objects matching your TeachScreen component properties
    formatted = [
        {
            "id": f"msg_{msg.id}", 
            "role": str(msg.role).lower(), 
            "text": str(msg.content),
            "timestamp": msg.timestamp.isoformat() if msg.timestamp else None
        } 
        for msg in past_messages
    ]
    
    return formatted

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
            
            
