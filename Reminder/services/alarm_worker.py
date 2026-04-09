import time
import datetime
import redis  # New: Redis library
import json   # New: To send structured data
from typing import List
from db.session import SessionLocal
from db.models import Alarm

# 1. Initialize Redis Connection (ensure Redis server is running!)
# decode_responses=True helps us handle strings easily
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

def monitor_alarms():
    print("🚀 Background Alarm Monitor: Active [Redis Mode]")
    while True:
        with SessionLocal() as db:
            try:
                # Get current time in UTC
                now = datetime.datetime.now(datetime.timezone.utc)
                
                # Fetch alarms that are due
                due_alarms: List[Alarm] = db.query(Alarm).filter(
                    Alarm.is_active == True,
                    Alarm.is_fired == False,
                    Alarm.trigger_time <= now
                ).all()

                for alarm in due_alarms:
                    # LOG 1: Backend acknowledges the hit
                    print(f"⏰ TRIGGERING: {alarm.title}")
                    
                    # 2. STATE UPDATE: Prevent double triggers
                    alarm.is_fired = True
                    if not alarm.repeat_days:
                        alarm.is_active = False
                    
                    db.commit() # Save to DB first for reliability

                    # 3. REDIS PUBLISH: The real-time "shout" to the UI
                    # We send a JSON object so the UI knows exactly what happened
                    payload = {
                        "event": "ALARM_TRIGGER",
                        "title": alarm.title,
                        "alarm_id": alarm.id,
                        "type": "mcq_test"  # Tells UI to prep the test
                    }
                    
                    # Publish to a channel unique to the user
                    channel_name = f"user_notifications_{alarm.user_id}"
                    r.publish(channel_name, json.dumps(payload))
                    
                    print(f"📡 Redis Signal Sent to Channel: {channel_name}")

                # 4. DAILY RESET: (Your existing midnight logic)
                if now.hour == 0 and now.minute == 0 and now.second < 15:
                    db.query(Alarm).filter(Alarm.repeat_days.isnot(None)).update({"is_fired": False})
                    db.commit()
                    print("♻️ Repeating alarms reset for the new day.")

            except Exception as e:
                db.rollback()
                print(f"❌ Worker Error: {e}")
        
        # 5. POLL RATE: 1 second for precision, or 5-10 to save CPU
        time.sleep(1)