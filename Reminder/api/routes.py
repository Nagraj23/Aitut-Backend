from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import Alarm
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

# Schema for incoming data
class AlarmCreate(BaseModel):
    title: str
    trigger_time: datetime

@router.post("/alarms/")
def create_study_alarm(alarm_data: AlarmCreate, db: Session = Depends(get_db)):
    new_alarm = Alarm(
        title=alarm_data.title,
        trigger_time=alarm_data.trigger_time,
        is_active=True
    )
    db.add(new_alarm)
    db.commit()
    db.refresh(new_alarm)
    return {"message": "Alarm scheduled successfully", "id": new_alarm.id}

@router.get("/alarms/active")
def list_active_alarms(db: Session = Depends(get_db)):
    return db.query(Alarm).filter(Alarm.is_active == True).all()