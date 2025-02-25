import logging
from bot import create_bot

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        logger.info("Запуск бота...")
        bot = create_bot()
        logger.info("Бот запущен успешно")
        bot.polling(none_stop=True)
    except Exception as e:
        logger.error(f"Произошла ошибка: {str(e)}") 