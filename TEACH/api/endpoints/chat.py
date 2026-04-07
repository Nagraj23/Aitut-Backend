import os
from fastapi import Form, File, UploadFile
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from db.database import get_db 
from db import models
from services.rag_service import RAGService
from fastapi.responses import StreamingResponse
import edge_tts
import io

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
    # 1. Standardize subject name for DB lookup
    clean_name = subject_name.strip().lower().replace(" ", "_")

    # 2. Find the Subject in your SQL Table
    subj = db.query(models.Subject).filter(
        models.Subject.dept_id == dept.lower(),
        models.Subject.year == year,
        models.Subject.name == clean_name
    ).first()

    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found in database")

    # 3. Handle Chat Session (using your UUID-based ChatSession model)
    session = db.query(models.ChatSession).filter(
        models.ChatSession.user_id == request.user_id, # <-- User Filter
        models.ChatSession.subject_id == subj.id,
        models.ChatSession.day_number == day           # <-- Day Filter
    ).first()

    if not session:
        print(f"🆕 [API] Creating new Day {day} session for {request.user_id}")
        session = models.ChatSession(
            user_id=request.user_id,
            subject_id=subj.id,
            day_number=day,
            daily_topic=request.topic
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    # 4. Fetch History from Message Model (Limit to last 6 for context)
    history_objs = db.query(models.Message).filter(
        models.Message.session_id == session.id
    ).order_by(models.Message.timestamp.desc()).limit(6).all()
    
    # Format history for the AI (Oldest to Newest)
    chat_context = [{"role": m.role, "content": m.content} for m in reversed(history_objs)]

    # 5. Call the RAG Service (The "Master Tutor" logic)
    # This merges data from your 3 textbooks in ChromaDB
    answer = RAGService.get_teacher_response(
        question=request.message, 
        university=uni,
        branch=dept,
        year=year,
        subject=clean_name,
        daily_task={
            "day": day,
            "topic": request.topic,
            "task": request.task
        },
        history=chat_context 
    )

    # 6. Save BOTH messages to your SQL Message Table
    # Save the User's input
    user_content = request.message if request.message.strip() else f"Started: {request.topic}"
    db.add(models.Message(session_id=session.id, role="user", content=user_content))
    db.add(models.Message(session_id=session.id, role="assistant", content=answer))
    db.commit()

    # 7. Final Response to UI
    return {
        "answer": answer,
        "session_id": session.id,
        "topic": request.topic,
        "day": day,
        "subject": subj.name,
        "is_new_session": not bool(history_objs)
    }
    
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