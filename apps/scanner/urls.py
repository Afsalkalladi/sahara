# URLs for scanner app
from django.urls import path
from .views import ScannerView, scanner_page

urlpatterns = [
	path('<str:token>/', ScannerView.as_view(), name='scanner_view'),
	path('page/<str:token>/', scanner_page, name='scanner_page'),
]
