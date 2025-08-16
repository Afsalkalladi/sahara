# Mess Management System

A comprehensive Django-based mess management system with Telegram bot integration and QR code scanning for meal access control.

## 🏗️ Architecture Overview

- **Backend**: Django + Django REST Framework
- **Database**: PostgreSQL with Redis for caching/queues
- **Bot Interface**: Python-Telegram-Bot for student interactions
- **Staff Interface**: Mobile-friendly web QR scanner
- **Admin Interface**: Telegram inline keyboards + Django admin
- **Background Jobs**: Celery for async tasks
- **File Storage**: Cloudinary for payment screenshots
- **Backup**: Google Sheets integration for audit trails

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- PostgreSQL 15+ (if running locally)
- Redis (if running locally)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd mess_management
cp .env.example .env
```

### 2. Configure Environment Variables

Edit `.env` file with your credentials:

```env
# Django
DJANGO_SECRET_KEY=your-super-secret-key-here-change-this
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# Database
DATABASE_URL=postgresql://mess_user:mess_password@db:5432/mess_db

# Redis
REDIS_URL=redis://redis:6379/0

# Telegram Bot (Get from @BotFather)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxyz
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/telegram/webhook
ADMIN_TG_IDS=123456789,987654321

# QR Security
QR_SECRET=your-qr-signing-secret-change-this

# Cloudinary (Get from cloudinary.com)
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name

# Google Sheets (Create service account)
GOOGLE_SHEETS_CREDENTIALS_JSON={"type": "service_account", "project_id": "..."}
GOOGLE_SHEETS_SPREADSHEET_ID=your-spreadsheet-id

# Settings
TIMEZONE=Asia/Kolkata
STAFF_TOKEN_EXPIRY_DAYS=30
```

### 3. Run with Docker (Recommended)

```bash
# Build and start all services
docker-compose up --build

# Run migrations (in another terminal)
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Create staff token for scanner
docker-compose exec web python manage.py shell
```

In the Django shell:
```python
from apps.core.models import StaffToken
staff_token, token = StaffToken.create_token("Main Scanner", expires_days=30)
print(f"Staff Token: {token}")
print(f"Scanner URL: http://localhost:8000/scanner/{token}/")
```

### 4. Alternative: Local Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup database
createdb mess_db
python manage.py migrate

# Run Redis (separate terminal)
redis-server

# Run Celery worker (separate terminal)
celery -A mess_management worker --loglevel=info

# Run Celery beat (separate terminal)
celery -A mess_management beat --loglevel=info

# Run Django dev server
python manage.py runserver
```

## 🤖 Telegram Bot Setup

### 1. Create Bot

1. Message @BotFather on Telegram
2. Send `/newbot`
3. Choose name and username
4. Copy the token to `TELEGRAM_BOT_TOKEN` in `.env`

### 2. Get Admin User IDs

1. Message your bot
2. Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Find your user ID in the response
4. Add it to `ADMIN_TG_IDS` in `.env`

### 3. Set Webhook (Production)

```bash
curl -X POST \
  https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://yourdomain.com/telegram/webhook",
    "allowed_updates": ["message", "callback_query"]
  }'
```

## 📱 Staff Scanner Setup

### 1. Create Staff Token

```python
# In Django shell
from apps.core.models import StaffToken
staff_token, token = StaffToken.create_token("Mess Counter 1", expires_days=30)
print(f"Scanner URL: https://yourdomain.com/scanner/{token}/")
```

### 2. Access Scanner

- Open the URL on any mobile device
- Allow camera permissions
- Select meal type and scan QR codes

## 🔧 Admin Operations

### 1. Via Telegram Bot

Admin users can access these functions through `/admin` command:

- ✅ Approve/deny student registrations
- 💳 Verify/deny payment screenshots
- 📊 View reports and statistics
- 🔒 Set mess closures
- 🔄 Regenerate all QR codes

### 2. Via Django Admin

Access `http://localhost:8000/admin/` for full system management:

- User management
- Bulk operations
- System settings
- Audit logs

## 📊 Google Sheets Backup Setup

### 1. Create Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google Sheets API
4. Create service account with Editor role
5. Download JSON credentials

### 2. Setup Spreadsheet

1. Create a new Google Sheets document
2. Share it with service account email (found in JSON)
3. Create tabs: `registrations`, `payments`, `mess_cuts`, `mess_closures`, `scan_events`, `audit`
4. Copy spreadsheet ID from URL to `GOOGLE_SHEETS_SPREADSHEET_ID`

## 🔐 Security Features

### QR Code Security
- HMAC-SHA256 signed payloads
- Version-based rotation invalidates old codes
- No PII in QR payload (only student ID + signature)

### Authentication
- Staff tokens with expiry and revocation
- Admin access via Telegram user ID whitelist
- CSRF protection for web interfaces

### Data Protection
- All sensitive operations logged to audit trail
- Payment screenshots stored securely in Cloudinary
- Database queries use parameterized statements

## 📱 User Workflows

### Student Registration Flow
1. `/start` → Click "Register"
2. Provide details: `Name|Roll|Room|Phone`
3. Wait for admin approval
4. Receive QR code upon approval

### Payment Upload Flow
1. `/start` → Click "Upload Payment"
2. Provide: `Amount|Start Date|End Date`
3. Upload payment screenshot
4. Wait for admin verification

### Mess Cut Flow
1. `/start` → Click "Take Mess Cut"
2. Provide date range (respects 11 PM cutoff)
3. Confirm dates
4. Receive confirmation

### Meal Access Flow
1. Show QR code to staff scanner
2. Staff selects meal type and scans
3. System checks: payment, cuts, closures
4. Access granted/denied with reason
5. Student receives notification

## 🛠️ Management Commands

### Create Staff Tokens
```bash
python manage.py shell
```
```python
from apps.core.models import StaffToken
token_obj, token = StaffToken.create_token("Counter 1", expires_days=30)
print(f"Token: {token}")
```

### Regenerate All QR Codes
```python
from apps.core.models import Student, Settings
from apps.utils.qr_utils import generate_qr_payload
import secrets

# Increment QR version
settings = Settings.get_settings()
settings.qr_secret_version += 1
settings.save()

# Update all student nonces
students = Student.objects.filter(status='APPROVED')
for student in students:
    student.qr_nonce = secrets.token_hex(16)
    student.qr_version = settings.qr_secret_version
    student.save()

print(f"Regenerated QR codes for {students.count()} students")
```

### Set Mess Closure
```python
from apps.core.models import MessClosure
from django.contrib.auth.models import User
from apps.utils.notifications import send_mess_closure_broadcast
from datetime import date

admin_user = User.objects.get(username='admin')
closure = MessClosure.objects.create(
    from_date=date(2024, 12, 25),
    to_date=date(2024, 12, 26),
    reason="Christmas Holiday",
    created_by_admin=admin_user
)

# Broadcast to all students
send_mess_closure_broadcast.delay(closure.id)
```

## 📈 Monitoring & Maintenance

### Health Checks
```bash
# Check database connectivity
docker-compose exec web python manage.py check --database

# Check Celery workers
docker-compose exec worker celery -A mess_management inspect active

# Check Redis connectivity
docker-compose exec redis redis-cli ping
```

### Log Monitoring
```bash
# View application logs
docker-compose logs -f web

# View worker logs
docker-compose logs -f worker

# View specific service logs
docker-compose logs -f scheduler
```

### Backup Verification
```bash
# Check DLQ for failed backups
python manage.py shell
```
```python
from apps.core.models import DLQLog
failed_backups = DLQLog.objects.filter(processed_at__isnull=True)
print(f"Failed backups: {failed_backups.count()}")

# Retry failed backups
from apps.utils.backup_utils import process_dlq_backups
process_dlq_backups.delay()
```

## 🔄 Deployment

### Production Environment Variables
```env
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DJANGO_SECRET_KEY=your-production-secret-key
DATABASE_URL=postgresql://user:pass@prod-db:5432/mess_db
REDIS_URL=redis://prod-redis:6379/0
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/telegram/webhook
```

### Nginx Configuration
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;
    
    ssl_certificate /etc/ssl/certs/your-cert.pem;
    ssl_certificate_key /etc/ssl/private/your-key.pem;
    
    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /static/ {
        alias /app/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias /app/media/;
        expires 1y;
        add_header Cache-Control "public";
    }
}
```

### Database Backup Script
```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
DB_NAME="mess_db"
DB_USER="mess_user"

# Create backup
pg_dump -h localhost -U $DB_USER -d $DB_NAME > $BACKUP_DIR/mess_db_$DATE.sql

# Keep only last 7 days of backups
find $BACKUP_DIR -name "mess_db_*.sql" -mtime +7 -delete

echo "Backup completed: mess_db_$DATE.sql"
```

### Cron Jobs for Production
```bash
# Add to crontab
0 2 * * * /path/to/backup.sh
0 3 * * * docker-compose exec web python manage.py process_dlq_backups
*/15 * * * * docker-compose exec web python manage.py health_check
```

## 🧪 Testing

### Run Tests
```bash
# All tests
python manage.py test

# Specific app tests
python manage.py test apps.core
python manage.py test apps.api

# With coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
coverage html
```

### Test Scenarios

#### 1. Registration Flow Test
```python
# Test student registration
def test_student_registration():
    # Create student via Telegram
    # Check pending status
    # Admin approve
    # Verify QR generation
```

#### 2. Payment Verification Test
```python
# Test payment upload and verification
def test_payment_flow():
    # Upload screenshot
    # Admin verify
    # Check access granted
```

#### 3. QR Scanning Test
```python
# Test QR code scanning
def test_qr_scanning():
    # Generate valid QR
    # Scan with valid payment
    # Check access granted
    # Test duplicate scan blocking
```

## 🐛 Troubleshooting

### Common Issues

#### Bot Not Responding
```bash
# Check webhook status
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# Reset webhook
curl -X POST https://api.telegram.org/bot<TOKEN>/deleteWebhook
curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook \
  -d "url=https://yourdomain.com/telegram/webhook"
```

#### Scanner Not Working
- Check camera permissions
- Verify staff token validity
- Check network connectivity
- Clear browser cache

#### Database Issues
```bash
# Check connections
docker-compose exec db psql -U mess_user -d mess_db -c "\conninfo"

# Reset migrations (⚠️ DATA LOSS)
python manage.py migrate --fake-initial
python manage.py migrate
```

#### Celery Worker Issues
```bash
# Restart workers
docker-compose restart worker scheduler

# Check queue status
docker-compose exec worker celery -A mess_management inspect stats
```

### Debug Mode Commands
```python
# Check student status
from apps.core.models import Student
student = Student.objects.get(roll_no='CS21B001')
print(f"Status: {student.status}")

# Check payment validity
from apps.core.models import Payment
payments = Payment.objects.filter(student=student, status='VERIFIED')
print(f"Valid payments: {payments.count()}")

# Test QR generation
from apps.utils.qr_utils import generate_qr_payload, verify_qr_payload
payload = generate_qr_payload(student.id, student.qr_nonce)
student_id, error = verify_qr_payload(payload)
print(f"QR Valid: {student_id is not None}")
```

## 📊 Analytics & Reports

### Built-in Reports
- Payment status dashboard
- Upcoming mess cuts
- Meal access statistics
- Failed notification logs

### Custom Queries
```python
# Monthly meal consumption
from django.db.models import Count
from apps.core.models import ScanEvent

monthly_stats = ScanEvent.objects.filter(
    result='ALLOWED',
    scanned_at__month=12
).values('meal').annotate(count=Count('id'))

# Payment collection rate
from apps.core.models import Student, Payment
total_students = Student.objects.filter(status='APPROVED').count()
paid_students = Payment.objects.filter(
    status='VERIFIED',
    cycle_start__lte=today,
    cycle_end__gte=today
).values('student').distinct().count()

collection_rate = (paid_students / total_students) * 100
```

## 🚀 Performance Optimization

### Database Indexing
```sql
-- Add these indexes for better performance
CREATE INDEX idx_payments_student_cycle ON payments(student_id, cycle_start, status);
CREATE INDEX idx_mess_cuts_date_range ON mess_cuts(from_date, to_date, student_id);
CREATE INDEX idx_scan_events_date_meal ON scan_events(DATE(scanned_at), meal, student_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
```

### Redis Caching
```python
# Add to settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Cache frequently accessed data
from django.core.cache import cache

def get_student_payment_status(student_id):
    cache_key = f'student_payment_{student_id}'
    result = cache.get(cache_key)
    if result is None:
        # Calculate payment status
        result = calculate_payment_status(student_id)
        cache.set(cache_key, result, 300)  # Cache for 5 minutes
    return result
```

## 📝 API Documentation

### Authentication
All API requests require authentication:
```bash
# Staff endpoints
curl -H "Authorization: Bearer <staff-token>" \
  https://yourdomain.com/api/v1/scanner/scan

# Admin endpoints require session auth or admin tokens
```

### Key Endpoints

#### Scanner API
```bash
# Scan QR Code
POST /api/v1/scanner/scan
{
  "qr_data": "1|123|1640995200|abc123|signature",
  "meal": "LUNCH",
  "device_info": "Mobile Scanner 1"
}

# Response
{
  "result": "ALLOWED",
  "student_snapshot": {
    "name": "John Doe",
    "roll_no": "CS21B001",
    "room_no": "A-101",
    "payment_ok": true,
    "today_cut": false
  }
}
```

#### Admin API
```bash
# Approve Registration
POST /api/v1/admin/registrations/123/approve

# Verify Payment
POST /api/v1/admin/payments/456/verify

# Get Reports
GET /api/v1/admin/reports/payments?status=UPLOADED
```

## 🔮 Future Enhancements

### Phase 2 Features
- Payment gateway integration (Razorpay/PayU)
- Mobile app for students
- Meal pre-booking system
- Diet preference management
- Multi-mess/hostel support

### Phase 3 Features
- Machine learning for fraud detection
- Advanced analytics dashboard
- Integration with hostel management
- Automated reconciliation
- Voice commands for accessibility

## 📞 Support

### Getting Help
1. Check this documentation first
2. Search existing issues in repository
3. Create detailed issue with:
   - Environment details
   - Steps to reproduce
   - Expected vs actual behavior
   - Relevant logs

### Contributing
1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Ready to manage your mess efficiently! 🍽️**

For any issues or questions, please check the troubleshooting section or create an issue in the repository.# Mess Management System - Complete Django Project

## Project Structure
```
mess_management/
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── manage.py
├── .env.example
├── README.md
├── mess_management/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── celery.py
├── apps/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   └── migrations/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── views.py
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   └── permissions.py
│   ├── telegram_bot/
│   │   ├── __init__.py
│   │   ├── bot.py
│   │   ├── handlers.py
│   │   ├── keyboards.py
│   │   └── utils.py
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── templates/
│   └── utils/
│       ├── __init__.py
│       ├── qr_utils.py
│       ├── notifications.py
│       ├── backup_utils.py
│       └── decorators.py
├── static/
├── templates/
└── media/
```

## 1. requirements.txt
```txt
Django==4.2.7
djangorestframework==3.14.0
django-cors-headers==4.3.1
psycopg2-binary==2.9.9
celery==5.3.4
redis==5.0.1
python-telegram-bot==20.7
qrcode==7.4.2
Pillow==10.1.0
cloudinary==1.36.0
google-api-python-client==2.108.0
google-auth==2.23.4
google-auth-oauthlib==1.1.0
google-auth-httplib2==0.1.1
python-dotenv==1.0.0
cryptography==41.0.7
pytz==2023.3
gunicorn==21.2.0
whitenoise==6.6.0
django-extensions==3.2.3
```

## 2. .env.example
```env
# Django Settings
DJANGO_SECRET_KEY=your-super-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# Database
DATABASE_URL=postgresql://mess_user:mess_password@localhost:5432/mess_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Telegram Bot
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/telegram/webhook
ADMIN_TG_IDS=123456789,987654321

# QR Code Security
QR_SECRET=your-qr-signing-secret

# Cloudinary
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS_JSON={"type": "service_account", ...}
GOOGLE_SHEETS_SPREADSHEET_ID=your-spreadsheet-id

# Timezone
TIMEZONE=Asia/Kolkata

# Staff Scanner
STAFF_TOKEN_EXPIRY_DAYS=30
```

## 3. mess_management/settings.py
```python
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
```

## 4. apps/core/models.py
```python
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import RegexValidator
import hashlib
import secrets

class Student(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('DENIED', 'Denied'),
    ]
    
    tg_user_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=100)
    roll_no = models.CharField(max_length=20, unique=True)
    room_no = models.CharField(max_length=10)
    phone = models.CharField(
        max_length=15,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$')]
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    qr_version = models.IntegerField(default=1)
    qr_nonce = models.CharField(max_length=32, default=lambda: secrets.token_hex(16))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.roll_no})"

    class Meta:
        db_table = 'students'


class Payment(models.Model):
    STATUS_CHOICES = [
        ('NONE', 'None'),
        ('UPLOADED', 'Uploaded'),
        ('VERIFIED', 'Verified'),
        ('DENIED', 'Denied'),
    ]
    
    SOURCE_CHOICES = [
        ('ONLINE_SCREENSHOT', 'Online Screenshot'),
        ('OFFLINE_MANUAL', 'Offline Manual'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments')
    cycle_start = models.DateField()
    cycle_end = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    screenshot_url = models.URLField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='NONE')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='ONLINE_SCREENSHOT')
    reviewer_admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student.name} - {self.cycle_start} to {self.cycle_end}"

    class Meta:
        db_table = 'payments'
        unique_together = ['student', 'cycle_start']


class MessCut(models.Model):
    APPLIED_BY_CHOICES = [
        ('STUDENT', 'Student'),
        ('ADMIN_SYSTEM', 'Admin System'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='mess_cuts')
    from_date = models.DateField()
    to_date = models.DateField()
    applied_at = models.DateTimeField(auto_now_add=True)
    applied_by = models.CharField(max_length=15, choices=APPLIED_BY_CHOICES, default='STUDENT')
    cutoff_ok = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.student.name} - {self.from_date} to {self.to_date}"

    class Meta:
        db_table = 'mess_cuts'


class MessClosure(models.Model):
    from_date = models.DateField()
    to_date = models.DateField()
    reason = models.TextField(blank=True)
    created_by_admin = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Closure: {self.from_date} to {self.to_date}"

    class Meta:
        db_table = 'mess_closures'


class ScanEvent(models.Model):
    MEAL_CHOICES = [
        ('BREAKFAST', 'Breakfast'),
        ('LUNCH', 'Lunch'),
        ('DINNER', 'Dinner'),
    ]
    
    RESULT_CHOICES = [
        ('ALLOWED', 'Allowed'),
        ('BLOCKED_NO_PAYMENT', 'Blocked - No Payment'),
        ('BLOCKED_CUT', 'Blocked - Mess Cut'),
        ('BLOCKED_STATUS', 'Blocked - Status Issue'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='scan_events')
    meal = models.CharField(max_length=10, choices=MEAL_CHOICES)
    scanned_at = models.DateTimeField(auto_now_add=True)
    staff_token = models.ForeignKey('StaffToken', on_delete=models.SET_NULL, null=True, blank=True)
    result = models.CharField(max_length=25, choices=RESULT_CHOICES)
    device_info = models.TextField(blank=True)

    def __str__(self):
        return f"{self.student.name} - {self.meal} - {self.result}"

    class Meta:
        db_table = 'scan_events'


class StaffToken(models.Model):
    label = models.CharField(max_length=100)
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    token_hash = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return f"{self.label} - {'Active' if self.active else 'Inactive'}"

    @classmethod
    def create_token(cls, label, expires_days=30):
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        expires_at = None
        if expires_days:
            expires_at = timezone.now() + timezone.timedelta(days=expires_days)
        
        staff_token = cls.objects.create(
            label=label,
            expires_at=expires_at,
            token_hash=token_hash
        )
        
        return staff_token, token

    class Meta:
        db_table = 'staff_tokens'


class AuditLog(models.Model):
    ACTOR_TYPE_CHOICES = [
        ('STUDENT', 'Student'),
        ('ADMIN', 'Admin'),
        ('STAFF', 'Staff'),
        ('SYSTEM', 'System'),
    ]
    
    actor_type = models.CharField(max_length=10, choices=ACTOR_TYPE_CHOICES)
    actor_id = models.CharField(max_length=50, null=True, blank=True)
    event_type = models.CharField(max_length=50)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.actor_type} - {self.event_type} - {self.created_at}"

    class Meta:
        db_table = 'audit_logs'


class Settings(models.Model):
    # Singleton pattern for global settings
    id = models.BooleanField(default=True, primary_key=True)
    timezone = models.CharField(max_length=50, default='Asia/Kolkata')
    cutoff_time = models.TimeField(default='23:00')
    qr_secret_version = models.IntegerField(default=1)
    qr_secret_hash = models.CharField(max_length=64)
    meals = models.JSONField(default=dict)
    
    def save(self, *args, **kwargs):
        self.id = True
        return super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        obj, created = cls.objects.get_or_create(id=True)
        return obj

    class Meta:
        db_table = 'settings'


class DLQLog(models.Model):
    """Dead Letter Queue for failed Google Sheets operations"""
    operation_type = models.CharField(max_length=50)
    payload = models.JSONField()
    error_message = models.TextField()
    retry_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'dlq_logs'
```

## 5. apps/utils/qr_utils.py
```python
import hmac
import hashlib
import time
import qrcode
from io import BytesIO
import base64
from django.conf import settings
from apps.core.models import Settings

def generate_qr_payload(student_id, nonce):
    """Generate HMAC-signed QR payload"""
    app_settings = Settings.get_settings()
    version = app_settings.qr_secret_version
    issued_at = int(time.time())
    
    # Create payload without HMAC first
    payload_data = f"{version}|{student_id}|{issued_at}|{nonce}"
    
    # Generate HMAC
    secret = settings.QR_SECRET.encode()
    signature = hmac.new(secret, payload_data.encode(), hashlib.sha256).hexdigest()
    
    # Final payload
    payload = f"{payload_data}|{signature}"
    return payload

def verify_qr_payload(payload):
    """Verify QR payload HMAC and return student_id if valid"""
    try:
        parts = payload.split('|')
        if len(parts) != 5:
            return None, "Invalid payload format"
        
        version, student_id, issued_at, nonce, signature = parts
        
        # Check version
        app_settings = Settings.get_settings()
        if int(version) != app_settings.qr_secret_version:
            return None, "QR code version mismatch"
        
        # Verify HMAC
        payload_data = f"{version}|{student_id}|{issued_at}|{nonce}"
        secret = settings.QR_SECRET.encode()
        expected_signature = hmac.new(secret, payload_data.encode(), hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return None, "Invalid signature"
        
        # Check if not too old (buffer for rotation)
        current_time = int(time.time())
        qr_age_hours = (current_time - int(issued_at)) / 3600
        if qr_age_hours > settings.MESS_CONFIG['qr_expiry_buffer_hours']:
            # Only check for very old QRs, allow some buffer
            pass
        
        return int(student_id), "Valid"
        
    except Exception as e:
        return None, f"Verification error: {str(e)}"

def generate_qr_image(payload):
    """Generate QR code image from payload"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 for easy transmission
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return img_base64
```

## 6. apps/telegram_bot/bot.py
```python
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)
from django.conf import settings
from .handlers import (
    start_handler, register_handler, payment_handler,
    mess_cut_handler, qr_handler, admin_handler
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup all bot handlers"""
        # Commands
        self.application.add_handler(CommandHandler("start", start_handler))
        self.application.add_handler(CommandHandler("admin", admin_handler))
        
        # Callback query handlers
        self.application.add_handler(CallbackQueryHandler(register_handler, pattern="^register"))
        self.application.add_handler(CallbackQueryHandler(payment_handler, pattern="^payment"))
        self.application.add_handler(CallbackQueryHandler(mess_cut_handler, pattern="^mess_cut"))
        self.application.add_handler(CallbackQueryHandler(qr_handler, pattern="^qr"))
        self.application.add_handler(CallbackQueryHandler(admin_handler, pattern="^admin"))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.PHOTO, payment_handler))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, register_handler))
    
    def get_application(self):
        return self.application

# Global bot instance
bot_instance = TelegramBot()
```

## 7. apps/telegram_bot/handlers.py
```python
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from django.conf import settings
from django.utils import timezone
from apps.core.models import Student, Payment, MessCut, MessClosure
from apps.utils.qr_utils import generate_qr_payload, generate_qr_image
from apps.utils.notifications import send_notification
import cloudinary.uploader

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    keyboard = [
        [InlineKeyboardButton("📝 Register", callback_data="register_start")],
        [InlineKeyboardButton("💳 Upload Payment", callback_data="payment_upload")],
        [InlineKeyboardButton("✂️ Take Mess Cut", callback_data="mess_cut_start")],
        [InlineKeyboardButton("📱 My QR Code", callback_data="qr_show")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "🍽️ *Welcome to Mess Management System*\n\n"
        "Hi! This bot helps you manage your mess registration, "
        "payments, mess cuts, and meal access. Use the buttons below to get started.\n\n"
        "⏰ *Important:* Mess cuts for tomorrow close at 11:00 PM."
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle registration flow"""
    query = update.callback_query
    
    if query and query.data == "register_start":
        await query.answer()
        
        # Check if already registered
        try:
            student = Student.objects.get(tg_user_id=update.effective_user.id)
            status_text = {
                'PENDING': '⏳ Your registration is pending admin approval.',
                'APPROVED': '✅ You are already registered and approved!',
                'DENIED': '❌ Your registration was denied. Contact admin for help.'
            }
            await query.edit_message_text(status_text[student.status])
            return
        except Student.DoesNotExist:
            pass
        
        await query.edit_message_text(
            "📝 *Registration Form*\n\n"
            "Please provide your details in this format:\n"
            "`Name|Roll Number|Room Number|Phone`\n\n"
            "Example: `John Doe|CS21B001|A-101|+919876543210`",
            parse_mode='Markdown'
        )
        context.user_data['registration_step'] = 'waiting_details'
        
    elif context.user_data.get('registration_step') == 'waiting_details' and update.message:
        # Process registration details
        try:
            details = update.message.text.split('|')
            if len(details) != 4:
                raise ValueError("Invalid format")
            
            name, roll_no, room_no, phone = [d.strip() for d in details]
            
            # Create student record
            student = Student.objects.create(
                tg_user_id=update.effective_user.id,
                name=name,
                roll_no=roll_no,
                room_no=room_no,
                phone=phone,
                status='PENDING'
            )
            
            await update.message.reply_text(
                "✅ Registration submitted successfully!\n"
                "Your application is pending admin approval. "
                "You'll be notified once approved."
            )
            
            # Notify admins
            await notify_admins_new_registration(student)
            
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid format. Please use:\n"
                "`Name|Roll Number|Room Number|Phone`",
                parse_mode='Markdown'
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ Registration failed: {str(e)}"
            )
        finally:
            context.user_data.pop('registration_step', None)

async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment upload flow"""
    query = update.callback_query
    
    if query and query.data == "payment_upload":
        await query.answer()
        
        # Check if student is approved
        try:
            student = Student.objects.get(
                tg_user_id=update.effective_user.id,
                status='APPROVED'
            )
        except Student.DoesNotExist:
            await query.edit_message_text(
                "❌ You must be registered and approved to upload payments."
            )
            return
        
        await query.edit_message_text(
            "💳 *Payment Upload*\n\n"
            "Please provide payment details in this format:\n"
            "`Amount|Start Date|End Date`\n\n"
            "Example: `3000|2024-01-01|2024-01-31`\n"
            "Then send the payment screenshot.",
            parse_mode='Markdown'
        )
        context.user_data['payment_step'] = 'waiting_details'
        
    elif context.user_data.get('payment_step') == 'waiting_details' and update.message and update.message.text:
        # Process payment details
        try:
            details = update.message.text.split('|')
            if len(details) != 3:
                raise ValueError("Invalid format")
            
            amount, start_date, end_date = [d.strip() for d in details]
            
            # Validate dates
            cycle_start = datetime.strptime(start_date, '%Y-%m-%d').date()
            cycle_end = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            context.user_data['payment_details'] = {
                'amount': float(amount),
                'cycle_start': cycle_start,
                'cycle_end': cycle_end
            }
            context.user_data['payment_step'] = 'waiting_screenshot'
            
            await update.message.reply_text(
                "📸 Great! Now please send the payment screenshot."
            )
            
        except ValueError as e:
            await update.message.reply_text(
                "❌ Invalid format. Please use:\n"
                "`Amount|Start Date|End Date`\n"
                "Date format: YYYY-MM-DD",
                parse_mode='Markdown'
            )
            
    elif context.user_data.get('payment_step') == 'waiting_screenshot' and update.message and update.message.photo:
        # Process screenshot upload
        try:
            student = Student.objects.get(tg_user_id=update.effective_user.id)
            payment_details = context.user_data['payment_details']
            
            # Download photo
            photo = update.message.photo[-1]  # Get highest resolution
            file = await context.bot.get_file(photo.file_id)
            
            # Upload to Cloudinary
            file_bytes = await file.download_as_bytearray()
            upload_result = cloudinary.uploader.upload(
                file_bytes,
                folder="mess_payments",
                resource_type="image"
            )
            
            # Create payment record
            payment = Payment.objects.create(
                student=student,
                cycle_start=payment_details['cycle_start'],
                cycle_end=payment_details['cycle_end'],
                amount=payment_details['amount'],
                screenshot_url=upload_result['secure_url'],
                status='UPLOADED'
            )
            
            await update.message.reply_text(
                "✅ Payment screenshot uploaded successfully!\n"
                "Your payment is pending admin verification. "
                "You'll be notified once verified."
            )
            
            # Notify admins
            await notify_admins_payment_upload(payment)
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Upload failed: {str(e)}"
            )
        finally:
            context.user_data.pop('payment_step', None)
            context.user_data.pop('payment_details', None)

async def mess_cut_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle mess cut flow"""
    query = update.callback_query
    
    if query and query.data == "mess_cut_start":
        await query.answer()
        
        # Check if student is approved
        try:
            student = Student.objects.get(
                tg_user_id=update.effective_user.id,
                status='APPROVED'
            )
        except Student.DoesNotExist:
            await query.edit_message_text(
                "❌ You must be registered and approved to take mess cuts."
            )
            return
        
        # Check cutoff time
        now = timezone.now()
        cutoff_time = timezone.datetime.combine(
            now.date(),
            timezone.datetime.strptime(settings.MESS_CONFIG['cutoff_time'], '%H:%M').time()
        )
        cutoff_time = timezone.make_aware(cutoff_time)
        
        if now > cutoff_time:
            min_date = (now + timedelta(days=2)).date()
        else:
            min_date = (now + timedelta(days=1)).date()
        
        await query.edit_message_text(
            f"✂️ *Mess Cut Request*\n\n"
            f"⏰ Cutoff time: {settings.MESS_CONFIG['cutoff_time']} daily\n"
            f"📅 Earliest available date: {min_date}\n\n"
            f"Please provide dates in format:\n"
            f"`From Date|To Date`\n\n"
            f"Example: `{min_date}|{min_date + timedelta(days=2)}`",
            parse_mode='Markdown'
        )
        context.user_data['mess_cut_step'] = 'waiting_dates'
        
    elif context.user_data.get('mess_cut_step') == 'waiting_dates' and update.message:
        try:
            student = Student.objects.get(tg_user_id=update.effective_user.id)
            dates = update.message.text.split('|')
            if len(dates) != 2:
                raise ValueError("Invalid format")
            
            from_date = datetime.strptime(dates[0].strip(), '%Y-%m-%d').date()
            to_date = datetime.strptime(dates[1].strip(), '%Y-%m-%d').date()
            
            # Validate dates
            now = timezone.now()
            cutoff_time = timezone.datetime.combine(
                now.date(),
                timezone.datetime.strptime(settings.MESS_CONFIG['cutoff_time'], '%H:%M').time()
            )
            cutoff_time = timezone.make_aware(cutoff_time)
            
            if now > cutoff_time:
                min_date = (now + timedelta(days=2)).date()
            else:
                min_date = (now + timedelta(days=1)).date()
            
            if from_date < min_date:
                raise ValueError(f"From date must be >= {min_date}")
            
            if to_date < from_date:
                raise ValueError("To date must be >= from date")
            
            # Create mess cut
            mess_cut = MessCut.objects.create(
                student=student,
                from_date=from_date,
                to_date=to_date,
                cutoff_ok=True
            )
            
            await update.message.reply_text(
                f"✅ Mess cut confirmed!\n"
                f"📅 From: {from_date}\n"
                f"📅 To: {to_date}\n\n"
                f"These days will be excluded from your meal access."
            )
            
        except ValueError as e:
            await update.message.reply_text(f"❌ {str(e)}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
        finally:
            context.user_data.pop('mess_cut_step', None)

async def qr_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle QR code display"""
    query = update.callback_query
    await query.answer()
    
    try:
        student = Student.objects.get(
            tg_user_id=update.effective_user.id,
            status='APPROVED'
        )
        
        # Generate QR payload and image
        payload = generate_qr_payload(student.id, student.qr_nonce)
        qr_image_base64 = generate_qr_image(payload)
        
        # Convert base64 to bytes for sending
        import base64
        from io import BytesIO
        qr_bytes = base64.b64decode(qr_image_base64)
        
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=BytesIO(qr_bytes),
            caption=(
                "📱 *Your Mess QR Code*\n\n"
                "This is your permanent QR code for meal access. "
                "Show this to the staff scanner when entering the mess.\n\n"
                "⚠️ *Note:* This QR will change only if admin regenerates all codes."
            ),
            parse_mode='Markdown'
        )
        
    except Student.DoesNotExist:
        await query.edit_message_text(
            "❌ You must be registered and approved to access your QR code."
        )

async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin commands and callbacks"""
    # Check if user is admin
    if update.effective_user.id not in settings.ADMIN_TG_IDS:
        await update.message.reply_text("❌ Access denied.")
        return
    
    query = update.callback_query
    
    if update.message and update.message.text == "/admin":
        # Show admin menu
        keyboard = [
            [InlineKeyboardButton("👥 Pending Registrations", callback_data="admin_registrations")],
            [InlineKeyboardButton("💳 Payment Reviews", callback_data="admin_payments")],
            [InlineKeyboardButton("📊 Reports", callback_data="admin_reports")],
            [InlineKeyboardButton("🔒 Mess Closure", callback_data="admin_closure")],
            [InlineKeyboardButton("🔄 Regenerate QR", callback_data="admin_qr_regen")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔧 *Admin Panel*\n\nSelect an option:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    elif query:
        await query.answer()
        
        if query.data == "admin_registrations":
            # Show pending registrations
            pending_students = Student.objects.filter(status='PENDING')
            
            if not pending_students.exists():
                await query.edit_message_text("✅ No pending registrations.")
                return
            
            text = "👥 *Pending Registrations:*\n\n"
            keyboard = []
            
            for student in pending_students:
                text += f"• {student.name} ({student.roll_no})\n"
                text += f"  Room: {student.room_no}, Phone: {student.phone}\n\n"
                
                keyboard.append([
                    InlineKeyboardButton(f"✅ Approve {student.roll_no}", 
                                       callback_data=f"admin_approve_{student.id}"),
                    InlineKeyboardButton(f"❌ Deny {student.roll_no}", 
                                       callback_data=f"admin_deny_{student.id}")
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
            
        elif query.data.startswith("admin_approve_"):
            student_id = int(query.data.split("_")[2])
            student = Student.objects.get(id=student_id)
            student.status = 'APPROVED'
            student.save()
            
            # Send QR to student
            payload = generate_qr_payload(student.id, student.qr_nonce)
            qr_image_base64 = generate_qr_image(payload)
            qr_bytes = base64.b64decode(qr_image_base64)
            
            await context.bot.send_message(
                chat_id=student.tg_user_id,
                text="✅ Your registration has been approved! Your mess access is now active."
            )
            
            await context.bot.send_photo(
                chat_id=student.tg_user_id,
                photo=BytesIO(qr_bytes),
                caption="📱 Here's your permanent QR code for meal access."
            )
            
            await query.edit_message_text(f"✅ Approved {student.name} ({student.roll_no})")
            
        elif query.data.startswith("admin_deny_"):
            student_id = int(query.data.split("_")[2])
            student = Student.objects.get(id=student_id)
            student.status = 'DENIED'
            student.save()
            
            await context.bot.send_message(
                chat_id=student.tg_user_id,
                text="❌ Your registration has been denied. Please contact the admin if you believe this is an error."
            )
            
            await query.edit_message_text(f"❌ Denied {student.name} ({student.roll_no})")

async def notify_admins_new_registration(student):
    """Notify admins about new registration"""
    text = (
        f"🔔 *New Registration*\n\n"
        f"Name: {student.name}\n"
        f"Roll: {student.roll_no}\n"
        f"Room: {student.room_no}\n"
        f"Phone: {student.phone}\n\n"
        f"Use /admin to review."
    )
    
    for admin_id in settings.ADMIN_TG_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode='Markdown'
            )
        except:
            pass

async def notify_admins_payment_upload(payment):
    """Notify admins about payment upload"""
    text = (
        f"💳 *Payment Uploaded*\n\n"
        f"Student: {payment.student.name} ({payment.student.roll_no})\n"
        f"Amount: ₹{payment.amount}\n"
        f"Cycle: {payment.cycle_start} to {payment.cycle_end}\n\n"
        f"Use /admin to review."
    )
    
    for admin_id in settings.ADMIN_TG_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode='Markdown'
            )
        except:
            pass
```

## 8. apps/api/views.py
```python
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.shortcuts import get_object_or_404
from datetime import datetime, timedelta

from apps.core.models import Student, Payment, MessCut, MessClosure, ScanEvent
from apps.utils.qr_utils import verify_qr_payload
from .serializers import StudentSnapshotSerializer, ScanEventSerializer
from .permissions import IsStaffUser

@api_view(['POST'])
@permission_classes([IsStaffUser])
def scanner_scan(request):
    """Handle QR code scanning"""
    qr_data = request.data.get('qr_data')
    meal = request.data.get('meal', '').upper()
    device_info = request.data.get('device_info', '')
    
    if not qr_data or meal not in ['BREAKFAST', 'LUNCH', 'DINNER']:
        return Response(
            {'error': 'Invalid request data'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify QR code
    student_id, error_msg = verify_qr_payload(qr_data)
    if not student_id:
        return Response({
            'result': 'BLOCKED_QR_INVALID',
            'reason': error_msg
        })
    
    # Get student
    try:
        student = Student.objects.get(id=student_id)
    except Student.DoesNotExist:
        return Response({
            'result': 'BLOCKED_STUDENT_NOT_FOUND',
            'reason': 'Student not found'
        })
    
    # Check student status
    if student.status != 'APPROVED':
        scan_event = ScanEvent.objects.create(
            student=student,
            meal=meal,
            result='BLOCKED_STATUS',
            device_info=device_info
        )
        return Response({
            'result': 'BLOCKED_STATUS',
            'reason': 'Student not approved',
            'student_snapshot': StudentSnapshotSerializer(student).data
        })
    
    # Check payment status
    today = timezone.now().date()
    valid_payment = Payment.objects.filter(
        student=student,
        status='VERIFIED',
        cycle_start__lte=today,
        cycle_end__gte=today
    ).first()
    
    if not valid_payment:
        scan_event = ScanEvent.objects.create(
            student=student,
            meal=meal,
            result='BLOCKED_NO_PAYMENT',
            device_info=device_info
        )
        return Response({
            'result': 'BLOCKED_NO_PAYMENT',
            'reason': 'No valid payment for current cycle',
            'student_snapshot': StudentSnapshotSerializer(student).data
        })
    
    # Check mess cuts
    is_cut = MessCut.objects.filter(
        student=student,
        from_date__lte=today,
        to_date__gte=today
    ).exists()
    
    # Check mess closures
    is_closed = MessClosure.objects.filter(
        from_date__lte=today,
        to_date__gte=today
    ).exists()
    
    if is_cut or is_closed:
        scan_event = ScanEvent.objects.create(
            student=student,
            meal=meal,
            result='BLOCKED_CUT',
            device_info=device_info
        )
        reason = 'Mess closed' if is_closed else 'Mess cut applied'
        return Response({
            'result': 'BLOCKED_CUT',
            'reason': reason,
            'student_snapshot': StudentSnapshotSerializer(student).data
        })
    
    # Check for duplicate scan (same meal, same day)
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    existing_scan = ScanEvent.objects.filter(
        student=student,
        meal=meal,
        scanned_at__gte=today_start,
        scanned_at__lt=today_end,
        result='ALLOWED'
    ).first()
    
    if existing_scan:
        return Response({
            'result': 'BLOCKED_DUPLICATE',
            'reason': f'{meal.title()} already served today',
            'student_snapshot': StudentSnapshotSerializer(student).data
        })
    
    # All checks passed - allow access
    scan_event = ScanEvent.objects.create(
        student=student,
        meal=meal,
        result='ALLOWED',
        device_info=device_info,
        staff_token=getattr(request.user, 'staff_token', None)
    )
    
    # Send notification to student
    from apps.utils.notifications import send_meal_scan_notification
    send_meal_scan_notification.delay(student.tg_user_id, meal, timezone.now())
    
    return Response({
        'result': 'ALLOWED',
        'student_snapshot': StudentSnapshotSerializer(student).data,
        'scan_event': ScanEventSerializer(scan_event).data
    })

@api_view(['GET'])
@permission_classes([IsStaffUser])
def student_snapshot(request, student_id):
    """Get student snapshot for staff"""
    student = get_object_or_404(Student, id=student_id)
    return Response(StudentSnapshotSerializer(student).data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_approve_registration(request, student_id):
    """Admin approve student registration"""
    if request.user.id not in settings.ADMIN_TG_IDS:
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    student = get_object_or_404(Student, id=student_id)
    student.status = 'APPROVED'
    student.save()
    
    # Send notification to student
    from apps.utils.notifications import send_registration_approved_notification
    send_registration_approved_notification.delay(student.tg_user_id, student.id)
    
    return Response({'message': 'Student approved successfully'})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_deny_registration(request, student_id):
    """Admin deny student registration"""
    if request.user.id not in settings.ADMIN_TG_IDS:
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    student = get_object_or_404(Student, id=student_id)
    student.status = 'DENIED'
    student.save()
    
    # Send notification to student
    from apps.utils.notifications import send_registration_denied_notification
    send_registration_denied_notification.delay(student.tg_user_id)
    
    return Response({'message': 'Student denied successfully'})
```

## 9. apps/api/serializers.py
```python
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from apps.core.models import Student, Payment, ScanEvent, MessCut, MessClosure

class StudentSnapshotSerializer(serializers.ModelSerializer):
    payment_ok = serializers.SerializerMethodField()
    today_cut = serializers.SerializerMethodField()
    today_closed = serializers.SerializerMethodField()
    
    class Meta:
        model = Student
        fields = ['id', 'name', 'roll_no', 'room_no', 'status', 
                 'payment_ok', 'today_cut', 'today_closed']
    
    def get_payment_ok(self, obj):
        today = timezone.now().date()
        return Payment.objects.filter(
            student=obj,
            status='VERIFIED',
            cycle_start__lte=today,
            cycle_end__gte=today
        ).exists()
    
    def get_today_cut(self, obj):
        today = timezone.now().date()
        return MessCut.objects.filter(
            student=obj,
            from_date__lte=today,
            to_date__gte=today
        ).exists()
    
    def get_today_closed(self, obj):
        today = timezone.now().date()
        return MessClosure.objects.filter(
            from_date__lte=today,
            to_date__gte=today
        ).exists()

class ScanEventSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.name', read_only=True)
    student_roll = serializers.CharField(source='student.roll_no', read_only=True)
    
    class Meta:
        model = ScanEvent
        fields = ['id', 'student_name', 'student_roll', 'meal', 
                 'scanned_at', 'result', 'device_info']

class PaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.name', read_only=True)
    student_roll = serializers.CharField(source='student.roll_no', read_only=True)
    
    class Meta:
        model = Payment
        fields = ['id', 'student_name', 'student_roll', 'cycle_start', 
                 'cycle_end', 'amount', 'screenshot_url', 'status', 
                 'source', 'created_at']
```

## 10. apps/api/permissions.py
```python
import hashlib
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone
from apps.core.models import StaffToken

class StaffTokenAuthentication(BaseAuthentication):
    """Custom authentication for staff tokens"""
    
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        try:
            staff_token = StaffToken.objects.get(
                token_hash=token_hash,
                active=True
            )
            
            # Check expiry
            if staff_token.expires_at and timezone.now() > staff_token.expires_at:
                raise AuthenticationFailed('Token expired')
            
            # Create a mock user object with staff token
            user = type('StaffUser', (), {
                'is_authenticated': True,
                'staff_token': staff_token
            })()
            
            return (user, staff_token)
            
        except StaffToken.DoesNotExist:
            raise AuthenticationFailed('Invalid token')

class IsStaffUser(BasePermission):
    """Permission class for staff users"""
    
    def has_permission(self, request, view):
        return hasattr(request.user, 'staff_token')
```

## 11. apps/scanner/views.py
```python
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json

@method_decorator(csrf_exempt, name='dispatch')
class ScannerView(View):
    """Staff QR Scanner Interface"""
    
    def get(self, request, token):
        """Render scanner page"""
        # Validate token (simplified for demo)
        context = {
            'token': token,
            'api_base': '/api/v1'
        }
        return render(request, 'scanner/scanner.html', context)

def scanner_page(request, token):
    """Staff scanner page with token validation"""
    # TODO: Validate staff token
    context = {
        'token': token,
        'meal_options': ['BREAKFAST', 'LUNCH', 'DINNER']
    }
    return render(request, 'scanner/scanner.html', context)
```

## 12. apps/scanner/templates/scanner/scanner.html
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mess Scanner</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/qr-scanner/1.4.2/qr-scanner.umd.min.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        
        .scanner-container {
            max-width: 400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .header {
            text-align: center;
            margin-bottom: 20px;
        }
        
        .header h1 {
            color: #333;
            margin: 0;
            font-size: 24px;
        }
        
        .camera-container {
            position: relative;
            width: 100%;
            height: 300px;
            background: #000;
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 20px;
        }
        
        #video {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .scan-overlay {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 200px;
            height: 200px;
            border: 2px solid #4CAF50;
            border-radius: 8px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .controls {
            margin-bottom: 20px;
        }
        
        .meal-selector {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 16px;
            margin-bottom: 10px;
        }
        
        .scan-btn {
            width: 100%;
            padding: 15px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
        }
        
        .scan-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        
        .result-container {
            margin-top: 20px;
            padding: 15px;
            border-radius: 6px;
            display: none;
        }
        
        .result-success {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }
        
        .result-error {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }
        
        .student-info {
            margin-top: 10px;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 4px;
        }
        
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 5px;
        }
        
        .status-ok { background: #28a745; }
        .status-error { background: #dc3545; }
        .status-warning { background: #ffc107; }
        
        .offline-indicator {
            position: fixed;
            top: 10px;
            right: 10px;
            padding: 8px 12px;
            background: #ff6b6b;
            color: white;
            border-radius: 4px;
            font-size: 12px;
            display: none;
        }
    </style>
</head>
<body>
    <div class="offline-indicator" id="offlineIndicator">
        📡 Offline
    </div>
    
    <div class="scanner-container">
        <div class="header">
            <h1>🍽️ Mess Scanner</h1>
            <p>Scan student QR codes for meal access</p>
        </div>
        
        <div class="camera-container">
            <video id="video" autoplay></video>
            <div class="scan-overlay"></div>
        </div>
        
        <div class="controls">
            <select id="mealSelector" class="meal-selector">
                <option value="">Select Meal</option>
                <option value="BREAKFAST">🌅 Breakfast</option>
                <option value="LUNCH">☀️ Lunch</option>
                <option value="DINNER">🌙 Dinner</option>
            </select>
            
            <button id="scanBtn" class="scan-btn" disabled>
                📷 Ready to Scan
            </button>
        </div>
        
        <div id="resultContainer" class="result-container">
            <div id="resultMessage"></div>
            <div id="studentInfo" class="student-info"></div>
        </div>
    </div>

    <script>
        class MessScanner {
            constructor() {
                this.video = document.getElementById('video');
                this.mealSelector = document.getElementById('mealSelector');
                this.scanBtn = document.getElementById('scanBtn');
                this.resultContainer = document.getElementById('resultContainer');
                this.resultMessage = document.getElementById('resultMessage');
                this.studentInfo = document.getElementById('studentInfo');
                this.offlineIndicator = document.getElementById('offlineIndicator');
            
            this.token = '{{ token }}';
            this.apiBase = '/api/v1';
            this.scanner = null;
            this.isScanning = false;
            this.lastScanResult = null;
            
            this.init();
        }
        
        async init() {
            await this.setupCamera();
            this.setupEventListeners();
            this.updateMealDefault();
            this.checkNetworkStatus();
        }
        
        async setupCamera() {
            try {
                this.scanner = new QrScanner(
                    this.video,
                    result => this.handleScanResult(result),
                    {
                        onDecodeError: error => {
                            // Ignore decode errors, they're normal
                        },
                        maxScansPerSecond: 2,
                        highlightScanRegion: false,
                        highlightCodeOutline: false
                    }
                );
                
                await this.scanner.start();
                console.log('Camera started successfully');
            } catch (error) {
                console.error('Camera setup failed:', error);
                this.showResult('error', 'Camera access failed. Please allow camera permissions.');
            }
        }
        
        setupEventListeners() {
            this.mealSelector.addEventListener('change', () => {
                this.scanBtn.disabled = !this.mealSelector.value;
                this.scanBtn.textContent = this.mealSelector.value ? 
                    '📷 Ready to Scan' : '📷 Select Meal First';
            });
            
            this.scanBtn.addEventListener('click', () => {
                if (this.mealSelector.value) {
                    this.scanBtn.textContent = '🔍 Scanning...';
                    this.isScanning = true;
                }
            });
            
            // Network status monitoring
            window.addEventListener('online', () => {
                this.offlineIndicator.style.display = 'none';
                this.retryPendingScans();
            });
            
            window.addEventListener('offline', () => {
                this.offlineIndicator.style.display = 'block';
            });
        }
        
        updateMealDefault() {
            const now = new Date();
            const time = now.getHours() * 100 + now.getMinutes();
            
            let defaultMeal = '';
            if (time >= 700 && time <= 930) defaultMeal = 'BREAKFAST';
            else if (time >= 1200 && time <= 1430) defaultMeal = 'LUNCH';
            else if (time >= 1900 && time <= 2130) defaultMeal = 'DINNER';
            
            if (defaultMeal) {
                this.mealSelector.value = defaultMeal;
                this.scanBtn.disabled = false;
                this.scanBtn.textContent = '📷 Ready to Scan';
            }
        }
        
        async handleScanResult(result) {
            if (!this.isScanning || !this.mealSelector.value) return;
            
            this.isScanning = false;
            this.scanBtn.textContent = '⏳ Processing...';
            this.scanBtn.disabled = true;
            
            const scanData = {
                qr_data: result.data,
                meal: this.mealSelector.value,
                device_info: navigator.userAgent
            };
            
            try {
                const response = await this.apiCall('/scanner/scan', scanData);
                this.processScanResponse(response);
            } catch (error) {
                console.error('Scan failed:', error);
                
                if (!navigator.onLine) {
                    this.storePendingScan(scanData);
                    this.showResult('warning', 'Offline - scan stored for retry');
                } else {
                    this.showResult('error', `Scan failed: ${error.message}`);
                }
            }
            
            // Reset UI
            setTimeout(() => {
                this.scanBtn.disabled = false;
                this.scanBtn.textContent = '📷 Ready to Scan';
                this.isScanning = false;
            }, 2000);
        }
        
        async apiCall(endpoint, data) {
            const response = await fetch(this.apiBase + endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.token}`
                },
                body: JSON.stringify(data)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            return await response.json();
        }
        
        processScanResponse(response) {
            const { result, student_snapshot, reason } = response;
            
            if (result === 'ALLOWED') {
                this.showResult('success', '✅ Access Granted');
                this.playSuccessSound();
            } else {
                this.showResult('error', `❌ Access Denied: ${reason}`);
                this.playErrorSound();
            }
            
            if (student_snapshot) {
                this.showStudentInfo(student_snapshot);
            }
            
            this.lastScanResult = response;
        }
        
        showResult(type, message) {
            this.resultContainer.className = `result-container result-${type}`;
            this.resultContainer.style.display = 'block';
            this.resultMessage.textContent = message;
            
            // Auto-hide after 5 seconds
            setTimeout(() => {
                this.resultContainer.style.display = 'none';
            }, 5000);
        }
        
        showStudentInfo(student) {
            const paymentStatus = student.payment_ok ? 'OK' : 'Not OK';
            const cutStatus = student.today_cut || student.today_closed ? 'Cut/Closed' : 'Available';
            
            this.studentInfo.innerHTML = `
                <div><strong>${student.name}</strong> (${student.roll_no})</div>
                <div>Room: ${student.room_no}</div>
                <div>
                    <span class="status-indicator status-${student.payment_ok ? 'ok' : 'error'}"></span>
                    Payment: ${paymentStatus}
                </div>
                <div>
                    <span class="status-indicator status-${student.today_cut || student.today_closed ? 'warning' : 'ok'}"></span>
                    Status: ${cutStatus}
                </div>
            `;
        }
        
        playSuccessSound() {
            // Create short beep sound
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            oscillator.frequency.value = 800;
            oscillator.type = 'sine';
            
            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);
            
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.2);
        }
        
        playErrorSound() {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            oscillator.frequency.value = 300;
            oscillator.type = 'sawtooth';
            
            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
            
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.5);
        }
        
        storePendingScan(scanData) {
            const pending = JSON.parse(localStorage.getItem('pendingScans') || '[]');
            pending.push({
                ...scanData,
                timestamp: Date.now()
            });
            localStorage.setItem('pendingScans', JSON.stringify(pending));
        }
        
        async retryPendingScans() {
            const pending = JSON.parse(localStorage.getItem('pendingScans') || '[]');
            if (pending.length === 0) return;
            
            console.log(`Retrying ${pending.length} pending scans`);
            
            for (const scanData of pending) {
                try {
                    const response = await this.apiCall('/scanner/scan', scanData);
                    console.log('Retry successful:', response);
                } catch (error) {
                    console.error('Retry failed:', error);
                    return; // Stop retrying if network is still bad
                }
            }
            
            localStorage.removeItem('pendingScans');
            this.showResult('success', `✅ ${pending.length} offline scans processed`);
        }
        
        checkNetworkStatus() {
            if (!navigator.onLine) {
                this.offlineIndicator.style.display = 'block';
            }
        }
    }
    
    // Initialize scanner when page loads
    document.addEventListener('DOMContentLoaded', () => {
        new MessScanner();
    });
    </script>
</body>
</html>
```

## 13. apps/utils/notifications.py
```python
from celery import shared_task
import telegram
from django.conf import settings
from apps.core.models import Student, AuditLog
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def send_telegram_message(self, chat_id, text, parse_mode='Markdown'):
    """Send Telegram message with retry logic"""
    try:
        bot = telegram.Bot(token=settings.TELEGRAM_BOT_TOKEN)
        bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode
        )
        
        # Log successful notification
        AuditLog.objects.create(
            actor_type='SYSTEM',
            event_type='NOTIFICATION_SENT',
            payload={
                'chat_id': chat_id,
                'message': text[:100] + '...' if len(text) > 100 else text
            }
        )
        
    except Exception as exc:
        logger.error(f"Failed to send Telegram message: {exc}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        else:
            # Log failed notification
            AuditLog.objects.create(
                actor_type='SYSTEM',
                event_type='NOTIFICATION_FAILED',
                payload={
                    'chat_id': chat_id,
                    'error': str(exc),
                    'message': text[:100] + '...' if len(text) > 100 else text
                }
            )

@shared_task
def send_registration_approved_notification(tg_user_id, student_id):
    """Send notification when registration is approved"""
    text = (
        "✅ *Registration Approved!*\n\n"
        "Your mess access is now active. You can now:\n"
        "• Upload payments\n"
        "• Take mess cuts\n"
        "• Access your QR code\n\n"
        "Use /start to access all features."
    )
    
    send_telegram_message.delay(tg_user_id, text)

@shared_task
def send_registration_denied_notification(tg_user_id):
    """Send notification when registration is denied"""
    text = (
        "❌ *Registration Denied*\n\n"
        "Your registration application has been denied. "
        "Please contact the mess admin if you believe this is an error."
    )
    
    send_telegram_message.delay(tg_user_id, text)

@shared_task
def send_payment_verified_notification(tg_user_id, cycle_start, cycle_end):
    """Send notification when payment is verified"""
    text = (
        f"✅ *Payment Verified*\n\n"
        f"Your payment has been verified for the cycle:\n"
        f"📅 {cycle_start} to {cycle_end}\n\n"
        f"You're all set for mess access during this period!"
    )
    
    send_telegram_message.delay(tg_user_id, text)

@shared_task
def send_payment_denied_notification(tg_user_id, reason=""):
    """Send notification when payment is denied"""
    text = (
        "⚠️ *Payment Could Not Be Verified*\n\n"
        "Your payment screenshot could not be verified. "
        "Please re-upload a clear screenshot of your payment.\n\n"
    )
    
    if reason:
        text += f"Reason: {reason}\n\n"
    
    text += "Use /start → Upload Payment to try again."
    
    send_telegram_message.delay(tg_user_id, text)

@shared_task
def send_mess_cut_confirmation(tg_user_id, from_date, to_date):
    """Send notification when mess cut is applied"""
    text = (
        f"✂️ *Mess Cut Confirmed*\n\n"
        f"Your mess cut has been applied for:\n"
        f"📅 From: {from_date}\n"
        f"📅 To: {to_date}\n\n"
        f"These days will be excluded from your meal access and charges."
    )
    
    send_telegram_message.delay(tg_user_id, text)

@shared_task
def send_meal_scan_notification(tg_user_id, meal, scan_time):
    """Send notification when QR is scanned for meal"""
    meal_emoji = {
        'BREAKFAST': '🌅',
        'LUNCH': '☀️',
        'DINNER': '🌙'
    }
    
    text = (
        f"🍽️ *QR Scanned*\n\n"
        f"{meal_emoji.get(meal, '🍽️')} {meal.title()} access granted\n"
        f"⏰ Time: {scan_time.strftime('%H:%M:%S')}\n\n"
        f"Enjoy your meal! 😊"
    )
    
    send_telegram_message.delay(tg_user_id, text)

@shared_task
def send_mess_closure_broadcast(closure_id):
    """Send mess closure notification to all approved students"""
    from apps.core.models import MessClosure
    
    try:
        closure = MessClosure.objects.get(id=closure_id)
        
        text = (
            f"📢 *Mess Closure Notice*\n\n"
            f"The mess will be closed from:\n"
            f"📅 {closure.from_date} to {closure.to_date}\n\n"
        )
        
        if closure.reason:
            text += f"Reason: {closure.reason}\n\n"
        
        text += "These days won't be charged to your account."
        
        # Send to all approved students
        approved_students = Student.objects.filter(status='APPROVED')
        for student in approved_students:
            send_telegram_message.delay(student.tg_user_id, text)
            
    except MessClosure.DoesNotExist:
        logger.error(f"MessClosure {closure_id} not found")

@shared_task
def send_qr_regeneration_notice():
    """Send QR regeneration notice to all approved students"""
    text = (
        "🔄 *QR Codes Regenerated*\n\n"
        "All QR codes have been regenerated for security purposes. "
        "Your old QR code is no longer valid.\n\n"
        "Use /start → My QR Code to get your new QR code."
    )
    
    approved_students = Student.objects.filter(status='APPROVED')
    for student in approved_students:
        send_telegram_message.delay(student.tg_user_id, text)
```

## 14. apps/utils/backup_utils.py
```python
from celery import shared_task
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from django.conf import settings
from apps.core.models import DLQLog, AuditLog
import logging

logger = logging.getLogger(__name__)

def get_sheets_service():
    """Get Google Sheets API service"""
    credentials = Credentials.from_service_account_info(
        settings.GOOGLE_SHEETS_CREDENTIALS,
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    return build('sheets', 'v4', credentials=credentials)

@shared_task(bind=True, max_retries=3)
def backup_to_sheets(self, sheet_name, data):
    """Backup data to Google Sheets with retry logic"""
    try:
        service = get_sheets_service()
        spreadsheet_id = settings.GOOGLE_SHEETS_SPREADSHEET_ID
        
        # Prepare the data for sheets
        values = [list(data.values())]
        
        body = {
            'values': values
        }
        
        # Append to the specified sheet
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet_name}!A:Z',
            valueInputOption='RAW',
            body=body
        ).execute()
        
        logger.info(f"Successfully backed up to {sheet_name}: {result}")
        
        # Log successful backup
        AuditLog.objects.create(
            actor_type='SYSTEM',
            event_type='BACKUP_SUCCESS',
            payload={
                'sheet_name': sheet_name,
                'rows_added': result.get('updates', {}).get('updatedRows', 0)
            }
        )
        
    except Exception as exc:
        logger.error(f"Failed to backup to sheets: {exc}")
        
        if self.request.retries < self.max_retries:
            # Exponential backoff
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(countdown=countdown)
        else:
            # Store in DLQ for manual processing
            DLQLog.objects.create(
                operation_type='SHEETS_BACKUP',
                payload={
                    'sheet_name': sheet_name,
                    'data': data
                },
                error_message=str(exc)
            )
            
            logger.error(f"Backup failed permanently, stored in DLQ: {exc}")

@shared_task
def backup_registration(student_data):
    """Backup student registration to sheets"""
    backup_data = {
        'timestamp': student_data['created_at'],
        'student_id': student_data['id'],
        'name': student_data['name'],
        'roll_no': student_data['roll_no'],
        'room_no': student_data['room_no'],
        'phone': student_data['phone'],
        'status': student_data['status'],
        'tg_user_id': student_data['tg_user_id']
    }
    
    backup_to_sheets.delay('registrations', backup_data)

@shared_task
def backup_payment(payment_data):
    """Backup payment to sheets"""
    backup_data = {
        'timestamp': payment_data['created_at'],
        'payment_id': payment_data['id'],
        'student_id': payment_data['student_id'],
        'student_name': payment_data['student_name'],
        'cycle_start': payment_data['cycle_start'],
        'cycle_end': payment_data['cycle_end'],
        'amount': payment_data['amount'],
        'status': payment_data['status'],
        'source': payment_data['source']
    }
    
    backup_to_sheets.delay('payments', backup_data)

@shared_task
def backup_scan_event(scan_data):
    """Backup scan event to sheets"""
    backup_data = {
        'timestamp': scan_data['scanned_at'],
        'student_id': scan_data['student_id'],
        'student_name': scan_data['student_name'],
        'meal': scan_data['meal'],
        'result': scan_data['result'],
        'device_info': scan_data.get('device_info', '')
    }
    
    backup_to_sheets.delay('scan_events', backup_data)

@shared_task
def backup_mess_cut(cut_data):
    """Backup mess cut to sheets"""
    backup_data = {
        'timestamp': cut_data['applied_at'],
        'student_id': cut_data['student_id'],
        'student_name': cut_data['student_name'],
        'from_date': cut_data['from_date'],
        'to_date': cut_data['to_date'],
        'applied_by': cut_data['applied_by'],
        'cutoff_ok': cut_data['cutoff_ok']
    }
    
    backup_to_sheets.delay('mess_cuts', backup_data)

@shared_task
def process_dlq_backups():
    """Process failed backups from DLQ"""
    failed_backups = DLQLog.objects.filter(
        operation_type='SHEETS_BACKUP',
        processed_at__isnull=True,
        retry_count__lt=5
    )
    
    for dlq_item in failed_backups:
        try:
            sheet_name = dlq_item.payload['sheet_name']
            data = dlq_item.payload['data']
            
            # Retry the backup
            backup_to_sheets.delay(sheet_name, data)
            
            # Update retry count
            dlq_item.retry_count += 1
            dlq_item.save()
            
        except Exception as e:
            logger.error(f"Failed to process DLQ item {dlq_item.id}: {e}")
```

## 15. Management Commands & Setup Files

### mess_management/celery.py
```python
import os
from celery import Celery
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mess_management.settings')

app = Celery('mess_management')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
```

### docker-compose.yml
```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: mess_db
      POSTGRES_USER: mess_user
      POSTGRES_PASSWORD: mess_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  web:
    build: .
    command: gunicorn mess_management.wsgi:application --bind 0.0.0.0:8000
    volumes:
      - .:/app
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    env_file:
      - .env

  worker:
    build: .
    command: celery -A mess_management worker --loglevel=info
    volumes:
      - .:/app
    depends_on:
      - db
      - redis
    env_file:
      - .env

  scheduler:
    build: .
    command: celery -A mess_management beat --loglevel=info
    volumes:
      - .:/app
    depends_on:
      - db
      - redis
    env_file:
      - .env

volumes:
  postgres_data:
  static_volume:
  media_volume:
```

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["gunicorn", "mess_management.wsgi:application", "--bind", "0.0.0.0:8000"]
```

## 16. README.md with Setup Instructions