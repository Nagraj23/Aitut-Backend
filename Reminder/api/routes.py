import asyncio
import json
# Use the async driver to handle streaming connections gracefully
from config.redis import get_async_redis

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import Alarm
from pydantic import BaseModel
from datetime import datetime
from .auth import verify_token 

router = APIRouter()

from config.redis import get_redis


class AlarmCreate(BaseModel):
    title: str
    trigger_time: datetime

@router.post("/alarms/")
def create_alarm(
    alarm_data: AlarmCreate, 
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    spring_user_id = token_data.get("user_id")
    
    new_alarm = Alarm(
        title=alarm_data.title,
        trigger_time=alarm_data.trigger_time,
        user_id=spring_user_id,
        is_active=True,
        is_fired=False
    )
    db.add(new_alarm)
    db.commit()
    db.refresh(new_alarm)
    return {"status": "success", "id": new_alarm.id}

@router.get("/alarms/active")
def list_active_alarms(
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    user_id = token_data.get("user_id")
    return db.query(Alarm).filter(
        Alarm.is_active == True,
        Alarm.user_id == user_id
    ).all()

# --- FIXED: THE REAL-TIME SSE LISTENING PIPE ---

@router.get("/alarms/listen")
async def listen_to_alarms(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    user_id = token_data.get("user_id")

    async def event_generator():
        # Open an async redis socket connection dedicated to this user's stream
        async_redis = get_async_redis()

        pubsub = async_redis.pubsub()
        channel_name = f"user_notifications_{user_id}"
        await pubsub.subscribe(channel_name)
        
        print(f"🔌 Student {user_id} connected to real-time alarm pipe")

        try:
            while True:
                # Close down channels gracefully if the user navigates away or shuts the app
                if await request.is_disconnected():
                    print(f"🔌 Student {user_id} disconnected from pipe")
                    break

                # Non-blocking pop from our Redis PubSub channel
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] == 'message':
                    yield f"data: {message['data']}\n\n"
                else:
                    # Send a silent keep-alive comment frame to prevent client connection timeouts
                    yield ": keep-alive ping\n\n"
                
                await asyncio.sleep(0.5) 

        except Exception as e:
            print(f"❌ Pipe Error for user {user_id}: {e}")
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()
            await async_redis.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")