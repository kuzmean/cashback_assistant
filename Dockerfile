FROM python:3.10-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY . .

# Создание директории для базы данных
RUN mkdir -p /app/data

# Настройка переменных окружения
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:///data/cashback.db

# Запуск приложения
CMD ["python", "telegram_bot.py"] 