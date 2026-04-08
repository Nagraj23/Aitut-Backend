import time
import datetime
from typing import List
from db.session import SessionLocal
from db.models import Alarm

def monitor_alarms():
    print("🚀 Background Alarm Monitor: Active")
    while True:
        with SessionLocal() as db:
            try:
                # Use UTC to stay in sync with Spring/PostgreSQL
                now = datetime.datetime.now(datetime.timezone.utc)
                
                # TYPE HINT: Fixes 'Cannot assign to attribute' error
                due_alarms: List[Alarm] = db.query(Alarm).filter(
                    Alarm.is_active == True,
                    Alarm.is_fired == False,
                    Alarm.trigger_time <= now
                ).all()

                for alarm in due_alarms:
                    # TERMINAL LOG: This is your test signal
                    print(f"⏰ TRIGGERING: {alarm.title}")
                   
                    if alarm.repeat_days:
                        alarm.is_fired = True
                    else:
                        alarm.is_active = False
                        alarm.is_fired = True
                    
                    db.commit()

                # DAILY RESET: Runs at midnight to reset repeating alarms
                if now.hour == 0 and now.minute == 0 and now.second < 15:
                    db.query(Alarm).filter(Alarm.repeat_days != None).update({"is_fired": False})
                    db.commit()

            except Exception as e:
                db.rollback()
                print(f"❌ Worker Error: {e}")
        
        time.sleep(10)