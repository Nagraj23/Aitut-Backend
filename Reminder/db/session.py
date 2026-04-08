import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# 1. Safety check to prevent the "None" error
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL not found in environment variables. Check your .env file!")

# 2. Now Pylance knows DATABASE_URL is definitely a string
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        