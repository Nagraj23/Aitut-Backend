from fastapi import FastAPI
from api.endpoints import chat

app = FastAPI(title="Ai-Tut Teacher Backend")

# Include our routes
app.include_router(chat.router, prefix="/api")

@app.get("/")
def health_check():
    return {"status": "Teacher AI is online 🎓"}