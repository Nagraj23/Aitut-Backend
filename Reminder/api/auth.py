import jwt
import os
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()
raw_secret = os.getenv("JWT_SECRET_KEY")

if raw_secret is None:
    raise RuntimeError("❌ JWT_SECRET_KEY is missing from .env file!")

SECRET_KEY: str = raw_secret

# Made this async so it can be called seamlessly by our streaming routes
async def verify_token(auth: HTTPAuthorizationCredentials = Security(security)):
    try:
        # Decodes the token issued by Spring
        payload = jwt.decode(auth.credentials, SECRET_KEY, algorithms=["HS256"])
        
        # Spring tokens store the user ID in 'sub' or 'user_id'
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID missing in token")
            
        return {"user_id": str(user_id)}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")