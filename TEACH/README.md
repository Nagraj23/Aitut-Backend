# Ai-Tut Teacher Backend 🎓

[![FastAPI](https://img.shields.io/badge/FastAPI-Modern%20Web-brightgreen)](https://fastapi.tiangolo.com/) [![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector%20DB-orange)](https://docs.trychroma.com/) [![Groq](https://img.shields.io/badge/Groq-LLM%20Inference-blue)](https://groq.com/) [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-purple)](https://www.postgresql.org/)

## 🚀 Overview
Ai-Tut is an AI-powered tutoring backend for engineering students (initially Solapur University CSE Year 1). It uses **RAG (Retrieval-Augmented Generation)** to provide personalized tutoring from uploaded PDF textbooks/notes/syllabi. 

**Key Features:**
- 📚 **PDF Ingestion**: Upload course materials (physics, chemistry) to ChromaDB vector store.
- 💬 **Interactive Chat**: Daily topic-based tutoring sessions with conversation history.
- 🎯 **Session Tracking**: Track student progress per day/topic, generate recaps (mastered topics, loopholes).
- 🔊 **Text-to-Speech**: Real-time audio responses (Indian English voice).
- 🗄️ **Hybrid DB**: PostgreSQL for metadata/sessions + ChromaDB for embeddings.
- 🤖 **Groq LLM**: Fast inference with Llama-3.3-70b-versatile.

Supports structured paths like `/solapur/cse/1/physics`.

## 🏗️ Architecture
```
Ai-Tut Backend
├── main.py                # FastAPI app (/, /api/chat endpoints)
├── api/endpoints/chat.py  # Upload PDF, ask questions, TTS, session wrapup
├── services/rag_service.py # RAG pipeline (ingest, query, recap)
├── db/                    # SQLAlchemy + Postgres (subjects, sessions
