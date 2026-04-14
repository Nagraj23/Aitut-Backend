import jwt
import logging
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings

class SpringUser:
    def __init__(self, payload):
        # CHANGE: payload.get("userId") will be None with your current Spring code.
        # Use "sub" because that's where Spring stores the username.
        self.id = payload.get("sub")  
        self.email = payload.get("sub") 
        self.role = payload.get("role", "user") # Default if not in JWT

    @property
    def is_authenticated(self):
        return True

logger = logging.getLogger(__name__)

class SpringBootTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ")[1]
        raw_secret = settings.SPRING_JWT_SECRET
        payload = None

        # --- FALLBACK LOGIC START ---
        # --- FIXED LOGIC ---
        try:
            # Most Spring Boot JWT implementations use the secret as a UTF-8 byte array
            payload = jwt.decode(token, raw_secret.encode('utf-8'), algorithms=["HS256"])
            print("--- DEBUG: Authenticated Successfully ---")
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token has expired.")
        except jwt.InvalidSignatureError:
            # If the first one fails, try as Hex (common for auto-generated keys)
            try:
                secret_as_hex = bytes.fromhex(raw_secret)
                payload = jwt.decode(token, secret_as_hex, algorithms=["HS256"])
            except:
                raise AuthenticationFailed("Invalid signature: Secret mismatch between Spring and Django.")
        except Exception as e:
            raise AuthenticationFailed(f"Auth error: {str(e)}")

        if payload:
            return (SpringUser(payload), None)
        return None
        
        # # Method 1: Try decoding as standard UTF-8 string (Matches SECRET.getBytes())
        # try:
        #     payload = jwt.decode(token, raw_secret.encode('utf-8'), algorithms=["HS256"])
        #     print("--- DEBUG: Authenticated via UTF-8 String Secret ---")
        # except jwt.InvalidSignatureError:
        #     # Method 2: Try decoding as Hex bytes (Common if the secret is a hash string)
        #     try:
        #         secret_as_hex = bytes.fromhex(raw_secret)
        #         payload = jwt.decode(token, secret_as_hex, algorithms=["HS256"])
        #         print("--- DEBUG: Authenticated via Hexadecimal Secret ---")
        #     except Exception as e:
        #         print(f"--- DEBUG: Both secret methods failed. Last error: {str(e)} ---")
        #         raise AuthenticationFailed("Invalid signature: Secret mismatch.")
        # except jwt.DecodeError:
        #     raise AuthenticationFailed("Malformed token structure.")
        # except jwt.ExpiredSignatureError:
        #     raise AuthenticationFailed("Token has expired.")
        # except Exception as e:
        #     raise AuthenticationFailed(f"Auth error: {str(e)}")

        # # --- FALLBACK LOGIC END ---

        # if payload:
        #  return (SpringUser(payload), None)
        