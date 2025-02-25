# Руководство по установке

## Системные требования

- Python 3.10 или выше
- Примерно 100 МБ свободного места на диске
- Интернет-соединение для работы с API

## Пошаговая установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/kuzmean/cashback-analyzer-bot.git
cd cashback-analyzer-bot
```

### 2. Создание виртуального окружения

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Получение API ключей

#### Telegram Bot API
1. Откройте https://t.me/BotFather
2. Отправьте команду `/newbot`
3. Следуйте инструкциям для создания нового бота
4. Получите API токен бота

#### GigaChat API
1. Зарегистрируйтесь на платформе GigaChat
2. Создайте новый API ключ
3. Скопируйте учетные данные (credentials)

### 5. Настройка окружения

1. Скопируйте файл .env.example:
```bash
cp .env.example .env
```

2. Отредактируйте файл .env, вставив свои API ключи:
```
TELEGRAM_TOKEN=your_telegram_bot_token
GIGACHAT_CREDENTIALS=your_gigachat_credentials
DATABASE_URL=sqlite:///cashback.db
```

### 6. Запуск бота

```bash
python telegram_bot.py
```

## Проверка работоспособности

1. Откройте созданный бот в Telegram
2. Отправьте команду `/start`
3. Получите приветственное сообщение
4. Попробуйте отправить скриншот с информацией о кэшбэке

## Запуск в фоновом режиме

### Linux/macOS

```bash
nohup python telegram_bot.py > bot.log 2>&1 &
```

### Windows

Создайте файл `start_bot.bat` со следующим содержимым:
```batch
@echo off
call venv\Scripts\activate
python telegram_bot.py
```

## Устранение неполадок

### Бот не отвечает
- Проверьте правильность токена в .env
- Убедитесь, что бот запущен
- Проверьте логи на наличие ошибок

### Ошибки распознавания
- Убедитесь в правильности учетных данных GigaChat
- Проверьте качество загружаемых изображений
- Убедитесь, что на изображении действительно есть информация о кэшбэке

### Проблемы с базой данных
- Проверьте права доступа к папке с базой данных
- Убедитесь, что у процесса достаточно прав для записи

## Обновление

Для обновления бота до последней версии:

```bash
git pull
pip install -r requirements.txt
``` 