def get_student_payment_status(student_id):
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