import datetime
import json
import os
import redis
from celery_app import celery_app
from db.session import SessionLocal
from db.models import Alarm

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Standard client connection for synchronous Celery workers
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

@celery_app.task
def check_and_trigger_alarms():
    """
    The Single Unified System Trigger Core.
    Configured via Celery Beat to execute safely every 5 seconds.
    """
    with SessionLocal() as db:
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            # 5-second buffer window to capture any processing time differences
            future_window = now + datetime.timedelta(seconds=5)

            # with_for_update blocks concurrent task instances from picking up identical rows
            due_alarms = (
                db.query(Alarm)
                .filter(
                    Alarm.is_active == True,
                    Alarm.is_fired == False,
                    Alarm.trigger_time <= future_window
                )
                .with_for_update(skip_locked=True)
                .all()
            )

            for alarm in due_alarms:
                print(f"⏰ TRIGGERING UNIQUE ALARM: {alarm.title} for user {alarm.user_id}")

                # Update operational visibility markers
                alarm.is_fired = True
                if not alarm.repeat_days:
                    alarm.is_active = False

                db.commit()

                # Structural message payload parsed out by your React/Vue components
                payload = {
                    "event": "ALARM_TRIGGER",
                    "title": alarm.title,
                    "alarm_id": alarm.id,
                    "type": "mcq_test"
                }

                channel_name = f"user_notifications_{alarm.user_id}"
                
                try:
                    r.publish(channel_name, json.dumps(payload))
                except Exception:
                    print(f"⚠️ Redis publish failed for channel {channel_name}. Retrying once...")
                    r.publish(channel_name, json.dumps(payload))

                print(f"📡 Event safely pushed down → {channel_name}")

            # Mid-night cleanup sequence handling recurring weekly schedules
            if now.hour == 0 and now.minute == 0 and now.second < 10:
                db.query(Alarm).filter(Alarm.repeat_days.isnot(None)).update({"is_fired": False})
                db.commit()
                print("♻️ Repeating alarms successfully reset for the new calendar day.")

        except Exception as e:
            db.rollback()
            print(f"❌ Core Trigger System Error: {e}")