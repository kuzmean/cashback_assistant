import os
from dotenv import load_dotenv
from langchain_gigachat.chat_models import GigaChat
from langchain.schema import SystemMessage, HumanMessage

load_dotenv()

def test_gigachat(image_path: str):
    try:
        # Инициализация GigaChat
        llm = GigaChat(
            credentials='NDlkMmJlMjMtMTE1MC00YTY3LWEwOTItY2EzZWUzZWNlNzhhOmVhYTIyNDI1LTBmOWQtNDI5ZS1iMDZhLTkzZjNlZTc0NjJkZA==',
            verify_ssl_certs=False,
            timeout=30,
            model="GigaChat-Pro"
        )
        
        # Загрузка файла
        with open(image_path, "rb") as f:
            uploaded_file = llm.upload_file(f)
        
        # Формируем запрос
        messages = [
            SystemMessage(
                content="""Распознай ВСЕ категории кэшбэка и их проценты и верни ТОЛЬКО JSON:
                Пример: {"Кино": 6, "Продукты": 5}. 
                Если нет данных - верни {"error": "Нет данных"}"""),
            HumanMessage(
                content="",
                additional_kwargs={"attachments": [uploaded_file.id_]}
            )
        ]
        
        # Отправка запроса
        response = llm(messages)
        print("\n📝 Ответ GigaChat:")
        print(response.content)
        
    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")

if __name__ == "__main__":
    test_image = "/Users/andrejkuzmin/ai_helper/2025-01-27 23.02.06.jpg"  # Укажите путь к тестовому фото
    test_gigachat(test_image) 