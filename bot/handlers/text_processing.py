import re
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from bot.database.models import CashbackRecord
from config import Config
from bot.handlers import visualization
import logging
from tabulate import tabulate
from datetime import datetime

logger = logging.getLogger(__name__)

engine = create_engine(Config.DATABASE_URL)
Session = sessionmaker(bind=engine)

# Обновленные состояния
BANK_SELECTION, CATEGORY_SELECTION, PERCENTAGE_INPUT, POST_SAVE_ACTIONS = range(4)
BANK_INPUT = 6  # Новое состояние для ввода своего банка
CATEGORY_INPUT = 7  # Новое состояние для ввода своей категории

# Добавим новые состояния для сброса
RESET_CHOOSE_BANK, RESET_CONFIRM = range(4, 6)

async def get_user_banks(user_id: int) -> list:
    """Получаем список всех банков пользователя"""
    session = Session()
    try:
        banks = session.query(CashbackRecord.bank_name).filter(
            CashbackRecord.user_id == user_id,
            CashbackRecord.is_active == True
        ).distinct().all()
        user_banks = [bank[0] for bank in banks]
        # Добавляем стандартные банки
        all_banks = list(set(Config.BANKS + user_banks))
        all_banks.sort()  # Сортируем по алфавиту
        if "Другой" in all_banks:
            all_banks.remove("Другой")
            all_banks.append("Другой")  # Перемещаем "Другой" в конец
        return all_banks
    finally:
        session.close()

async def get_user_categories(user_id: int) -> list:
    """Получаем список всех категорий пользователя"""
    session = Session()
    try:
        categories = session.query(CashbackRecord.category).filter(
            CashbackRecord.user_id == user_id
        ).distinct().all()
        user_categories = [cat[0] for cat in categories]
        # Добавляем стандартные категории
        all_categories = list(set(Config.CATEGORIES + user_categories))
        all_categories.sort()  # Сортируем по алфавиту
        if "Другое" in all_categories:
            all_categories.remove("Другое")
            all_categories.append("Другое")  # Перемещаем "Другое" в конец
        return all_categories
    finally:
        session.close()

async def start_adding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Если update пришел из callback, используем его message
    message = update.message if update.message else update.callback_query.message
    user_banks = await get_user_banks(update.effective_user.id)
    buttons = [[bank] for bank in user_banks]
    reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
    await message.reply_text(
        "🏦 Выберите банк из списка:",
        reply_markup=reply_markup
    )
    return BANK_SELECTION

async def handle_bank_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_bank = update.message.text.strip()
    
    if selected_bank == "Другой":
        await update.message.reply_text("🏦 Введите название вашего банка:")
        return BANK_INPUT
    else:
        context.user_data['current_bank'] = selected_bank
        return await show_category_selection(update.message, context)

async def show_category_selection(message, context: ContextTypes.DEFAULT_TYPE):
    user_categories = await get_user_categories(message.chat.id)
    keyboard = [
        [InlineKeyboardButton(cat, callback_data=f"cat_{cat}")]
        for cat in user_categories
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text(
        "📋 Выберите категорию:",
        reply_markup=reply_markup
    )
    return CATEGORY_SELECTION

async def handle_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    category = query.data.replace("cat_", "")
    if category == "Другое":
        await query.edit_message_text("📝 Введите название вашей категории:")
        return CATEGORY_INPUT
    else:
        context.user_data['current_category'] = category
        await query.edit_message_text(f"💵 Введите процент кэшбэка для {category}:")
        return PERCENTAGE_INPUT

async def handle_percentage_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        percentage = float(update.message.text.replace('%', '').strip())
        data = {
            'bank': context.user_data['current_bank'],
            'category': context.user_data['current_category'],
            'cashback': percentage
        }

        await save_cashback_data(update.effective_user.id, data)

        # Кнопки после сохранения
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить категорию", callback_data="add_category")],
            [InlineKeyboardButton("➡️ Следующий банк", callback_data="next_bank")],
            [InlineKeyboardButton("🗑️ Сбросить статистику", callback_data="command_reset")],
            [InlineKeyboardButton("📊 Показать сводку", callback_data="command_summary")]
        ])

        await update.message.reply_text(
            "✅ Данные сохранены!",
            reply_markup=keyboard
        )
        return POST_SAVE_ACTIONS

    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Введите число, например: 5")
        return PERCENTAGE_INPUT

async def handle_post_save_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "add_category":
        return await show_category_selection(query.message, context)
    elif query.data == "next_bank":
        context.user_data.pop('current_bank', None)
        new_update = Update(update.update_id + 1, message=query.message)
        return await start_adding(new_update, context)
    elif query.data == "command_summary":
        return await generate_summary(update, context)
    elif query.data == "command_reset":
        return await start_reset(update, context)

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена диалога"""
    await update.message.reply_text("❌ Добавление данных отменено.")
    return ConversationHandler.END

async def handle_command_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    command = query.data.replace("command_", "")

    if command == "add":
        return await start_adding(update, context)
    elif command == "reset":
        return await start_reset(update, context)
    elif command == "summary":
        return await generate_summary(update, context)
    elif command == "full_reset":
        return await handle_full_reset(update, context)

    return ConversationHandler.END

async def generate_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        message = update.message or update.callback_query.message

        session = Session()
        records = session.query(CashbackRecord).filter(
            CashbackRecord.user_id == user_id,
            CashbackRecord.is_active == True
        ).all()

        if not records:
            await message.reply_text("📭 У вас пока нет сохраненных данных")
            await message.reply_text(
                "📝 Доступные команды:\n\n"
                "/add - добавить новые данные о кэшбэке\n"
                "/reset - сбросить данные для выбранного банка\n"
                "/summary - показать сводку по кэшбэкам\n"
                "/full_reset - сбросить все данные\n"
                "/cancel - отменить текущую операцию"
            )
            return ConversationHandler.END

        categories = {}
        for record in records:
            if record.category not in categories:
                categories[record.category] = []
            categories[record.category].append((record.percentage, record.bank_name))

        sorted_categories = sorted(categories.keys())
        table = "<b>🏆 Лучшие кэшбэки по категориям:</b>\n\n"

        for category in sorted_categories:
            sorted_banks = sorted(categories[category], key=lambda x: (-x[0], x[1]))

            emoji = get_category_emoji(category)
            table += f"<b>{emoji} {category}</b>\n"
            table += f"└ 🥇 {sorted_banks[0][1]}: <b>{int(sorted_banks[0][0])}%</b>\n"

            for i, (percent, bank) in enumerate(sorted_banks[1:], 1):
                medal = "🥈" if i == 1 else "🥉" if i == 2 else "  •"
                table += f"└ {medal} {bank}: {int(percent)}%\n"
            table += "\n"

        current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        footer = f"\n📅 Актуально на: {current_date}"
        await message.reply_text(
            f"{table}{footer}",
            parse_mode="HTML"
        )

        # Добавляем справку по командам
        help_text = (
            "📝 Доступные команды:\n\n"
            "/add - добавить новые данные о кэшбэке\n"
            "/reset - сбросить данные для выбранного банка\n"
            "/summary - показать эту сводку\n"
            "/full_reset - сбросить все данные\n"
            "/cancel - отменить текущую операцию"
        )
        await message.reply_text(help_text)

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        await message.reply_text("❌ Ошибка при формировании сводки")
        return ConversationHandler.END
    finally:
        session.close()

def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить данные", callback_data="command_add")],
        [InlineKeyboardButton("🗑️ Сбросить все", callback_data="command_full_reset")],
        [InlineKeyboardButton("📊 Показать сводку", callback_data="command_summary")]
    ])

async def handle_all_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "add_category":
        return await handle_post_save_actions(update, context)
    elif data == "next_bank":
        return await handle_post_save_actions(update, context)
    elif data == "command_reset":
        return await start_reset(update, context)
    elif data == "command_summary":
        return await generate_summary(update, context)

    return ConversationHandler.END

async def start_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message if update.message else update.callback_query.message
    session = Session()
    try:
        banks = session.query(CashbackRecord.bank_name).filter(
            CashbackRecord.user_id == update.effective_user.id
        ).distinct().all()
        banks = [bank[0] for bank in banks]
        if banks:
            buttons = [[bank] for bank in banks]
            buttons.append(["🗑️ Сбросить все банки"])
            reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
            text = "🏦 Выберите банк для сброса:"
            await message.reply_text(text, reply_markup=reply_markup)
        else:
            await message.reply_text("📭 Нет данных для сброса")
            await message.reply_text(
                "📝 Доступные команды:\n\n"
                "/add - добавить новые данные о кэшбэке\n"
                "/reset - сбросить данные для выбранного банка\n"
                "/summary - показать сводку по кэшбэкам\n"
                "/full_reset - сбросить все данные\n"
                "/cancel - отменить текущую операцию"
            )
    finally:
        session.close()
    return ConversationHandler.END if not banks else RESET_CHOOSE_BANK

async def handle_reset_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_option = update.message.text.strip()
    
    if selected_option == "🗑️ Сбросить все банки":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_reset_all"),
             InlineKeyboardButton("❌ Отмена", callback_data="cancel_reset")]
        ])
        await update.message.reply_text(
            "⚠️ Вы уверены, что хотите сбросить данные для ВСЕХ банков?",
            reply_markup=keyboard
        )
        context.user_data['reset_all_banks'] = True
    else:
        context.user_data['reset_bank'] = selected_option
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_reset"),
             InlineKeyboardButton("❌ Отмена", callback_data="cancel_reset")]
        ])
        await update.message.reply_text(
            f"⚠️ Вы уверены, что хотите сбросить данные для {selected_option}?",
            reply_markup=keyboard
        )
    return RESET_CONFIRM

async def handle_reset_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_reset":
        await query.edit_message_text("✅ Сброс отменен")
        await query.message.reply_text(
            "📝 Доступные команды:\n\n"
            "/add - добавить новые данные о кэшбэке\n"
            "/reset - сбросить данные для выбранного банка\n"
            "/reset_category - сбросить данные для категории\n"
            "/summary - показать сводку по кэшбэкам\n"
            "/full_reset - сбросить все данные\n"
            "/cancel - отменить текущую операцию"
        )
        context.user_data.pop('reset_bank', None)
        context.user_data.pop('reset_all_banks', None)
        context.user_data.pop('reset_category', None)
        return ConversationHandler.END
        
    if query.data in ["confirm_reset", "confirm_reset_all", "confirm_reset_cat", "confirm_reset_cat_all"]:
        if context.user_data.get('reset_all_banks'):
            session = Session()
            try:
                deleted = session.query(CashbackRecord).filter(
                    CashbackRecord.user_id == update.effective_user.id
                ).delete()
                session.commit()
                await query.edit_message_text("♻️ Данные для всех банков сброшены!")
                await query.message.reply_text(
                    "📝 Доступные команды:\n\n"
                    "/add - добавить новые данные о кэшбэке\n"
                    "/reset - сбросить данные для выбранного банка\n"
                    "/summary - показать сводку по кэшбэкам\n"
                    "/full_reset - сбросить все данные\n"
                    "/cancel - отменить текущую операцию"
                )
            finally:
                session.close()
        elif query.data == "confirm_reset_cat_all":
            session = Session()
            try:
                deleted = session.query(CashbackRecord).filter(
                    CashbackRecord.user_id == update.effective_user.id
                ).delete()
                session.commit()
                await query.edit_message_text("♻️ Данные для всех категорий сброшены!")
            finally:
                session.close()
        elif query.data == "confirm_reset_cat":
            category = context.user_data.get('reset_category')
            session = Session()
            try:
                session.query(CashbackRecord).filter(
                    CashbackRecord.user_id == update.effective_user.id,
                    CashbackRecord.category == category
                ).delete()
                session.commit()
                await query.edit_message_text(f"♻️ Данные для категории {category} сброшены!")
            finally:
                session.close()
    
    # Очищаем данные сессии
    context.user_data.pop('reset_bank', None)
    context.user_data.pop('reset_all_banks', None)
    return ConversationHandler.END

async def save_cashback_data(user_id: int, data: dict):
    session = Session()
    try:
        # Проверяем существующую запись
        record = session.query(CashbackRecord).filter(
            CashbackRecord.user_id == user_id,
            CashbackRecord.bank_name == data['bank'],
            CashbackRecord.category == data['category']
        ).first()

        if record:
            record.percentage = data['cashback']
        else:
            new_record = CashbackRecord(
                user_id=user_id,
                bank_name=data['bank'],
                category=data['category'],
                percentage=data['cashback']
            )
            session.add(new_record)
        
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

async def handle_full_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = Session()
    try:
        deleted_count = session.query(CashbackRecord).filter(
            CashbackRecord.user_id == update.effective_user.id
        ).delete()
        session.commit()
        await update.message.reply_text("♻️ Вся статистика успешно сброшена!" if deleted_count else "📭 Нет данных для сброса")
        await update.message.reply_text(
            "📝 Доступные команды:\n\n"
            "/add - добавить новые данные о кэшбэке\n"
            "/reset - сбросить данные для выбранного банка\n"
            "/summary - показать сводку по кэшбэкам\n"
            "/full_reset - сбросить все данные\n"
            "/cancel - отменить текущую операцию"
        )
    except Exception as e:
        session.rollback()
        await update.message.reply_text("❌ Ошибка при сбросе данных")
    finally:
        session.close()
    return ConversationHandler.END

async def handle_custom_bank_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    custom_bank = update.message.text.strip()
    if len(custom_bank) > 30:
        await update.message.reply_text("❌ Название банка слишком длинное (макс 30 символов)")
        return BANK_INPUT
    
    context.user_data['current_bank'] = custom_bank
    return await show_category_selection(update.message, context)

def get_category_emoji(category):
    emoji_map = {
        "АЗС": "⛽️",
        "Продукты": "🛒",
        "Рестораны": "🍽️",
        "Аптеки": "💊",
        "Транспорт": "🚌",
        "Маркетплейсы": "🛍️",
        "Развлечения": "🎮",
        "Другое": "📦"
    }
    return emoji_map.get(category, "📋")

async def handle_custom_category_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    custom_category = update.message.text.strip()
    if len(custom_category) > 30:
        await update.message.reply_text("❌ Название категории слишком длинное (макс 30 символов)")
        return CATEGORY_INPUT
    
    context.user_data['current_category'] = custom_category
    await update.message.reply_text(f"💵 Введите процент кэшбэка для {custom_category}:")
    return PERCENTAGE_INPUT

async def start_reset_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message if update.message else update.callback_query.message
    session = Session()
    try:
        categories = session.query(CashbackRecord.category).filter(
            CashbackRecord.user_id == update.effective_user.id,
            CashbackRecord.is_active == True
        ).distinct().all()
        categories = [cat[0] for cat in categories]
        if categories:
            keyboard = [
                [InlineKeyboardButton(cat, callback_data=f"reset_cat_{cat}")]
                for cat in categories
            ]
            keyboard.append([InlineKeyboardButton("🗑️ Сбросить все категории", callback_data="reset_cat_all")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await message.reply_text(
                "📋 Выберите категорию для сброса:",
                reply_markup=reply_markup
            )
        else:
            await message.reply_text("📭 Нет данных для сброса")
            await message.reply_text(
                "📝 Доступные команды:\n\n"
                "/add - добавить новые данные о кэшбэке\n"
                "/reset - сбросить данные для выбранного банка\n"
                "/reset_category - сбросить данные для категории\n"
                "/summary - показать сводку по кэшбэкам\n"
                "/full_reset - сбросить все данные\n"
                "/cancel - отменить текущую операцию"
            )
    finally:
        session.close()
    return ConversationHandler.END if not categories else RESET_CATEGORY_SELECTION

async def handle_reset_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    category = query.data.replace("reset_cat_", "")
    if category == "all":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_reset_cat_all"),
             InlineKeyboardButton("❌ Отмена", callback_data="cancel_reset")]
        ])
        await query.edit_message_text(
            "⚠️ Вы уверены, что хотите сбросить данные для ВСЕХ категорий?",
            reply_markup=keyboard
        )
    else:
        context.user_data['reset_category'] = category
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_reset_cat"),
             InlineKeyboardButton("❌ Отмена", callback_data="cancel_reset")]
        ])
        await query.edit_message_text(
            f"⚠️ Вы уверены, что хотите сбросить данные для категории {category}?",
            reply_markup=keyboard
        )
    return RESET_CONFIRM

# Остальные функции остаются без изменений