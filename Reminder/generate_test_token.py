import jwt
import os
import datetime
from dotenv import load_dotenv

load_dotenv()
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your_fallback_shared_secret_here")

# Simulate a standard payload issued by your Spring Boot container
payload = {
    "sub": "550e8400-e29b-41d4-a716-446655440000", # Mock User UUID
    "role": "STUDENT",
    "exp": datetime.datetime.utcnow() + datetime.timedelta(days=1)
}

token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
print(f"\n🔑 YOUR TEST JWT TOKEN:\nBearer {token}\n")