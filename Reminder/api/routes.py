import asyncio
import json
import redis
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import Alarm
from pydantic import BaseModel
from datetime import datetime
from .auth import verify_token 

router = APIRouter()

# Initialize Redis connection
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

class AlarmCreate(BaseModel):
    title: str
    trigger_time: datetime

@router.post("/alarms/")
def create_alarm(
    alarm_data: AlarmCreate, 
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    spring_user_id = token_data.get("sub") 
    
    new_alarm = Alarm(
        title=alarm_data.title,
        trigger_time=alarm_data.trigger_time,
        user_id=spring_user_id,
        is_active=True,
        is_fired=False
    )
    db.add(new_alarm)
    db.commit()
    return {"status": "success", "id": new_alarm.id}

@router.get("/alarms/active")
def list_active_alarms(
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    # FIX: Use .get("sub") to stay consistent with your Create route
    user_id = token_data.get("sub")
    return db.query(Alarm).filter(
        Alarm.is_active == True,
        Alarm.user_id == user_id
    ).all()

# --- NEW: THE LISTENING PIPE ---

@router.get("/alarms/listen")
async def listen_to_alarms(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    user_id = token_data.get("sub")

    async def event_generator():
        # 1. Subscribe to the user's Redis channel
        pubsub = r.pubsub()
        channel_name = f"user_notifications_{user_id}"
        pubsub.subscribe(channel_name)
        
        print(f"🔌 Student {user_id} connected to real-time alarm pipe")

        try:
            while True:
                # 2. Check if browser tab was closed
                if await request.is_disconnected():
                    break

                message = pubsub.get_message()
                if message and message['type'] == 'message':
                        yield f"data: {message['data']}\n\n"
                
                if message:
                    # 'yield' sends the data to the UI immediately
                    yield f"data: {message['data']}\n\n"
                
                # 4. Stay efficient
                await asyncio.sleep(0.5) 

        except Exception as e:
            print(f"❌ Pipe Error: {e}")
        finally:
            pubsub.unsubscribe(channel_name)
            pubsub.close()

    # Returns the continuous 'stream' of data to React
    return StreamingResponse(event_generator(), media_type="text/event-stream")