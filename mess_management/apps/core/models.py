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
