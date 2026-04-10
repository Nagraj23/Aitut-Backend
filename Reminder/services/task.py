import datetime
import json
import redis
from celery_app import celery_app
from db.session import SessionLocal
from db.models import Alarm

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

@celery_app.task
def check_and_trigger_alarms():
    print("🚀 Celery Alarm Check Running...")

    with SessionLocal() as db:
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            future_window = now + datetime.timedelta(seconds=5)

            print(f"👀 Checking at {now}")

            due_alarms = db.query(Alarm).filter(
                Alarm.is_active == True,
                Alarm.is_fired == False,
                Alarm.trigger_time <= future_window
            ).all()

            for alarm in due_alarms:
                print(f"⏰ TRIGGERING: {alarm.title}")

                alarm.is_fired = True
                if not alarm.repeat_days:
                    alarm.is_active = False

                db.commit()

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
                    print("⚠️ Redis retry...")
                    r.publish(channel_name, json.dumps(payload))

                print(f"📡 Sent → {channel_name}")

        except Exception as e:
            db.rollback()
            print(f"❌ Worker Error: {e}")