from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel
from services.rag_service import RAGService
import os

router = APIRouter()

# -----------------------------
# Request Model
# -----------------------------
class QuestionRequest(BaseModel):
    question: str


@router.post("/upload/{subject}")
async def upload_pdf(subject: str, file: UploadFile = File(...)):
    file_path = f"data/{file.filename}"

    with open(file_path, "wb") as f:
        f.write(await file.read())

    status = RAGService.ingest_pdf(file_path, subject)
    return {"status": status}


@router.post("/ask/{subject}")
async def ask_teacher(subject: str, request: QuestionRequest):
    answer = RAGService.get_teacher_response(
        request.question,
        subject
    )
    return {"answer": answer}
