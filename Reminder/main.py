import uvicorn
from fastapi import FastAPI

from api.routes import router
from db.models import Base
from db.session import engine
from config.redis import get_redis

# Create tables in Postgres if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Nagraj's Study Reminder API")


@app.on_event("startup")
async def startup():
    try:
        redis_client = get_redis()

        print("🔄 Checking Redis Connection...")

        if redis_client.ping():
            print("✅ Redis Connected Successfully")
        else:
            print("❌ Redis Ping Failed")

    except Exception as e:
        print(f"❌ Redis Connection Error: {e}")


app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)