import datetime
import json

from db.session import SessionLocal
from db.models import Alarm

from config.redis import get_redis

# Get the Redis client
redis_client = get_redis()


def force_trigger_check():
    print("⏳ Manually invoking unified alarm check function...")

    with SessionLocal() as db:
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            future_window = now + datetime.timedelta(seconds=5)

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

            print(f"🔎 Found {len(due_alarms)} due alarms.")

            for alarm in due_alarms:
                print(f"💥 Processing row Match: {alarm.title}")

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

                redis_client.publish(
                    channel_name,
                    json.dumps(payload)
                )

                print(f"📡 Broadcast completed to: {channel_name}")

        except Exception as e:
            db.rollback()
            print(f"❌ Core Trigger Error: {e}")


if __name__ == "__main__":
    force_trigger_check()