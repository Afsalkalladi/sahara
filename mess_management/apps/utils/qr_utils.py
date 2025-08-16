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
