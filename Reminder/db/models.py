import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

from sqlalchemy.orm import Mapped, mapped_column

class Alarm(Base):
    __tablename__ = "alarms"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(nullable=False)
    trigger_time: Mapped[datetime.datetime] = mapped_column(nullable=False)

    is_active: Mapped[bool] = mapped_column(default=True)
    is_fired: Mapped[bool] = mapped_column(default=False)

    repeat_days: Mapped[str | None] = mapped_column(nullable=True)
    user_id: Mapped[str] = mapped_column(index=True)