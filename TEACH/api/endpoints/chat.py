import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from db.database import get_db
from db import models
from services.rag_service import RAGService
from services.gemini_service import get_gemini_response

router = APIRouter()


# ============================================================
# PYDANTIC MODELS
# ============================================================

class QuestionRequest(BaseModel):
    question: str


class HistoryItem(BaseModel):
    role: str       # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    question: str
    university: str = "general"
    branch: str = "cse"
    year: int = 1
    subject: str = "general"
    history: Optional[List[HistoryItem]] = []
    use_rag: bool = True


class ChatResponse(BaseModel):
    answer: str
    source: str     # "rag+gemini" or "gemini"


# ============================================================
# EXISTING ENDPOINT 1 — PDF Upload (unchanged, kept as-is)
# ============================================================

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
    clean_subject = subject_name.strip().lower().replace(" ", "_")
    vector_id = f"{uni}_{dept}_{year}_{clean_subject}".lower()
    safe_filename = str(file.filename) if file.filename else "file.pdf"

    # Auto-detect syllabus from filename
    final_doc_type = doc_type.lower()
    if "syllabus" in safe_filename.lower():
        final_doc_type = "syllabus"

    # Register subject in SQL if not exists
    subj = db.query(models.Subject).filter(
        models.Subject.vector_collection == vector_id
    ).first()

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

    # Save file to disk
    dir_path = f"data/{dept}/year_{year}/{vector_id}"
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, safe_filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Ingest into ChromaDB
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


# ============================================================
# EXISTING ENDPOINT 2 — Ask Teacher with Day/Session (unchanged)
# ============================================================

@router.post("/ask/{uni}/{dept}/{year}/{subject_name}/{day}")
async def ask_teacher(
    uni: str,
    dept: str,
    year: int,
    subject_name: str,
    day: int,
    request: QuestionRequest,
    db: Session = Depends(get_db)
):
    clean_name = subject_name.strip().lower().replace(" ", "_")

    print(f"--- DEBUGGING SQL SEARCH ---")
    print(f"Target Dept: {dept.lower()} | Year: {year} | Subject: {clean_name}")

    subj = db.query(models.Subject).filter(
        models.Subject.dept_id == dept.lower(),
        models.Subject.year == year,
        models.Subject.name == clean_name
    ).first()

    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found in database")

    # Get or create chat session for this day
    session = db.query(models.ChatSession).filter(
        models.ChatSession.subject_id == subj.id,
        models.ChatSession.day_number == day
    ).first()

    if not session:
        session = models.ChatSession(subject_id=subj.id, day_number=day)
        db.add(session)
        db.commit()
        db.refresh(session)

    # Fetch last 6 messages for context
    history_objs = db.query(models.Message).filter(
        models.Message.session_id == session.id
    ).order_by(models.Message.timestamp.desc()).limit(6).all()

    chat_context = [
        {"role": m.role, "content": m.content}
        for m in reversed(history_objs)
    ]

    # RAG response using Groq (your original flow)
    answer = RAGService.get_teacher_response(
        question=request.question,
        university=uni,
        branch=dept,
        year=year,
        subject=clean_name,
        history=chat_context
    )

    # Persist messages
    db.add(models.Message(session_id=session.id, role="user", content=request.question))
    db.add(models.Message(session_id=session.id, role="assistant", content=answer))
    db.commit()

    return {
        "answer": answer,
        "day": day,
        "subject": subj.name
    }


# ============================================================
# NEW ENDPOINT 3 — General Chatbot (React Native ChatScreen)
#   Route: POST /api/chat
#   Flow:  RAG (ChromaDB) → Gemini (enriched or fallback)
# ============================================================

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    history_dicts = [h.model_dump() for h in req.history] if req.history else []

    rag_context = ""

    # Step 1: Try RAG — pull relevant notes from ChromaDB
    if req.use_rag:
        try:
            rag_answer = RAGService.get_teacher_response(
                question=req.question,
                university=req.university,
                branch=req.branch,
                year=req.year,
                subject=req.subject,
                history=history_dicts
            )
            # Only use RAG result if it actually found something
            if rag_answer and "No relevant notes found" not in rag_answer:
                rag_context = rag_answer
        except Exception as e:
            print(f"RAG Error (non-fatal, falling back to Gemini): {e}")

    # Step 2: Send to Gemini with or without RAG context
    if rag_context:
        enriched_question = (
            f"Based on the following notes from the student's syllabus, answer their question.\n\n"
            f"NOTES CONTEXT:\n{rag_context}\n\n"
            f"STUDENT QUESTION: {req.question}\n\n"
            f"Prefer the notes content if relevant, otherwise use your knowledge."
        )
        final_answer = get_gemini_response(
            question=enriched_question,
            university=req.university,
            branch=req.branch,
            year=req.year,
            subject=req.subject,
            history=history_dicts
        )
        source = "rag+gemini"
    else:
        final_answer = get_gemini_response(
            question=req.question,
            university=req.university,
            branch=req.branch,
            year=req.year,
            subject=req.subject,
            history=history_dicts
        )
        source = "gemini"

    return ChatResponse(answer=final_answer, source=source)


# ============================================================
# HEALTH CHECK
# ============================================================

@router.get("/chat/health")
def chat_health():
    return {"status": "Chat API is live ✅", "endpoints": ["/upload", "/ask", "/chat"]}