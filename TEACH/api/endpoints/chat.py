import os
from fastapi import Form, File, UploadFile
import shutil
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from db.models import ChatSession, Message, Subject
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from db.database import get_db 
from db import models
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from services.rag_service import RAGService
from fastapi.responses import StreamingResponse
import logging
import edge_tts
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import ChatSession, Message
from services.rag_service import RAGService
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
import io

logger = logging.getLogger(__name__)

router = APIRouter()

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

    # A. Ensure Department exists (Fixes the ForeignKeyViolation)
    dept_obj = db.query(models.Department).filter(models.Department.id == dept_id_clean).first()
    
    if not dept_obj:
        # Create department on the fly
        dept_obj = models.Department(
            id=dept_id_clean, 
            name=dept.upper() 
        )
        db.add(dept_obj)
        db.commit() # Essential: Save the department so the subject can find it
        db.refresh(dept_obj)

    # B. Check if Subject exists, if not, create it
    subj = db.query(models.Subject).filter(models.Subject.vector_collection == vector_id).first()
    
    if not subj:
        subj = models.Subject(
            name=clean_subject,
            university=uni.lower(),
            dept_id=dept_obj.id, # Uses the foreign key from the department we checked/created
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
    
    # Save file content
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
    # 1. Normalize for DB (Match the logic in your Subject table)
    # Using ilike in the query is safer than manual normalization
    subj = db.query(models.Subject).filter(
        models.Subject.dept_id == dept.lower(),
        models.Subject.year == year,
        models.Subject.name.ilike(subject_name) 
    ).first()

    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")

    # 2. Fetch or Create Session
    # Note: request.topic should be dynamic based on your syllabus/day roadmap
    session = db.query(models.ChatSession).filter(
        models.ChatSession.user_id == request.user_id,
        models.ChatSession.subject_id == subj.id,
        models.ChatSession.day_number == day
    ).first()

    if not session:
        session = models.ChatSession(
            user_id=request.user_id,
            subject_id=subj.id,
            day_number=day,
            daily_topic=request.topic, # Provided by frontend or roadmap logic
            daily_task_json={"task": request.task, "topic": request.topic}
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    # 3. Handle Streaming with the TeacherService logic
    # We pass the db session so the method can handle the final save internally
    
    return StreamingResponse(
        RAGService.get_teacher_response(
            db=db,
            user_id=request.user_id,
            university=uni,
            branch=dept,
            year=year,
            subject_name=getattr(subj, "name"),
            day=day,
            question=request.message
        ),
        media_type="text/event-stream"
    )
   

@router.get("/history/{user_id}/{subject_name}/{day}")
async def get_session_history(user_id: str, subject_name: str, day: int, db: Session = Depends(get_db)):
    
    # 1. Use the Capitalized class name "Subject"
    subj = db.query(Subject).filter(Subject.name.ilike(subject_name)).first()
    
    if not subj:
        return {"messages": []}

    # 2. Use "ChatSession" exactly as imported
    session = db.query(ChatSession).filter(
        ChatSession.user_id == user_id,
        ChatSession.subject_id == subj.id,
        ChatSession.day_number == day
    ).first()

    if not session:
        return {"messages": []}

    # 3. Use your RAGService to get formatted messages
    messages = RAGService.get_chat_history(db, user_id, subject_name, day)
    return {"messages": messages}

@router.get("/speak")
async def speak(text: str, voice: str = "en-IN-NeerjaNeural"):
    """
    Converts text to an MP3 audio stream using Edge-TTS.
    Default voice: en-IN-NeerjaNeural (Natural Indian English)
    """
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


@router.post("/session/{session_id}/wrapup")
async def wrapup_chat_session(session_id: str, db: Session = Depends(get_db)):
    # 1. Fetch the Chat Session
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 2. Fetch all messages in this session to analyze
    messages = db.query(Message).filter(Message.session_id == session_id).order_by(Message.timestamp.asc()).all()
    
    if not messages:
        return {"message": "No conversation found to summarize."}

    # 3. Format history for the AI
    history_data = [
        {"role": msg.role, "content": msg.content} 
        for msg in messages
    ]

    try:
        recap = RAGService.generate_daily_recap(history_data)
        
        setattr(session, 'is_completed', True)
        setattr(session, 'mastered_topics', recap.get("mastered", []))
        setattr(session, 'loopholes', recap.get("loopholes", []))
        
        db.commit()
        db.refresh(session)
        
        logger.info(f"Session {session_id} wrapped up successfully.")
        
        return {
            "status": "success",
            "day": session.day_number,
            "summary": recap
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error wrapping up session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate daily recap")