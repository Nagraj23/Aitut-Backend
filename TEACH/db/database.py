from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models import Base

# Change this to your actual Postgres credentials
DATABASE_URL = "postgresql://postgres:Nagraj@2005@localhost:5432/Aitut"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# This creates the tables in Postgres if they don't exist
def init_db():
    Base.metadata.create_all(bind=engine)

# This is what you use in your routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()