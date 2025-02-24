# Рекомендуется установить библиотеку:
# !pip install -q pyTelegramBotAPI

import os
import tempfile
import sqlite3
from datetime import datetime
from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

import telebot
from telebot import types

# Импортируем компоненты LLM (код объединён в один файл)
from langchain_gigachat.chat_models import GigaChat
from langchain.output_parsers import PydanticOutputParser
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, Field
import re, json

# Инициализация LLM
llm = GigaChat(
    credentials=os.environ["GIGACHAT_CREDENTIALS"],
    temperature=0.1,
    verify_ssl_certs=False,
    timeout=6000,
    model="GigaChat-Max"
)

class CashbackCategory(BaseModel):
    category: str = Field(..., description="Название категории")
    amount: float = Field(..., description="Процент кешбэка")

class CashbackResponse(BaseModel):
    categories: list[CashbackCategory] = Field(..., description="Список категорий с кешбэком")

class RobustParser(PydanticOutputParser):
    def parse(self, text: str) -> CashbackResponse:
        try:
            text = text.replace("'", '"').replace("\\", "")
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if not json_match:
                raise ValueError("Не найден JSON в ответе")
            json_str = json_match.group()
            data = json.loads(json_str)
            if "cashbacks" in data and "categories" not in data:
                data["categories"] = data.pop("cashbacks")
            return CashbackResponse(**data)
        except Exception as e:
            return CashbackResponse(categories=[])

parser = RobustParser(pydantic_object=CashbackResponse)

def _get_messages_from_url(url: str):
    return {
        "history": [
            HumanMessage(content="", additional_kwargs={"attachments": [url]}),
        ]
    }

prompt = ChatPromptTemplate.from_messages(
    [
        SystemMessage(
            content="Проанализируй изображение и выдели все категории кешбэка. Ответь строго в JSON формате.\n\n"
                    "Пример ответа:\n"
                    "{\"categories\": ["
                    "{\"category\": \"рестораны\", \"amount\": 5}, "
                    "{\"category\": \"аптеки\", \"amount\": 3}"
                    "]}\n\n"
                    "Используй только указанные названия полей!"
        ),
        MessagesPlaceholder("history"),
    ]
)

chain = (
    RunnableLambda(_get_messages_from_url)
    | prompt
    | llm
    | RunnableLambda(lambda x: x.content)
    | parser
)

# Инициализация базы данных SQLite
conn = sqlite3.connect("cashback.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS cashback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    bank TEXT,
    category TEXT,
    amount REAL,
    input_type TEXT,
    created_at TEXT
)
""")
conn.commit()

def save_cashback(user_id: int, bank: str, category: str, amount: float, input_type: str):
    cursor.execute("INSERT INTO cashback (user_id, bank, category, amount, input_type, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                   (user_id, bank, category, amount, input_type, datetime.now().strftime("%d.%m.%Y %H:%M")))
    conn.commit()

def get_summary(user_id: int):
    cursor.execute("SELECT bank, category, amount FROM cashback WHERE user_id=?", (user_id,))
    rows = cursor.fetchall()
    # Группируем данные по категории
    summary = {}
    for bank, category, amount in rows:
        if category not in summary:
            summary[category] = []
        summary[category].append((bank, amount))
    # Формирование текста сводки
    text_lines = ["🏆 Лучшие кэшбэки по категориям:"]
    for cat, entries in summary.items():
        text_lines.append(f"\n📋 {cat}")
        # Сортировка по величине кешбэка (убывание)
        entries.sort(key=lambda x: x[1], reverse=True)
        medals = ["🥇", "🥈", "🥉"]
        for idx, (bank, amount) in enumerate(entries[:3]):
            medal = medals[idx] if idx < len(medals) else ""
            text_lines.append(f"└ {medal} {bank}: {int(amount)}%")
    text_lines.append(f"\n📅 Актуально на: {datetime.now().strftime('%d.%м.%Y %H:%M')}")
    return "\n".join(text_lines)

def reset_data_for_bank(user_id: int, bank: str):
    cursor.execute("DELETE FROM cashback WHERE user_id=? AND bank=?", (user_id, bank))
    conn.commit()

# Глобальная сессия для хранения промежуточных данных пользователя
sessions = {}

# Инициализация Telegram-бота через pyTelegramBotAPI
bot = telebot.TeleBot(os.environ["TELEGRAM_TOKEN"])

# Главная клавиатура с опциями
def main_menu_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("Добавить информацию", "Показать сводку")
    keyboard.row("Сбросить данные")
    return keyboard

# Дополнительная клавиатура для добавления информации
def add_info_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("Выбрать банк")
    keyboard.row("Назад")
    return keyboard

# Клавиатура для выбора категорий
def category_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    categories = ["спорт", "еда", "образование", "кино", "искусство"]
    buttons = [types.InlineKeyboardButton(text=cat.capitalize(), callback_data=f"cat_{cat}") for cat in categories]
    buttons.append(types.InlineKeyboardButton(text="Другой", callback_data="cat_other"))
    keyboard.add(*buttons)
    return keyboard

# Клавиатура для подтверждения сброса данных
def reset_confirm_keyboard(bank: str):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(types.InlineKeyboardButton(text="Подтвердить", callback_data=f"reset_{bank}"),
                 types.InlineKeyboardButton(text="Отмена", callback_data="reset_cancel"))
    return keyboard

# Клавиатура для выбора добавления еще данных для банка
def add_more_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(types.InlineKeyboardButton(text="Добавить ещё", callback_data="add_more"),
                 types.InlineKeyboardButton(text="Главное меню", callback_data="back_main"))
    return keyboard

# Добавляем функцию для клавиатуры выбора способа ввода
def input_method_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("Ручной ввод", "Скриншот")
    keyboard.row("Назад")
    return keyboard

@bot.message_handler(commands=["start"])
def command_start(message):
    sessions[message.from_user.id] = {}  # сброс сессии
    bot.reply_to(message, "Привет! Чем могу помочь? 😊\nВыберите опцию:", reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda m: m.text == "Добавить информацию")
def add_information(message):
    sessions[message.from_user.id] = {}  # Сброс сессии для нового ввода
    # Убираем сообщение "Сначала выберите банк:" – вызываем функцию выбора банка напрямую
    choose_bank(message)

@bot.message_handler(func=lambda m: m.text == "Показать сводку")
def show_summary(message):
    summary = get_summary(message.from_user.id)
    bot.reply_to(message, f"Вот ваша сводка кешбэка: \n{summary}", reply_markup=main_menu_keyboard())

# Добавляем функцию для получения банков пользователя из БД
def get_user_banks(user_id: int):
    cursor.execute("SELECT DISTINCT bank FROM cashback WHERE user_id=?", (user_id,))
    banks = [row[0] for row in cursor.fetchall() if row[0] != "Не выбран"]
    return banks

# Изменяем обработчик для сброса данных: предлагаем только те банки, которые уже введены
@bot.message_handler(func=lambda m: m.text == "Сбросить данные")
def reset_data(message):
    user_id = message.from_user.id
    banks = get_user_banks(user_id)
    if not banks:
        bot.reply_to(message, "У вас ещё нет сохранённых банков.", reply_markup=main_menu_keyboard())
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(text=bank, callback_data=f"resetbank_{bank}") for bank in banks]
    markup.add(*buttons)
    bot.reply_to(message, "Выберите банк для сброса данных:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "Назад")
def back_to_main(message):
    bot.reply_to(message, "Главное меню", reply_markup=main_menu_keyboard())

# Обработчик выбора банка
@bot.message_handler(func=lambda m: m.text == "Выбрать банк")
def choose_bank(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    banks = ["OZON", "Газпромбанк", "Яндекс банк", "ВТБ", "МТС банк", "Тинькофф", "Сбербанк", "Альфа-Банк"]
    buttons = [types.InlineKeyboardButton(text=bank, callback_data=f"bank_{bank}") for bank in banks]
    buttons.append(types.InlineKeyboardButton(text="Другой", callback_data="bank_other"))
    markup.add(*buttons)
    bot.reply_to(message, "Выберите банк:", reply_markup=markup)

# Изменяем callback_bank: после выбора банка показываем выбор способа ввода, а не сразу категорию
@bot.callback_query_handler(func=lambda call: call.data.startswith("bank_"))
def callback_bank(call):
    user_id = call.from_user.id
    bank = call.data.split("_", 1)[1]
    if bank == "other":
        bot.send_message(user_id, "Введите название вашего банка:")
        sessions[user_id]["await_bank"] = True
    else:
        sessions.setdefault(user_id, {})["bank"] = bank
        # Показываем клавиатуру выбора способа ввода
        bot.send_message(user_id, f"Выбран банк: {bank}\nВыберите способ ввода информации:", reply_markup=input_method_keyboard())
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def callback_category(call):
    user_id = call.from_user.id
    cat = call.data.split("_", 1)[1]
    if cat == "other":
        bot.send_message(user_id, "Введите название категории:")
        sessions[user_id]["await_category"] = True
    else:
        sessions.setdefault(user_id, {})["category"] = cat
        bot.send_message(user_id, f"Выбрана категория: {cat}\nВведите величину кешбэка (целое число):")
        sessions[user_id]["stage"] = "await_cashback"
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("resetbank_"))
def callback_reset_bank(call):
    user_id = call.from_user.id
    bank = call.data.split("_", 1)[1]
    msg = f"Вы действительно хотите сбросить данные для банка {bank}?"
    bot.send_message(user_id, msg, reply_markup=reset_confirm_keyboard(bank))
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("reset_"))
def callback_reset_confirm(call):
    user_id = call.from_user.id
    bank = call.data.split("_", 1)[1]
    reset_data_for_bank(user_id, bank)
    bot.send_message(user_id, f"Данные для банка {bank} сброшены.", reply_markup=main_menu_keyboard())
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "reset_cancel")
def callback_reset_cancel(call):
    user_id = call.from_user.id
    bot.send_message(user_id, "Сброс данных отменён.", reply_markup=main_menu_keyboard())
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data in ["add_more", "back_main"])
def callback_add_more(call):
    user_id = call.from_user.id
    if call.data == "add_more":
        bot.send_message(user_id, "Выберите категорию:", reply_markup=category_keyboard())
        sessions[user_id]["stage"] = "choose_category"
    else:
        bot.send_message(user_id, "Главное меню", reply_markup=main_menu_keyboard())
    bot.answer_callback_query(call.id)

# Приём текста для ручного ввода или для ввода названия банка, если выбран вариант "Другой"
@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message):
    user_id = message.from_user.id
    session = sessions.setdefault(user_id, {})
    # Если ожидается название банка
    if session.get("await_bank"):
        session["bank"] = message.text
        session.pop("await_bank")
        bot.reply_to(message, f"👍 Отлично! Выбран банк: {message.text}\nТеперь выберите категорию:", reply_markup=category_keyboard())
    # Если ожидается ввод названия категории (при выборе "Другой" в категории)
    elif session.get("await_category"):
        session["category"] = message.text
        session.pop("await_category")
        bot.reply_to(message, f"👍 Категория \"{message.text}\" принята!\nВведите величину кешбэка (целое число):")
        session["stage"] = "await_cashback"
    # Если ожидается ввод величины кешбэка
    elif session.get("stage") == "await_cashback":
        try:
            amount = int(message.text.strip())
            bank = session.get("bank", "Не выбран")
            category = session.get("category", "Не выбрана")
            save_cashback(user_id, bank, category, amount, input_type="manual")
            bot.reply_to(message, f"✅ Успешно сохранено: {category} – {amount}% для банка {bank}!", reply_markup=add_more_keyboard())
            session.pop("stage")
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка: введите, пожалуйста, целое число для кешбэка. ({e})")
    # Обработка команды "скриншот"
    elif message.text.lower() == "скриншот":
        bot.reply_to(message, "Пожалуйста, отправьте скриншот с информацией о кешбэке. 📷", reply_markup=input_method_keyboard())
    else:
        bot.reply_to(message, "🤔 Неизвестная команда. Пожалуйста, используйте меню ниже.", reply_markup=main_menu_keyboard())

# Обработчик фото для автоматического распознавания через LLM
@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    user_id = message.from_user.id
    try:
        # Берём файл фото (наилучшего качества) 📸
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        tmp_path = tmp_file.name
        tmp_file.close()
        downloaded_file = bot.download_file(file_info.file_path)
        with open(tmp_path, "wb") as new_file:
            new_file.write(downloaded_file)
        # Отправляем фото в LLM для обработки 🤖
        with open(tmp_path, "rb") as f:
            uploaded_file = llm.upload_file(f)
        result = chain.batch([uploaded_file.id_])
        if result and result[0].categories:  # исправлено синтаксическое условие
            bank = sessions.get(user_id, {}).get("bank", "Не выбран")
            for cat in result[0].categories:
                save_cashback(user_id, bank, cat.category, int(cat.amount), input_type="screenshot")
            response_text = "\n".join(f"{cat.category.capitalize()}: {int(cat.amount)}% 💰" for cat in result[0].categories)
        else:
            response_text = "🙁 К сожалению, не удалось определить кешбэк из изображения."
        bot.reply_to(message, f"Отлично! Вот что я нашёл:\n{response_text}", reply_markup=add_info_keyboard())
    except Exception as e:
        bot.reply_to(message, f"❌ Ой, произошла ошибка при обработке изображения. Попробуйте ввести данные вручную! ({e})")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    bot.polling(none_stop=True)
