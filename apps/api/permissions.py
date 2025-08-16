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
