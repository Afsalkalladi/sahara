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

# Handlers for telegram bot
