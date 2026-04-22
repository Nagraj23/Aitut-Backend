import jwt
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings

class SpringUser:
    def __init__(self, payload):
        # Matches .claim("userId", userId) in your Spring code
        self.id = payload.get("userId")  
        self.email = payload.get("sub") 
        self.username = payload.get("sub")

    @property
    def is_authenticated(self):
        return True

class SpringBootTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ")[1]
        raw_secret = settings.SPRING_JWT_SECRET
        
        if not raw_secret:
            raise AuthenticationFailed("Server Error: SPRING_JWT_SECRET not configured.")

        try:
            # Your Spring code uses SECRET.getBytes(), which is a UTF-8 encoded string
            payload = jwt.decode(token, raw_secret.encode('utf-8'), algorithms=["HS256"])
            return (SpringUser(payload), None)
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token has expired.")
        except jwt.InvalidSignatureError:
            raise AuthenticationFailed("Signature mismatch. Check your secret keys.")
        except Exception as e:
            raise AuthenticationFailed(f"Authentication failed: {str(e)}")