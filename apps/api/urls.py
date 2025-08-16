# URLs for api app
from django.urls import path
from .views import scanner_scan, student_snapshot, admin_approve_registration, admin_deny_registration

urlpatterns = [
	path('scanner/scan', scanner_scan, name='scanner_scan'),
	path('student/<int:student_id>/snapshot', student_snapshot, name='student_snapshot'),
	path('admin/approve/<int:student_id>', admin_approve_registration, name='admin_approve_registration'),
	path('admin/deny/<int:student_id>', admin_deny_registration, name='admin_deny_registration'),
]
