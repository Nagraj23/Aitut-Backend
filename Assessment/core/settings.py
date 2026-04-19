import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
# settings.py
ALLOWED_HOSTS = ['10.139.12.44', '10.108.86.191', 'localhost', '127.0.0.1', '*']

CORS_ALLOW_ALL_ORIGINS = True

# Application Definition
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'rest_framework',
    'corsheaders','db.apps.DbConfig',
   # Your models folder [cite: 1, 11]
    'api', # Your views folder [cite: 6, 23]
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Keep this at the top
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware', # Added
    'django.middleware.csrf.CsrfViewMiddleware',           # Added
    'django.contrib.auth.middleware.AuthenticationMiddleware', # Added
    'django.contrib.messages.middleware.MessageMiddleware', # Added
]

# Auth Bridge: Using the shared secret from Spring Boot 
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'core.authentication.SpringBootTokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
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