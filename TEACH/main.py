from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # <--- Add this
from api.endpoints import chat
from db.database import init_db
import os

os.environ["ANONYMIZED_TELEMETRY"] = "False"

app = FastAPI(title="Ai-Tut Teacher Backend")

# --- ADD THIS BLOCK ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (POST, GET, etc.)
    allow_headers=["*"],  # Allows all headers
)
# ----------------------

init_db()

app.include_router(chat.router, prefix="/api")

@app.get("/")
def health_check():
    return {"status": "Teacher AI is online 🎓"}