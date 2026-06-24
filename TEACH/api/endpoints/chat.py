import os
from fastapi import Form, File, UploadFile
import shutil
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Depends, HTTPException
from db.models import ChatSession, Message, Subject
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from db.database import get_db 
from db import models
from services.rag_service import RAGService
import logging
import edge_tts
from groq import Groq
import json
import io

router = APIRouter()
logger = logging.getLogger(__name__)

class QuestionRequest(BaseModel):
    question: str
    
class TutorRequest(BaseModel):
    message: str  # Student's question or "hi"
    topic: str    # Topic from the Roadmap (e.g., "Band Theory")
    task: str
    user_id: str

@router.post("/upload/{uni}/{dept}/{year}/{subject_name}")
async def upload_pdf(
    uni: str, 
    dept: str, 
    year: int, 
    subject_name: str, 
    doc_type: str = Form("notes"),
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    # 1. Standardize IDs
    clean_subject = subject_name.strip().lower().replace(" ", "_")
    dept_id_clean = dept.lower().strip()
    vector_id = f"{uni}_{dept_id_clean}_{year}_{clean_subject}".lower()
    safe_filename = str(file.filename) if file.filename else "file.pdf"

    # 2. Auto-Detect Syllabus
    final_doc_type = doc_type.lower()
    if "syllabus" in safe_filename.lower():
        final_doc_type = "syllabus"

    # --- SQL REGISTRATION ---
    dept_obj = db.query(models.Department).filter(models.Department.id == dept_id_clean).first()
    
    if not dept_obj:
        dept_obj = models.Department(
            id=dept_id_clean, 
            name=dept.upper() 
        )
        db.add(dept_obj)
        db.commit() 
        db.refresh(dept_obj)

    subj = db.query(models.Subject).filter(models.Subject.vector_collection == vector_id).first()
    
    if not subj:
        subj = models.Subject(
            name=clean_subject,
            university=uni.lower(),
            dept_id=dept_obj.id, 
            year=year,
            vector_collection=vector_id
        )
        db.add(subj)
        try:
            db.commit()
            db.refresh(subj)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # 3. Save physical file to disk
    dir_path = f"data/{dept_id_clean}/year_{year}/{vector_id}"
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, safe_filename)
    
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # --- CHROMA INGESTION ---
    status = RAGService.ingest_pdf(
        file_path=file_path,
        university=uni,
        branch=dept_id_clean,
        year=year,
        subject=clean_subject,
        doc_type=final_doc_type
    )
    
    return {
        "status": status, 
        "subject_id": subj.id, 
        "department": dept_obj.id,
        "type_assigned": final_doc_type
    }
    
@router.post("/ask/{uni}/{dept}/{year}/{subject_name}/{day}")
async def ask_teacher(
    uni: str,
    dept: str, 
    year: int, 
    subject_name: str, 
    day: int, 
    request: TutorRequest, 
    db: Session = Depends(get_db)
):
    # 1. Clean subject name strings natively
    clean_subject_name = subject_name.replace('-', ' ').strip().lower()

    # Try fetching subject metadata safely without crashing if it's missing (DBMS)
    subj = db.query(models.Subject).filter(
        models.Subject.dept_id == dept.lower(),
        models.Subject.year == year,
        models.Subject.name.ilike(clean_subject_name)
    ).first()

    subject_id = subj.id if subj else None
    safe_subject_name = subj.name if subj else clean_subject_name 

    # 2. FIXED LOOKUP: Find or create the session using a structural text fallback match
    # We strip out the rigid subject_id filter from the query so unseeded subjects resolve safely
    session = db.query(models.ChatSession).filter(
    models.ChatSession.user_id == request.user_id,
    models.ChatSession.day_number == day
).order_by(models.ChatSession.created_at.desc()).first()

    # If it doesn't exist, build it cleanly from scratch
    if not session:
        session = models.ChatSession(
            user_id=request.user_id,
            subject_id=subject_id,  # Will save as NULL for DBMS
            day_number=day,
            daily_topic=request.topic if request.topic else safe_subject_name,
            daily_task_json={"task": request.task, "topic": request.topic}
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
    print("=" * 50)
    print("ASK SESSION:", session.id)
    print("ASK TOPIC:", session.daily_topic)
    print("=" * 50)
        
    safe_subject_name = str(subj.name) if subj else str(subject_name)
    
    # 3. Call RAG stream pipeline natively
    return StreamingResponse(
        RAGService.get_teacher_response(
            db=db,
            user_id=request.user_id,
            university=uni,
            branch=dept,
            topic=request.topic,  
            task=request.task,
            year=year,
            subject_name=safe_subject_name,  
            day=day,
            question=request.message
        ),
        media_type="text/event-stream"
    )

@router.get("/history/{user_id}/{subject_name}/{day}")
async def get_session_history(
    user_id: str, 
    subject_name: str, 
    day: int, 
    skip: int = 0, 
    limit: int = 5, 
    db: Session = Depends(get_db)
):
    # 1. Clean frontend hyphen strings (e.g., "database-management" -> "database management")
    clean_subject_name = subject_name.replace('-', ' ').strip().lower()
    
    # 2. FIXED LOOKUP: Must mirror the /ask route perfectly!
    session = db.query(ChatSession).filter(
        ChatSession.user_id == user_id,
        ChatSession.day_number == day,
        ChatSession.daily_topic.ilike(f"%{clean_subject_name}%")
    ).first()

    # Fallback: If it's missing the topic match, find the absolute latest active entry for this user/day
    if not session:
        session = db.query(ChatSession).filter(
            ChatSession.user_id == user_id,
            ChatSession.day_number == day
        ).order_by(ChatSession.created_at.desc()).first()

    # If absolutely no row exists in the database yet, return empty safely
    if not session:
        return {"messages": []}

    # 3. Call RAGService to fetch the array history with explicit offset values passed down
    messages = RAGService.get_chat_history(db, user_id, subject_name, day, skip=skip, limit=limit)
    
    # Ultimate fail-safe protection: if RAGService returns an empty array because of an internal ID check, 
    # query the messages table directly using the session ID we just found!
    if not messages:
        past_messages = db.query(Message).filter(
            Message.session_id == session.id
        ).order_by(Message.timestamp.desc()).offset(skip).limit(limit).all()
        
        # Format and invert back into chronological sequence for FlatList prepending logic
        messages = [
            {
                "id": f"msg_{msg.id}", 
                "role": str(msg.role).lower(), 
                "text": str(msg.content),
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None
            } 
            for msg in past_messages
        ][::-1]

    return {"messages": messages}

@router.get("/speak")
async def speak(text: str, voice: str = "en-IN-NeerjaNeural"):
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text is required")

    async def generate():
        communicate = edge_tts.Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data = chunk.get("data")
                if audio_data:
                    yield audio_data

    return StreamingResponse(generate(), media_type="audio/mpeg")

@router.post("/session/wrapup_by_context/{user_id}/{subject_name}/{day}")
async def wrapup_by_context(
    user_id: str,
    subject_name: str,
    day: int,
    db: Session = Depends(get_db)
):
    sessions = db.query(ChatSession).filter(
    ChatSession.user_id == user_id,
    ChatSession.day_number == day
    ).all()

    session = None
    max_messages = -1

    for s in sessions:
        count = db.query(Message).filter(
        Message.session_id == s.id
        ).count()

        if count > max_messages:
            max_messages = count
            session = s
    print("SELECTED SESSION:", session.id)
    print("SELECTED MESSAGE COUNT:", max_messages)

    if not session:
        raise HTTPException(status_code=404, detail="No session found")

    sessions = db.query(ChatSession).filter(
    ChatSession.user_id == user_id,
    ChatSession.day_number == day
    ).all()

    print("\n===== SESSION DEBUG =====")

    for s in sessions:
        count = db.query(Message).filter(
        Message.session_id == s.id
    ).count()

        print(
            f"ID={s.id} | Topic={s.daily_topic} | Messages={count}"
        )

    print("=========================\n")

    messages = db.query(Message).filter(
    Message.session_id == session.id
    ).order_by(Message.timestamp.asc()).all()
    print("=" * 50)
    print("WRAPUP SESSION ID:", session.id)
    print("WRAPUP TOPIC:", session.daily_topic)
    print("MESSAGE COUNT:", len(messages))
    print("=" * 50)

    history = [
        {
            "role": m.role,
            "content": m.content
        }
        for m in messages
    ]

    print("HISTORY SAMPLE:")
    for h in history[:5]:
        print(h)
    print("TOTAL HISTORY ITEMS:", len(history))
    recap = RAGService.generate_daily_recap(history)

    session.is_completed = True
    session.mastered_topics = recap.get("mastered", [])
    session.loopholes = recap.get("loopholes", [])
    db.commit()

    db.commit()

    return {
        "status": "success",
        "summary": recap
    }
    
@router.get("/today_recap/{user_id}")
async def get_today_recap(
    user_id: str,
    db: Session = Depends(get_db)
):

    # DEBUG: Show all completed sessions
    completed_sessions = (
        db.query(ChatSession)
        .filter(
            ChatSession.user_id == user_id,
            ChatSession.is_completed == True
        )
        .order_by(ChatSession.day_number.asc())
        .all()
    )

    print("\n" + "=" * 60)
    print("TODAY RECAP DEBUG")
    print(f"USER ID: {user_id}")
    print("=" * 60)

    for s in completed_sessions:
        print(
            f"ID={s.id} | "
            f"DAY={s.day_number} | "
            f"TOPIC={s.daily_topic} | "
            f"CREATED={s.created_at} | "
            f"COMPLETED={s.is_completed}"
        )

    print("=" * 60)

    # Get latest completed day
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.user_id == user_id,
            ChatSession.is_completed == True
        )
        .order_by(ChatSession.day_number.desc())
        .first()
    )

    if not session:
        print("❌ No completed session found")
        return {
            "completed": False,
            "message": "No completed session found"
        }

    print("✅ SELECTED SESSION")
    print(f"ID: {session.id}")
    print(f"DAY: {session.day_number}")
    print(f"TOPIC: {session.daily_topic}")
    print(f"MASTERED: {session.mastered_topics}")
    print(f"LOOPHOLES: {session.loopholes}")
    print("=" * 60 + "\n")

    response = {
        "completed": True,
        "day": session.day_number,
        "topic": session.daily_topic,
        "mastered": session.mastered_topics or [],
        "loopholes": session.loopholes or []
    }

    print("📦 RESPONSE SENT TO FRONTEND:")
    print(response)
    print("=" * 60 + "\n")

    return response