# API Документация

## GigaChat API

### Авторизация
```python
credentials = os.environ["GIGACHAT_CREDENTIALS"]
llm = GigaChat(
    credentials=credentials,
    temperature=0.1,
    verify_ssl_certs=False,
    timeout=6000,
    model="GigaChat-Max"
)
```

### Загрузка файла
```python
with open(file_path, "rb") as f:
    uploaded_file = llm.upload_file(f)
```

### Формирование запроса
```python
messages = [
    SystemMessage(
        content="Проанализируй изображение и выдели все категории кешбэка..."
    ),
    HumanMessage(
        content=[{"type": "file", "file_id": uploaded_file.id_}]
    )
]
```

### Отправка запроса
```python
response = llm(messages)
content = response.content
```

### Обработка ответа
```python
try:
    data = json.loads(content)
    # Дальнейшая обработка структурированных данных
except json.JSONDecodeError:
    # Обработка ошибки парсинга JSON
```

## Telegram Bot API

### Инициализация бота
```python
bot = telebot.TeleBot(os.environ["TELEGRAM_TOKEN"])
```

### Обработчики сообщений
```python
@bot.message_handler(commands=["start"])
def start_command(message):
    # Обработка команды /start
    
@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    # Обработка фотографий
    
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    # Обработка callback-запросов
```

### Клавиатуры
```python
# Обычная клавиатура
keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.row("Кнопка 1", "Кнопка 2")

# Inline-клавиатура
markup = types.InlineKeyboardMarkup(row_width=2)
markup.add(
    types.InlineKeyboardButton(text="Да", callback_data="yes"),
    types.InlineKeyboardButton(text="Нет", callback_data="no")
)
```

### Отправка сообщений
```python
bot.send_message(user_id, text, reply_markup=keyboard)
bot.reply_to(message, text, reply_markup=keyboard)
```

## База данных SQLite

### Подключение
```python
conn = sqlite3.connect("cashback.db", check_same_thread=False)
cursor = conn.cursor()
```

### Создание таблицы
```python
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
```

### Вставка данных
```python
cursor.execute(
    "INSERT INTO cashback VALUES (?, ?, ?, ?, ?, ?)",
    (user_id, bank, category, amount, input_type, datetime.now().strftime("%d.%m.%Y %H:%M"))
)
conn.commit()
```

### Чтение данных
```python
cursor.execute("SELECT bank, category, amount FROM cashback WHERE user_id=?", (user_id,))
rows = cursor.fetchall()
```

### Удаление данных
```python
cursor.execute("DELETE FROM cashback WHERE user_id=? AND bank=?", (user_id, bank))
conn.commit()
``` 