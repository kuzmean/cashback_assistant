from telebot import types
from .config import CATEGORY_EMOJIS, DEFAULT_CATEGORY_EMOJI, DEFAULT_CATEGORIES
from .database import get_user_categories, get_user_banks

def main_menu_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("➕ Добавить информацию", "🔄 Сбросить данные")
    keyboard.row("📊 Показать сводку")
    return keyboard

def add_info_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("Выбрать банк")
    keyboard.row("Назад")
    return keyboard

def input_method_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("Ручной ввод", "Скриншот")
    keyboard.row("Назад")
    return keyboard

def bank_keyboard(user_id: int):
    markup = types.InlineKeyboardMarkup(row_width=3)
    default_banks = ["Тинькофф", "Альфа-Банк", "Сбербанк", "ВТБ", "OZON", "Газпромбанк"]
    user_banks = get_user_banks(user_id)
    all_banks = list(set(default_banks + user_banks))
    
    buttons = []
    for bank in all_banks:
        buttons.append(types.InlineKeyboardButton(text=bank, callback_data=f"bank_{bank}"))
    
    buttons.append(types.InlineKeyboardButton(text="Другой", callback_data="bank_other"))
    markup.add(*buttons)
    return markup

def category_keyboard(user_id: int):
    default_cats = DEFAULT_CATEGORIES.copy()
    user_cats = get_user_categories(user_id)
    all_cats = list(set(default_cats + user_cats))
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    for cat in all_cats:
        if cat in default_cats:
            text = cat.capitalize()
        else:
            text = f"{CATEGORY_EMOJIS.get(cat, DEFAULT_CATEGORY_EMOJI)} {cat.capitalize()}"
        buttons.append(types.InlineKeyboardButton(text=text.strip(), callback_data=f"cat_{cat}"))
    
    buttons.append(types.InlineKeyboardButton(text="Другой", callback_data="cat_other"))
    markup.add(*buttons)
    return markup

def reset_confirm_keyboard(bank: str):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(text="Подтвердить ✅", callback_data=f"reset_{bank}"),
        types.InlineKeyboardButton(text="Отмена ❌", callback_data="reset_cancel")
    )
    return keyboard

def full_reset_confirm_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(text="Подтвердить ✅", callback_data="reset_all_confirm"),
        types.InlineKeyboardButton(text="Отмена ❌", callback_data="reset_cancel")
    )
    return keyboard

def add_more_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(text="Добавить ещё", callback_data="add_more"),
        types.InlineKeyboardButton(text="Главное меню", callback_data="back_main")
    )
    return keyboard

def screenshot_confirm_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(text="Сохранить ✅", callback_data="confirm_screenshot"),
        types.InlineKeyboardButton(text="Отмена ❌", callback_data="cancel_screenshot")
    )
    return keyboard 