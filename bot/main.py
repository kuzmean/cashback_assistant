import sys, os  # Added to modify sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
print("sys.path:", sys.path)  # Debug: Check that project root is included

from telegram.ext import Application, MessageHandler, filters, CommandHandler, ConversationHandler, CallbackQueryHandler, DictPersistence
from config import Config
from bot.database.models import Base
from sqlalchemy import create_engine
from bot.handlers import image_processing, text_processing
from bot.handlers.text_processing import (
    start_adding, cancel,
    BANK_SELECTION, CATEGORY_SELECTION,
    PERCENTAGE_INPUT, POST_SAVE_ACTIONS,
    RESET_CHOOSE_BANK, RESET_CONFIRM,
    BANK_INPUT, CATEGORY_INPUT
)
import logging
from telegram import Update
from telegram.ext import ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update, context):
    await update.message.reply_text(
        "Welcome to Cashback Assistant! 🤑\n\n"
        "📝 Доступные команды:\n\n"
        "/add - добавить новые данные о кэшбэке\n"
        "/reset - сбросить данные для выбранного банка\n"
        "/reset_category - сбросить данные для категории\n"
        "/summary - показать сводку по кэшбэкам\n"
        "/full_reset - сбросить все данные\n"
        "/cancel - отменить текущую операцию"
    )

def main():
    logger.info("Starting bot.")
    Config.check_token()
    # Initialize database
    engine = create_engine(Config.DATABASE_URL)
    Base.metadata.create_all(engine)

    # Create bot application
    application = Application.builder() \
        .token(Config.TELEGRAM_TOKEN) \
        .persistence(DictPersistence()) \
        .build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, image_processing.handle_image))

    # Conversation handler
    conversation_handler = ConversationHandler(
        entry_points=[
            CommandHandler("add", start_adding),
            CommandHandler("reset", text_processing.start_reset)
        ],
        states={
            BANK_SELECTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_processing.handle_bank_selection),
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_processing.handle_custom_bank_input)
            ],
            CATEGORY_SELECTION: [
                CallbackQueryHandler(text_processing.handle_category_selection)
            ],
            CATEGORY_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_processing.handle_custom_category_input)
            ],
            PERCENTAGE_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_processing.handle_percentage_input)
            ],
            POST_SAVE_ACTIONS: [
                CallbackQueryHandler(text_processing.handle_post_save_actions, pattern="^(add_category|next_bank|command_reset|command_summary)$")
            ],
            RESET_CHOOSE_BANK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_processing.handle_reset_bank)
            ],
            RESET_CONFIRM: [
                CallbackQueryHandler(text_processing.handle_reset_confirm, pattern="^(confirm_reset|confirm_reset_all|cancel_reset)$")
            ],
            BANK_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_processing.handle_custom_bank_input)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    application.add_handler(conversation_handler)

    # Add other handlers
    application.add_handler(CommandHandler("summary", text_processing.generate_summary))

    # Add CallbackQueryHandlers
    application.add_handler(CallbackQueryHandler(
        text_processing.handle_command_buttons,
        pattern="^command_"
    ))
    # Add a general CallbackQueryHandler last
    application.add_handler(CallbackQueryHandler(text_processing.handle_all_callbacks))

    # Add full reset handler
    application.add_handler(CommandHandler(
        "full_reset", 
        text_processing.handle_full_reset
    ))

    # Add reset category handler
    application.add_handler(CommandHandler(
        "reset_category", 
        text_processing.start_reset_category
    ))

    # Error handler
    application.add_error_handler(error_handler)

    application.run_polling()

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling update:", exc_info=context.error)
    if update and update.callback_query:
        await update.callback_query.answer("⚠️ Произошла ошибка, попробуйте еще раз")

if __name__ == "__main__":
    main()