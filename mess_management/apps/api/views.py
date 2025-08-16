# Views for api app

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
