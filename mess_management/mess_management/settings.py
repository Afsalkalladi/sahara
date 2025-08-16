import os
from pathlib import Path
from dotenv import load_dotenv
import json

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost').split(',')

INSTALLED_APPS = [
	'django.contrib.admin',
	'django.contrib.auth',
	'django.contrib.contenttypes',
	'django.contrib.sessions',
	'django.contrib.messages',
	'django.contrib.staticfiles',
	'rest_framework',
	'corsheaders',
	'django_extensions',
	'apps.core',
	'apps.api',
	'apps.telegram_bot',
	'apps.scanner',
	'apps.utils',
]

MIDDLEWARE = [
	'corsheaders.middleware.CorsMiddleware',
	'django.middleware.security.SecurityMiddleware',
	'whitenoise.middleware.WhiteNoiseMiddleware',
	'django.contrib.sessions.middleware.SessionMiddleware',
	'django.middleware.common.CommonMiddleware',
	'django.middleware.csrf.CsrfViewMiddleware',
	'django.contrib.auth.middleware.AuthenticationMiddleware',
	'django.contrib.messages.middleware.MessageMiddleware',
	'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'mess_management.urls'

TEMPLATES = [
	{
		'BACKEND': 'django.template.backends.django.DjangoTemplates',
		'DIRS': [BASE_DIR / 'templates'],
		'APP_DIRS': True,
		'OPTIONS': {
			'context_processors': [
				'django.template.context_processors.debug',
				'django.template.context_processors.request',
				'django.contrib.auth.context_processors.auth',
				'django.contrib.messages.context_processors.messages',
			],
		},
	},
]

WSGI_APPLICATION = 'mess_management.wsgi.application'

# Database
import dj_database_url
DATABASES = {
	'default': dj_database_url.parse(
		os.getenv('DATABASE_URL', 'postgresql://mess_user:mess_password@localhost:5432/mess_db')
	)
}

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.getenv('TIMEZONE', 'Asia/Kolkata')
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
	'DEFAULT_AUTHENTICATION_CLASSES': [
		'apps.api.permissions.StaffTokenAuthentication',
		'rest_framework.authentication.SessionAuthentication',
	],
	'DEFAULT_PERMISSION_CLASSES': [
		'rest_framework.permissions.IsAuthenticated',
	],
	'DEFAULT_RENDERER_CLASSES': [
		'rest_framework.renderers.JSONRenderer',
	],
	'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
	'PAGE_SIZE': 50,
}

# Celery Configuration
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Telegram Bot Settings
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_WEBHOOK_URL = os.getenv('TELEGRAM_WEBHOOK_URL')
ADMIN_TG_IDS = [int(x.strip()) for x in os.getenv('ADMIN_TG_IDS', '').split(',') if x.strip()]

# QR Code Settings
QR_SECRET = os.getenv('QR_SECRET')

# Cloudinary Settings
import cloudinary
cloudinary.config(
	secure=True
)

# Google Sheets Settings
GOOGLE_SHEETS_CREDENTIALS = json.loads(os.getenv('GOOGLE_SHEETS_CREDENTIALS_JSON', '{}'))
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')

# Custom Settings
MESS_CONFIG = {
	'cutoff_time': '23:00',
	'payment_cycle_duration_days': 30,
	'max_advance_cut_days': 7,
	'qr_expiry_buffer_hours': 1,
	'notification_retry_attempts': 3,
	'meal_windows': {
		'BREAKFAST': {'start': '07:00', 'end': '09:30'},
		'LUNCH': {'start': '12:00', 'end': '14:30'},
		'DINNER': {'start': '19:00', 'end': '21:30'},
	}
}

STAFF_TOKEN_EXPIRY_DAYS = int(os.getenv('STAFF_TOKEN_EXPIRY_DAYS', '30'))

# CORS Settings
CORS_ALLOWED_ORIGINS = [
	"http://localhost:3000",
	"http://127.0.0.1:3000",
]

# Security Settings
if not DEBUG:
	SECURE_SSL_REDIRECT = True
	SESSION_COOKIE_SECURE = True
	CSRF_COOKIE_SECURE = True
	SECURE_BROWSER_XSS_FILTER = True
	SECURE_CONTENT_TYPE_NOSNIFF = True
