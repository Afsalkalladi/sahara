# Views for scanner app

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
