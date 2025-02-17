from telegram import InlineKeyboardButton, InlineKeyboardMarkup

async def get_action_keyboard():
    """Возвращает стандартную клавиатуру действий"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить данные", callback_data="next_bank")],
        [InlineKeyboardButton("🗑️ Сбросить статистику", callback_data="command_reset")],
        [InlineKeyboardButton("📊 Показать сводку", callback_data="command_summary")]
    ]) 