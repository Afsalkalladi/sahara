# URL configuration for mess_management project.
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
	path('admin/', admin.site.urls),
	path('api/v1/', include('apps.api.urls')),
	path('scanner/', include('apps.scanner.urls')),
]
