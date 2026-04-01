from google import genai
from core.config import get_settings

settings = get_settings()
client = genai.Client(api_key=settings.GEMINI_API_KEY)

for model in client.models.list():
    print(model.name)