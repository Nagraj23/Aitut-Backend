import time
import datetime
from db.session import SessionLocal
from db.models import Alarm

def monitor_alarms():
    print("🚀 Background Alarm Monitor: Active")
    while True:
        # Create a fresh session for this check
        with SessionLocal() as db:
            try:
                now = datetime.datetime.now(datetime.timezone.utc)
                
                # Find active alarms that are due or overdue
                due_alarms = db.query(Alarm).filter(
                    Alarm.trigger_time <= now,
                    Alarm.is_active == True
                ).all()

                for alarm in due_alarms:
                    print(f"⏰ TRIGGERING: {alarm.title} at {now}")
                    
                    # 1. Mark as inactive so it doesn't repeat
                    alarm.is_active = False
                    db.commit()
                    
                    # 2. Logic to notify the student (e.g., Push Notification)
                    send_push_notification(alarm.title)

            except Exception as e:
                print(f"❌ Worker Error: {e}")
        
        # Wait 10 seconds. Adjust this for more/less precision.
        time.sleep(10)

def send_push_notification(title):
    # Place your FCM (Firebase) or OneSignal code here
    print(f"Sending Notification: 'Time to study {title}!'")