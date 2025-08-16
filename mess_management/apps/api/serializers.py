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
