# Архитектура Cashback Analyzer Bot

## Компоненты системы

### 1. Telegram Bot API Client
Компонент, отвечающий за взаимодействие с Telegram API.
- Обработка входящих сообщений и команд
- Отправка ответов пользователю
- Управление интерактивными элементами (кнопки, клавиатуры)

### 2. Session Manager
Управление состояниями пользователей и их сессиями.
- Хранение текущего контекста взаимодействия
- Отслеживание пользовательского прогресса по сценариям использования
- Управление таймаутами и очисткой неактивных сессий

### 3. LangChain Integration
Компонент для интеграции с LangChain и GigaChat API.
- Подготовка и отправка запросов к GigaChat
- Обработка и парсинг ответов
- Структурирование данных с помощью моделей Pydantic

### 4. Storage Layer
Слой хранения данных на основе SQLite.
- Сохранение информации о кэшбэке
- Хранение пользовательских настроек
- Обеспечение персистентности данных между запусками

### 5. Image Processing
Обработка изображений, загруженных пользователями.
- Временное сохранение файлов
- Конвертация и оптимизация изображений
- Подготовка изображений для отправки в API

### 6. Response Formatter
Форматирование ответов для пользователя.
- Структурирование и форматирование текста
- Добавление эмодзи и визуальных элементов
- Подготовка удобных для восприятия отчетов

## Диаграмма потока данных

```
User Request → Telegram Bot → Session Manager → Action Handler → [LangChain/Manual Input] → Data Parser → Database → Response Formatter → User Response
```

## Взаимодействие компонентов

1. Пользователь отправляет сообщение или команду боту
2. Telegram Bot API Client получает запрос и передает его в Session Manager
3. Session Manager определяет текущее состояние пользователя и необходимое действие
4. Action Handler выполняет соответствующее действие:
   - Для скриншотов: обрабатывает изображение и отправляет в GigaChat API
   - Для ручного ввода: обрабатывает текстовые данные от пользователя
5. Data Parser структурирует полученные данные
6. Данные сохраняются в базу данных
7. Response Formatter подготавливает ответ для пользователя
8. Ответ отправляется пользователю через Telegram Bot API Client

## Схема базы данных

```
+-----------------+     +-------------------+
| cashback        |     | user_settings     |
+-----------------+     +-------------------+
| id              |     | user_id           |
| user_id         |     | preferred_banks   |
| bank            |     | preferred_cats    |
| category        |     | last_active       |
| amount          |     | notifications     |
| input_type      |     +-------------------+
| created_at      |
+-----------------+
```

## Технологический стек

- **Backend:** Python 3.10+
- **Bot Framework:** PyTelegramBotAPI
- **Database:** SQLite
- **LLM Integration:** LangChain + GigaChat API
- **Image Processing:** Pillow
- **Configuration:** python-dotenv

## Безопасность

- Все API ключи хранятся в переменных окружения
- Пользовательские данные изолированы по user_id
- Временные файлы автоматически удаляются после обработки
- Проверка входных данных для предотвращения SQL-инъекций 