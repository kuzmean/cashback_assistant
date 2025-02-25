# Запуск в Docker

## Требования
- Docker
- Docker Compose

## Подготовка
1. Скопируйте файл .env.example:
   ```bash
   cp .env.example .env
   ```

2. Отредактируйте файл .env, заполнив необходимые переменные окружения:
   ```
   TELEGRAM_TOKEN=your_telegram_token_here
   GIGACHAT_CREDENTIALS=your_gigachat_credentials_here
   ```

## Сборка и запуск

### Сборка образа
```bash
docker-compose build
```

### Запуск в режиме демона
```bash
docker-compose up -d
```

### Остановка контейнера
```bash
docker-compose down
```

## Просмотр логов
```bash
docker-compose logs -f
```

## Обновление
Для обновления бота при изменении кода:
```bash
git pull
docker-compose down
docker-compose build
docker-compose up -d
```

## Структура данных
- Файл базы данных хранится в директории `./data/`
- Логи приложения сохраняются в директории `./logs/`

## Устранение неполадок

### Проблемы с правами доступа
Если возникли проблемы с правами доступа к директориям:
```bash
chmod -R 777 data logs
```

### Контейнер не запускается
Проверьте логи запуска:
```bash
docker-compose logs
```

### Занят порт
Если порт 80 уже используется другим сервисом, измените маппинг портов в docker-compose.yml 