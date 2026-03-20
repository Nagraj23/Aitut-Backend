import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

# Local imports - ensuring these match your project structure
from db.database import get_db 
from db import models
from services.rag_service import RAGService

router = APIRouter()

# -----------------------------
# Request Models
# -----------------------------
class QuestionRequest(BaseModel):
    question: str

# -----------------------------
# 1. PDF Upload with Hierarchy
# -----------------------------
@router.post("/upload/{dept}/{year}/{subject_name}")
async def upload_pdf(
    dept: str, 
    year: int, 
    subject_name: str, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    # Standardize the subject name and vector ID
    clean_subject = subject_name.strip().capitalize()
    vector_id = f"{dept}_{year}_{clean_subject}".lower().replace(" ", "_")

    # A. Physical File Storage
    dir_path = f"data/{dept}/year_{year}/{vector_id}"
    os.makedirs(dir_path, exist_ok=True)
    file_path = str(os.path.join(dir_path, str(file.filename)))
    
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # B. Database Registration (Postgres)
    # Check if department exists, if not, create it
    department = db.query(models.Department).filter(models.Department.id == dept.lower()).first()
    if not department:
        department = models.Department(id=dept.lower(), name=dept.upper())
        db.add(department)
        db.commit()

    # Check if subject exists
    subj = db.query(models.Subject).filter(models.Subject.vector_collection == vector_id).first()
    if not subj:
        subj = models.Subject(
            dept_id=dept.lower(), 
            year=year, 
            name=clean_subject, 
            vector_collection=vector_id
        )
        db.add(subj)
        db.commit()
        db.refresh(subj)

    # C. Ingest into ChromaDB via RAGService
    status = RAGService.ingest_pdf(file_path, vector_id)
    
    return {
        "status": status, 
        "subject_id": subj.id, 
        "collection_name": vector_id
    }

# -----------------------------
# 2. Ask Teacher with History (The "Recap" Logic)
# -----------------------------
@router.post("/ask/{dept}/{year}/{subject_name}/{day}")
async def ask_teacher(
    dept: str, 
    year: int, 
    subject_name: str, 
    day: int, 
    request: QuestionRequest, 
    db: Session = Depends(get_db)
):
    # A. Verify Subject exists in Hierarchy
    subj = db.query(models.Subject).filter(
        models.Subject.dept_id == dept.lower(),
        models.Subject.year == year,
        models.Subject.name == subject_name.capitalize()
    ).first()

    if not subj:
        raise HTTPException(
            status_code=404, 
            detail=f"Subject '{subject_name}' not registered for {dept} Year {year}. Please upload PDF first."
        )

    # B. Handle Day-wise Session
    session = db.query(models.ChatSession).filter(
        models.ChatSession.subject_id == subj.id,
        models.ChatSession.day_number == day
    ).first()

    if not session:
        session = models.ChatSession(subject_id=subj.id, day_number=day)
        db.add(session)
        db.commit()
        db.refresh(session)

    # C. Prepare History Context (Last 6 messages for better recap memory)
    history_objs = db.query(models.Message).filter(
        models.Message.session_id == session.id
    ).order_by(models.Message.timestamp.desc()).limit(6).all()
    
    # We reverse because we want chronological order for the AI
    chat_context = [{"role": m.role, "content": m.content} for m in reversed(history_objs)]

    # D. Get AI Response from RAGService
    # Ensure your RAGService.get_teacher_response accepts 'history'
    answer = RAGService.get_teacher_response(
        question=request.question, 
        subject=subj.vector_collection,
        history=chat_context 
    )

    # E. Save New Interaction
    user_msg = models.Message(session_id=session.id, role="user", content=request.question)
    ai_msg = models.Message(session_id=session.id, role="assistant", content=answer)
    
    db.add(user_msg)
    db.add(ai_msg)
    db.commit()

    return {
        "answer": answer, 
        "day": day,
        "session_id": session.id,
        "subject": subj.name
    }