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
        "❌ *Registration Denied!*\n\n"
        "Your registration application has been denied. "
        "Please contact the mess admin if you believe this is an error."
    )
    
    send_telegram_message.delay(tg_user_id, text)

@shared_task
def send_payment_verified_notification(tg_user_id, cycle_start, cycle_end):
    """Send notification when payment is verified"""
    text = (
        f"✅ *Payment Verified!*\n\n"
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
        f"✂️ *Mess Cut Confirmed!*\n\n"
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
