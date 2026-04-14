import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = ['*']

# Application Definition
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'rest_framework',
    'corsheaders','db.apps.DbConfig',
   # Your models folder [cite: 1, 11]
    'api', # Your views folder [cite: 6, 23]
]
# 1. Ensure Middleware order is correct (CorsMiddleware MUST be at the top)
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware', # MUST be first
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

# 2. Add these specific CORS settings
CORS_ALLOW_ALL_ORIGINS = True 
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]
CORS_ALLOW_HEADERS = ["*"]

# 3. CSRF Trust (Required for POST requests from mobile)
CSRF_TRUSTED_ORIGINS = [
    'http://10.205.155.26',
    'http://localhost:8000',
    'http://127.0.0.1:8000'
]

# Auth Bridge: Using the shared secret from Spring Boot 
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'core.authentication.SpringBootTokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

SPRING_JWT_SECRET = os.getenv("SPRING_JWT_SECRET") # Must match Spring Boot secret [cite: 10]
GROQ_API_KEY = os.getenv("GROQ_API_KEY") # 👈 Add this

CHROMA_DB_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', 'TEACH', 'chroma_data'))

print(f"📡 System Linking: ChromaDB path set to {CHROMA_DB_PATH}")
# Optional: Define your preferred Groq model here for easy global changes
GROQ_DEFAULT_MODEL = "llama-3.1-8b-instant"
CHAT_MODEL = GROQ_DEFAULT_MODEL

ROOT_URLCONF = 'core.urls'
WSGI_APPLICATION = 'core.wsgi.application'
# Add these at the very bottom
# CORS_ALLOW_ALL_ORIGINS = True  # Allows your mobile app to connect
# CSRF_TRUSTED_ORIGINS = ['http://10.205.155.26'] # Trust your own network IP
# Database (PostgreSQL) [cite: 4]
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}