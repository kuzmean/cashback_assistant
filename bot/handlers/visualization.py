import matplotlib.pyplot as plt
import io
from sqlalchemy.orm import sessionmaker
from bot.database.models import CashbackRecord
from config import Config
from telegram import Update, InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from sqlalchemy import create_engine
import matplotlib
from tabulate import tabulate
import logging

matplotlib.use('Agg')  # Важно для работы в бэкенде

engine = create_engine(Config.DATABASE_URL)
Session = sessionmaker(bind=engine)
logger = logging.getLogger(__name__)

async def generate_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        message = update.effective_message
        
        session = Session()
        records = session.query(CashbackRecord).filter(
            CashbackRecord.user_id == user_id,
            CashbackRecord.is_active == True
        ).all()

        if not records:
            await message.reply_text("📭 У вас пока нет сохраненных данных")
            return

        # Группируем по категориям
        categories = {}
        for record in records:
            if record.category not in categories:
                categories[record.category] = []
            categories[record.category].append((record.percentage, record.bank_name))
        
        # Сортируем категории и данные внутри них
        sorted_categories = sorted(categories.keys())
        table_data = []
        
        for category in sorted_categories:
            # Сортируем банки по убыванию кэшбэка
            sorted_banks = sorted(categories[category], key=lambda x: (-x[0], x[1]))
            
            # Добавляем первую строку с категорией
            table_data.append([
                category,
                f"{int(sorted_banks[0][0])}%",
                sorted_banks[0][1]
            ])
            
            # Добавляем остальные банки под категорией
            for percent, bank in sorted_banks[1:]:
                table_data.append([
                    "",  # Пустое поле для категории
                    f"{int(percent)}%",
                    bank
                ])

        # Формируем таблицу
        table = tabulate(
            table_data,
            headers=["Категория", "Кэшбэк", "Банк"],
            tablefmt="pretty",
            stralign="left",
            missingval=""
        )

        await message.reply_text(f"<pre>{table}</pre>", parse_mode="HTML")
        
        # Используем те же callback_data, что и в основном меню
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить данные", callback_data="next_bank")],
            [InlineKeyboardButton("🗑️ Сбросить статистику", callback_data="command_reset")]
        ])
        await message.reply_text(
            "Выберите действие:",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        await message.reply_text("❌ Ошибка при формировании сводки")
    finally:
        session.close() 