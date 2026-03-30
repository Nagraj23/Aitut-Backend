import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from db.database import get_db 
from db import models
from services.rag_service import RAGService

router = APIRouter()

class QuestionRequest(BaseModel):
    question: str

@router.post("/upload/{dept}/{year}/{subject_name}")
async def upload_pdf(
    dept: str, 
    year: int, 
    subject_name: str, 
    doc_type: str = "notes", 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    clean_subject = subject_name.strip().lower().replace(" ", "_")
    vector_id = f"{dept}_{year}_{clean_subject}".lower().replace(" ", "_")

    dir_path = f"data/{dept}/year_{year}/{vector_id}"
    os.makedirs(dir_path, exist_ok=True)
    
    # Fix for the "os.path.join" red line
    safe_filename = str(file.filename) if file.filename else "file.pdf"
    file_path = os.path.join(dir_path, safe_filename)
    
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Database Registration
    department = db.query(models.Department).filter(models.Department.id == dept.lower()).first()
    if not department:
        department = models.Department(id=dept.lower(), name=dept.upper())
        db.add(department)
        db.commit()

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

    status = RAGService.ingest_pdf(file_path, vector_id, doc_type=doc_type)
    
    return {
        "status": status, 
        "subject_id": subj.id, 
        "collection_name": vector_id,
        "type": doc_type
    }

@router.post("/ask/{dept}/{year}/{subject_name}/{day}")
async def ask_teacher(
    dept: str, 
    year: int, 
    subject_name: str, 
    day: int, 
    request: QuestionRequest, 
    db: Session = Depends(get_db)
):
    clean_name = subject_name.strip().lower().replace(" ", "_")

    subj = db.query(models.Subject).filter(
        models.Subject.dept_id == dept.lower(),
        models.Subject.year == year,
        models.Subject.name == clean_name
    ).first()

    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")

    session = db.query(models.ChatSession).filter(
        models.ChatSession.subject_id == subj.id,
        models.ChatSession.day_number == day
    ).first()

    if not session:
        session = models.ChatSession(subject_id=subj.id, day_number=day)
        db.add(session)
        db.commit()
        db.refresh(session)

    history_objs = db.query(models.Message).filter(
        models.Message.session_id == session.id
    ).order_by(models.Message.timestamp.desc()).limit(6).all()
    
    chat_context = [{"role": m.role, "content": m.content} for m in reversed(history_objs)]

    # Fix for the Groq "messages" red line
    answer = RAGService.get_teacher_response(
        question=request.question, 
        subject=subj.vector_collection, # type: ignore
        history=chat_context 
    )

    db.add(models.Message(session_id=session.id, role="user", content=request.question))
    db.add(models.Message(session_id=session.id, role="assistant", content=answer))
    db.commit()

    return {
        "answer": answer, 
        "day": day,
        "subject": subj.name
    }