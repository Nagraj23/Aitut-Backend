import threading
from fastapi import FastAPI
from api.routes import router
from db.models import Base
from db.session import engine
from services.alarm_worker import monitor_alarms

# Create tables in Postgres if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Nagraj's Study Reminder API")

app.include_router(router)

@app.on_event("startup")
def start_worker():
    # daemon=True ensures the worker dies if you stop the main app
    worker_thread = threading.Thread(target=monitor_alarms, daemon=True)
    worker_thread.start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)