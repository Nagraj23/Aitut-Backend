from fastapi import FastAPI
from api.endpoints import chat
from db.database import init_db
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"

app = FastAPI(title="Ai-Tut Teacher Backend")

init_db()
# Include our routes
app.include_router(chat.router, prefix="/api")

@app.get("/")
def health_check():
    return {"status": "Teacher AI is online 🎓"}