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

router = APIRouter()

class QuestionRequest(BaseModel):
    question: str

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
    vector_id = f"{uni}_{dept}_{year}_{clean_subject}".lower()
    safe_filename = str(file.filename) if file.filename else "file.pdf"

    # 2. Auto-Detect Syllabus (Fixes your previous roadmap bug)
    final_doc_type = doc_type.lower()
    if "syllabus" in safe_filename.lower():
        final_doc_type = "syllabus"

    # --- SQL REGISTRATION (The "Librarian") ---
    # Check if subject exists, if not, create it
    subj = db.query(models.Subject).filter(models.Subject.vector_collection == vector_id).first()
    
    if not subj:
        subj = models.Subject(
            name=clean_subject,
            university=uni.lower(),
            branch=dept.lower(),
            year=year,
            vector_collection=vector_id
        )
        db.add(subj)
        db.commit()
        db.refresh(subj)

    # 3. Save physical file to disk
    dir_path = f"data/{dept}/year_{year}/{vector_id}"
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, safe_filename)
    
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # --- CHROMA INGESTION (The "Bookshelf") ---
    status = RAGService.ingest_pdf(
        file_path=file_path,
        university=uni,
        branch=dept,
        year=year,
        subject=clean_subject,
        doc_type=final_doc_type
    )
    
    return {
        "status": status, 
        "subject_id": subj.id, 
        "type_assigned": final_doc_type
    }
    
@router.post("/ask/{uni}/{dept}/{year}/{subject_name}/{day}")
async def ask_teacher(
    uni:str,
    dept: str, 
    year: int, 
    subject_name: str, 
    day: int, 
    request: QuestionRequest, 
    db: Session = Depends(get_db)
):
    # university = "dbatu"
    clean_name = subject_name.strip().lower().replace(" ", "_")

    print(f"--- DEBUGGING SQL SEARCH ---")
    print(f"Target Dept ID: {dept.lower()}")
    print(f"Target Year: {year}")
    print(f"Target Subject Name: {clean_name}")
    
    subj = db.query(models.Subject).filter(
        models.Subject.dept_id == dept.lower(),
        models.Subject.year == year,
        models.Subject.name == clean_name
    ).first()

    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Handle Chat Session
    session = db.query(models.ChatSession).filter(
        models.ChatSession.subject_id == subj.id,
        models.ChatSession.day_number == day
    ).first()

    if not session:
        session = models.ChatSession(subject_id=subj.id, day_number=day)
        db.add(session)
        db.commit()
        db.refresh(session)

    # Get Chat History
    history_objs = db.query(models.Message).filter(
        models.Message.session_id == session.id
    ).order_by(models.Message.timestamp.desc()).limit(6).all()
    
    chat_context = [{"role": m.role, "content": m.content} for m in reversed(history_objs)]

    # UPDATED CALL: Pass the full hierarchy to get_teacher_response
    answer = RAGService.get_teacher_response(
        question=request.question, 
        university=uni,
        branch=dept,
        year=year,
        subject=clean_name,
        history=chat_context 
    )

    # Save to DB
    db.add(models.Message(session_id=session.id, role="user", content=request.question))
    db.add(models.Message(session_id=session.id, role="assistant", content=answer))
    db.commit()

    return {
        "answer": answer, 
        "day": day,
        "subject": subj.name
    }