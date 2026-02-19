from fastapi import APIRouter, UploadFile, File
from services.rag_service import RAGService
import os

router = APIRouter()

@router.post("/upload/{subject}")
async def upload_pdf(subject: str, file: UploadFile = File(...)):
    # Save file temporarily
    file_path = f"data/{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    # Process PDF
    status = RAGService.ingest_pdf(file_path, subject)
    return {"status": status}

@router.post("/ask/{subject}")
async def ask_teacher(subject: str, question: str):
    answer = RAGService.get_teacher_response(question, subject)
    return {"answer": answer}