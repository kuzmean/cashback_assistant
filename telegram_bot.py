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

# Обновлённая функция форматирования сводки с эмодзи
def get_summary(user_id):
    rows = cursor.execute("SELECT bank, category, amount FROM cashback WHERE user_id=?", (user_id,)).fetchall()
    summary = {}
    
    for bank, category, amount in rows:
        if category not in summary:
            summary[category] = []
        summary[category].append((bank, amount))
    
    text_lines = ["🏆 Лучшие кэшбэки по категориям:"]
    
    # Сортируем категории в алфавитном порядке
    for cat in sorted(summary.keys(), key=str.lower):
        entries = summary[cat]
        # Добавляем эмодзи, если категория есть в словаре (с учетом нижнего регистра)
        if cat.lower() in category_emojis:
            cat_label = f"{category_emojis[cat.lower()]} {cat.capitalize()}"
        else:
            cat_label = f"{default_category_emoji} {cat.capitalize()}"
        text_lines.append(f"\n {cat_label}")
        
        # Сортируем по размеру кэшбэка и добавляем медали
        entries.sort(key=lambda x: x[1], reverse=True)
        medals = ["🥇", "🥈", "🥉"]
        
        for idx, (bank, amount) in enumerate(entries[:3]):
            medal = medals[idx] if idx < len(medals) else ""
            # Выделяем жирным первый (лучший) вариант
            if idx == 0:
                text_lines.append(f"└ {medal} *{bank}: {int(amount)}%*")
            else:
                text_lines.append(f"└ {medal} {bank}: {int(amount)}%")
    
    text_lines.append(f"\n📅 Актуально на: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(text_lines)

def reset_data_for_bank(user_id: int, bank: str):
    cursor.execute("DELETE FROM cashback WHERE user_id=? AND bank=?", (user_id, bank))
    conn.commit()

# Глобальная сессия для хранения промежуточных данных пользователя
sessions = {}

# Инициализация Telegram-бота через pyTelegramBotAPI
bot = telebot.TeleBot(os.environ["TELEGRAM_TOKEN"])

# Обновлённая основная клавиатура с эмодзи
def main_menu_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # Первая строка – добавить информацию и показать сводку
    keyboard.row("➕ Добавить информацию", "🔄 Сбросить данные")
    # Вторая строка – сброс по банкам и полный сброс статистики
    keyboard.row("📊 Показать сводку")
    return keyboard

# Дополнительная клавиатура для добавления информации
def add_info_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("Выбрать банк")
    keyboard.row("Назад")
    return keyboard

# Обновлённый словарь стандартных категорий и их эмодзи
default_categories = ["одежда", "продукты", "рестораны", "образование", "техника", "такси"]
category_emojis = {
    # Транспорт и авто
    "авто": "🚗",
    "автозапчасти": "🔧",
    "автоуслуги": "🛠️",
    "топливо": "⛽",
    "топливо и азс": "⛽",
    "такси": "🚖",
    "транспорт": "🚇",
    "аренда авто": "🚙",
    "покупка авто": "🏎️",
    
    # Еда и напитки
    "продукты": "🛒",
    "супермаркеты": "🏪",
    "кафе и рестораны": "🍽️",
    "рестораны": "🍽️",
    "кафе": "🍽️",
    "фастфуд": "🍔",
    "алкоголь": "🍷",
    "доставка еды": "🛵",
    
    # Здоровье
    "аптеки": "💊",
    "медицинские услуги": "🏥",
    "товары для здоровья": "🩺",
    "красота": "💄",
    
    # Образование и хобби
    "образование": "🎓",
    "хобби": "🧩",
    "культура и искусство": "🎭",
    "спортивные товары": "🏋️",
    "активный отдых": "🎢",
    "спорт": "🏋️",
    "спорттовары": "🏋️",
    "кино": "🎬",
    "кинотеатры": "🎬",

    
    # Техника и связь
    "техника": "📱",
    "связь, интернет и тв": "📡",
    "цифровые товары": "💻",
    
    # Дом и быт
    "дом и ремонт": "🏡",
    "мебель": "🪑",
    "цветы": "��",
    # Шопинг
    "одежда и обувь": "👠",
    "детские товары": "🧸",
    "ювелирные изделия": "��",
    "маркетплейсы": "📦",

    
    # Специфические сервисы
    "сервис тревел": "✈️",
    "сервис заправки": "⛽",
    "сервис маркет": "🛍️",
    "сервис афиша": "🎟️",
    "через alfa pay": "📲",  # "Alfa Pay" оставлен с заглавными, так как это бренд
    
    # Животные
    "животные": "🐾",
}
default_category_emoji = "📋"

# Функция для получения дополнительных категорий из БД для данного пользователя
def get_user_categories(user_id: int):
    cursor.execute("SELECT DISTINCT category FROM cashback WHERE user_id=?", (user_id,))
    cats = [row[0] for row in cursor.fetchall()]
    # Вернуть те, которых нет в default_categories
    return list(set(c for c in cats if c not in default_categories))

# Добавляем функцию для формирования клавиатуры банков с учётом введённых пользователем
def bank_keyboard(user_id: int):
    default_banks = ["OZON", "Газпромбанк", "Яндекс банк", "ВТБ", "МТС банк", "Тинькофф", "Сбербанк", "Альфа-Банк"]
    user_banks = get_user_banks(user_id)
    # Объединяем списки и удаляем дубликаты
    banks = list(set(default_banks + user_banks))
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(text=bank, callback_data=f"bank_{bank}") for bank in banks]
    buttons.append(types.InlineKeyboardButton(text="Другой", callback_data="bank_other"))
    markup.add(*buttons)
    return markup

# Обновлённая функция category_keyboard с учетом пользовательских категорий и дефолтного эмодзи
def category_keyboard(user_id: int):
    default_cats = ["одежда", "продукты", "рестораны", "образование", "техника", "такси"]
    cursor.execute("SELECT DISTINCT category FROM cashback WHERE user_id=?", (user_id,))
    user_cats = [row[0] for row in cursor.fetchall()]
    all_cats = list(set(default_cats + user_cats))
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    for cat in all_cats:
        text = cat.capitalize()
        buttons.append(types.InlineKeyboardButton(text=text, callback_data=f"cat_{cat}"))
    
    buttons.append(types.InlineKeyboardButton(text="Другой", callback_data="cat_other"))
    markup.add(*buttons)
    return markup

# Обновлённая клавиатура для подтверждения сброса данных с эмодзи
def reset_confirm_keyboard(bank: str):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(text="Подтвердить ✅", callback_data=f"reset_{bank}"),
        types.InlineKeyboardButton(text="Отмена ❌", callback_data="reset_cancel")
    )
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
    keyboard.row("✍️ Ручной ввод", "📸 Скриншот")
    keyboard.row("🔙 Назад")
    return keyboard

# Обновлённое приветствие при вызове команды /start
@bot.message_handler(commands=["start"])
def command_start(message):
    sessions[message.from_user.id] = {}  # сброс сессии
    welcome_text = (
        "Welcome to Cashback Assistant! 🤑\n\n"
        "Я помогу вам отслеживать лучшие предложения и сохранять информацию о кешбэке.\n"
        "Выберите, что хотите сделать:"
    )
    bot.reply_to(message, welcome_text, reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda m: "добавить информацию" in m.text.lower())
def add_information(message):
    sessions[message.from_user.id] = {}  # Сброс сессии для нового ввода
    choose_bank(message)

@bot.message_handler(func=lambda m: "показать сводку" in m.text.lower())
def show_summary(message):
    summary = get_summary(message.from_user.id)
    bot.reply_to(message, f"\n{summary}", reply_markup=main_menu_keyboard(), parse_mode="Markdown")
    offer_msg = (
        "💳 Чтобы увеличить вашу выгоду, оформите карту:\n"
        "Альфа-банк: https://alfa.me/xGH5KO\n"
        "Т-банк: https://www.tbank.ru/baf/4HLAiOHJMyt"
    )
    bot.send_message(message.from_user.id, offer_msg, reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda m: "сбросить данные" in m.text.lower())
def reset_data(message):
    user_id = message.from_user.id
    banks = get_user_banks(user_id)
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    # Если есть сохранённые банки, добавить их кнопки
    if banks:
        buttons = [types.InlineKeyboardButton(text=bank, callback_data=f"resetbank_{bank}") for bank in banks]
        keyboard.add(*buttons)
    # Всегда добавляем кнопку для полного сброса
    keyboard.add(types.InlineKeyboardButton(text="Полный сброс статистики", callback_data="reset_all"))
    bot.reply_to(message, "Выберите сброс: для отдельного банка или полный сброс статистики:", reply_markup=keyboard)

@bot.message_handler(func=lambda m: "назад" in m.text.lower())
def back_to_main(message):
    bot.reply_to(message, "Главное меню", reply_markup=main_menu_keyboard())

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

@bot.message_handler(func=lambda m: "ручной ввод" in m.text.lower())
def manual_input(message):
    user_id = message.from_user.id
    # Если у пользователя уже выбран банк, показываем клавиатуру категорий
    if user_id in sessions and "bank" in sessions[user_id]:
        bank = sessions[user_id]["bank"]
        markup = category_keyboard(user_id)
        bot.send_message(user_id, f"Выбран банк: {bank}\nВыберите категорию:", reply_markup=markup)
    else:
        bot.send_message(user_id, "Сначала выберите банк", reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda m: "скриншот" in m.text.lower())
def screenshot_input(message):
    user_id = message.from_user.id
    if user_id in sessions and "bank" in sessions[user_id]:
        bank = sessions[user_id]["bank"]
        bot.send_message(user_id, f"Выбран банк: {bank}\nОтправьте скриншот с информацией о кешбэке:")
    else:
        bot.send_message(user_id, "Сначала выберите банк", reply_markup=main_menu_keyboard())

# Обработчик выбора банка
@bot.message_handler(func=lambda m: m.text == "Выбрать банк")
def choose_bank(message):
    user_id = message.from_user.id
    markup = bank_keyboard(user_id)
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

# В callback для выбора категории – передаем user_id в category_keyboard
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

@bot.callback_query_handler(func=lambda call: call.data == "reset_all")
def callback_reset_all(call):
    user_id = call.from_user.id
    bot.send_message(user_id, "Вы действительно хотите полностью сбросить всю статистику?", reply_markup=full_reset_confirm_keyboard())
    bot.answer_callback_query(call.id)

# Обработчик для подтверждения полного сброса
@bot.callback_query_handler(func=lambda call: call.data == "reset_all_confirm")
def callback_reset_all_confirm(call):
    user_id = call.from_user.id
    cursor.execute("DELETE FROM cashback WHERE user_id=?", (user_id,))
    conn.commit()
    bot.send_message(user_id, "✅ Полный сброс статистики выполнен.", reply_markup=main_menu_keyboard())
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "reset_cancel")
def callback_reset_cancel(call):
    user_id = call.from_user.id
    bot.send_message(user_id, "Сброс данных отменён.", reply_markup=main_menu_keyboard())
    bot.answer_callback_query(call.id)

# При вызове клавиатуры категорий в callback_add_more и handle_text передаем user_id
@bot.callback_query_handler(func=lambda call: call.data in ["add_more", "back_main"])
def callback_add_more(call):
    user_id = call.from_user.id
    if call.data == "add_more":
        bot.send_message(user_id, "Выберите категорию:", reply_markup=category_keyboard(user_id))
        sessions[user_id]["stage"] = "choose_category"
    else:
        bot.send_message(user_id, "Главное меню", reply_markup=main_menu_keyboard())
    bot.answer_callback_query(call.id)

# Приём текста для ручного ввода или для ввода названия банка, если выбран вариант "Другой"
@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message):
    # Если сообщение начинается с '/', не обрабатываем его здесь
    if message.text.startswith('/'):
        return
    user_id = message.from_user.id
    session = sessions.setdefault(user_id, {})
    # Если ожидается название банка (в том числе "Другой")
    if session.get("await_bank"):
        session["bank"] = message.text
        session.pop("await_bank")
        # Изменено: предлагаем выбор способа ввода, а не сразу категории
        bot.reply_to(message, f"👍 Отлично! Выбран банк: {message.text}\nВыберите способ ввода информации:", reply_markup=input_method_keyboard())
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
    # Если выбрана команда "скриншот"
    elif message.text.lower() == "скриншот":
        bot.reply_to(message, "Пожалуйста, отправьте скриншот с информацией о кешбэке. 📷", reply_markup=input_method_keyboard())
    # Добавляем новую ветку для "ручной ввод"
    elif message.text.lower() == "ручной ввод":
        bot.reply_to(message, "Пожалуйста, выберите категорию для ручного ввода:", reply_markup=category_keyboard(user_id))
    else:
        bot.reply_to(message, "🤔 Неизвестная команда. Пожалуйста, используйте меню ниже.", reply_markup=main_menu_keyboard())

# Добавляем inline-клавиатуру для подтверждения результата скриншота
def screenshot_confirm_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(text="Подтвердить ✅", callback_data="confirm_screenshot"),
        types.InlineKeyboardButton(text="Отмена ❌", callback_data="cancel_screenshot")
    )
    return markup

# Изменяем обработчик фото: сохраняем результат во временную сессию и запрашиваем подтверждение
@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    user_id = message.from_user.id
    try:
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        tmp_path = tmp_file.name
        tmp_file.close()
        downloaded_file = bot.download_file(file_info.file_path)
        with open(tmp_path, "wb") as new_file:
            new_file.write(downloaded_file)
        with open(tmp_path, "rb") as f:
            uploaded_file = llm.upload_file(f)
        result = chain.batch([uploaded_file.id_])
        if result and result[0].categories:
            # Сохраняем результат во временную сессию
            sessions[user_id]["screenshot"] = result[0].categories
            response = "\n".join(f"{cat.category.capitalize()}: {int(cat.amount)}% 💰" for cat in result[0].categories)
            # Запрашиваем подтверждение
            bot.reply_to(message,
                         f"Я распознал следующие кешбэк категории:\n{response}\nПодтвердите, чтобы сохранить данные:",
                         reply_markup=screenshot_confirm_keyboard())
        else:
            bot.reply_to(message, "🙁 Не удалось распознать кешбэк. Попробуйте ввести данные вручную.",
                         reply_markup=input_method_keyboard())
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при обработке изображения. Попробуйте ввести данные вручную! ({e})")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# Обработчики inline для подтверждения / отмены сохранения результата скриншота
@bot.callback_query_handler(func=lambda call: call.data == "confirm_screenshot")
def confirm_screenshot(call):
    user_id = call.from_user.id
    categories = sessions.get(user_id, {}).get("screenshot")
    bank = sessions.get(user_id, {}).get("bank", "Не выбран")
    if categories:
        for cat in categories:
            save_cashback(user_id, bank, cat.category, int(cat.amount), input_type="screenshot")
        response = "\n".join(f"{cat.category.capitalize()}: {int(cat.amount)}% 💰" for cat in categories)
        bot.send_message(user_id, f"✅ Сохранено:\n{response}", reply_markup=main_menu_keyboard())
        sessions[user_id].pop("screenshot", None)
    else:
        bot.send_message(user_id, "❌ Нет данных для сохранения.", reply_markup=main_menu_keyboard())
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_screenshot")
def cancel_screenshot(call):
    user_id = call.from_user.id
    sessions[user_id].pop("screenshot", None)
    bot.send_message(user_id, "Отменено. Вы можете попробовать ввести данные вручную.", reply_markup=input_method_keyboard())
    bot.answer_callback_query(call.id)

# Новая inline-клавиатура для подтверждения полного сброса
def full_reset_confirm_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(text="Подтвердить ✅", callback_data="reset_all_confirm"),
        types.InlineKeyboardButton(text="Отмена ❌", callback_data="reset_cancel")
    )
    return keyboard

@bot.message_handler(commands=["offer"])
def card_links(message):
    links_text = (
        "💳 Оформление карт:\n"
        "Альфа-банк: https://alfa.me/xGH5KO\n"
        "Т-банк: https://www.tbank.ru/baf/4HLAiOHJMyt"
    )
    bot.reply_to(message, links_text, reply_markup=main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("reset_") and call.data not in ["reset_all", "reset_all_confirm", "reset_cancel"])
def callback_reset_bank_confirm(call):
    user_id = call.from_user.id
    bank = call.data.split("_", 1)[1]
    reset_data_for_bank(user_id, bank)
    bot.send_message(user_id, f"Данные для банка {bank} сброшены.", reply_markup=main_menu_keyboard())
    bot.answer_callback_query(call.id)

if __name__ == "__main__":
    bot.polling(none_stop=True)
