from fastapi import FastAPI
from api.routes import router
from db.models import Base
from db.session import engine

# Create tables in Postgres if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Nagraj's Study Reminder API")

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)