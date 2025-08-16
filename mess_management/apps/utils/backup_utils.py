# Backup utilities

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
