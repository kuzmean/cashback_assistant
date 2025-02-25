import os
from dotenv import find_dotenv, load_dotenv

# Загрузка переменных окружения
load_dotenv(find_dotenv())

# Telegram
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

# GigaChat
GIGACHAT_CREDENTIALS = os.environ["GIGACHAT_CREDENTIALS"]
GIGACHAT_MODEL = "GigaChat-Max"
GIGACHAT_TEMPERATURE = 0.1
GIGACHAT_TIMEOUT = 6000

# Database
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///cashback.db")
DATABASE_PATH = DATABASE_URL.replace("sqlite:///", "")

# Bot Settings
DEFAULT_CATEGORY_EMOJI = "📋"
CATEGORY_EMOJIS = {
    "одежда": "👕",
    "продукты": "🛒",
    "рестораны": "🍽️",
    "образование": "📚",
    "техника": "📱",
    "такси": "🚕",
    "супермаркеты": "🏪",
    "кафе": "☕",
    "аптеки": "💊",
    "азс": "⛽",
    "кино": "🎬",
    "заправки": "⛽"
}

# Default categories
DEFAULT_CATEGORIES = ["одежда", "продукты", "рестораны", "образование", "техника", "такси"]

# External links
CARD_LINKS = {
    "Альфа банк": "https://alfa.me/xGH5KO",
    "Тинькофф": "https://www.tbank.ru/baf/4HLAiOHJMyt"
} 