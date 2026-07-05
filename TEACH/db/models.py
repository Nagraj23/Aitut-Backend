from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Text,Boolean
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class Department(Base):
    __tablename__ = "departments"
    id = Column(String, primary_key=True)  # e.g., "cse"
    name = Column(String)                  # e.g., "Computer Science"

class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True)
    dept_id = Column(String, ForeignKey("departments.id"))
    year = Column(Integer)                 # 1, 2, 3, or 4
    university = Column(String)
    name = Column(String)                  # e.g., "Physics"
    vector_collection = Column(String)     # Unique name for ChromaDB

# --- UPDATED: Added user_id and daily_plan storage ---
class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    day_number = Column(Integer)
    
    daily_topic = Column(String, nullable=True) 
    daily_task_json = Column(JSON, nullable=True) 
    
    # NEW: Structured summary columns
    mastered_topics = Column(JSON, nullable=True) # List of strings
    loopholes = Column(JSON, nullable=True)       # List of strings
    is_completed = Column(Boolean, default=False) # Standard Boolean
    
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    messages = relationship("Message", back_populates="session")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"))
    role = Column(String)                  # "user" or "assistant"
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")