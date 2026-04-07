from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Alarm(Base):
    __tablename__ = "alarms"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    # The scheduled time (ISO format or Timestamp)
    trigger_time = Column(DateTime(timezone=True), nullable=False)
    # To track if the alarm has already fired
    is_active = Column(Boolean, default=True)
    # For future logic: "1,2,3,4,5" for weekdays
    repeat_days = Column(String, nullable=True) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())