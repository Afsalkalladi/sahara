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
