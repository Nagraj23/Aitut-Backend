from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import Alarm
from pydantic import BaseModel
from datetime import datetime
# Import the verification logic
from .auth import verify_token 

router = APIRouter()

class AlarmCreate(BaseModel):
    title: str
    trigger_time: datetime

@router.post("/alarms/")
def create_alarm(
    alarm_data: AlarmCreate, 
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token) # Auth Guard
):
    # 'sub' is the standard field for User ID in JWT
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
    # Only return alarms belonging to the logged-in user
    return db.query(Alarm).filter(
        Alarm.is_active == True,
        Alarm.user_id == token_data["user_id"]
    ).all()