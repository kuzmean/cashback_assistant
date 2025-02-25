from .config import TELEGRAM_TOKEN
from .handlers import register_handlers
from telebot import TeleBot

def create_bot():
    bot = TeleBot(TELEGRAM_TOKEN)
    register_handlers(bot)
    return bot 