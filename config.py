import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///cashback.db')
    
    # Временная проверка
    @classmethod
    def check_token(cls):
        if not cls.TELEGRAM_TOKEN or 'your_bot_token' in cls.TELEGRAM_TOKEN:
            raise ValueError('Invalid Telegram token!')

    BANKS = ["Тинькофф", "Сбербанк", "Альфа-Банк", "ВТБ", "Другой"]

    CATEGORIES = [
        "АЗС",
        "Продукты",
        "Рестораны",
        "Аптеки",
        "Транспорт",
        "Маркетплейсы",
        "Развлечения",
        "Другое"
    ] 