import json
import re
import os
from langchain_gigachat.chat_models import GigaChat
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.output_parsers import PydanticOutputParser
import logging

from .config import GIGACHAT_CREDENTIALS, GIGACHAT_MODEL, GIGACHAT_TEMPERATURE, GIGACHAT_TIMEOUT
from .models import CashbackCategory, CashbackResponse

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация LLM
llm = GigaChat(
    credentials=GIGACHAT_CREDENTIALS,
    temperature=GIGACHAT_TEMPERATURE,
    verify_ssl_certs=False,
    timeout=GIGACHAT_TIMEOUT,
    model=GIGACHAT_MODEL
)

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
            logger.error(f"Ошибка парсинга: {str(e)}")
            return CashbackResponse(categories=[])

parser = RobustParser(pydantic_object=CashbackResponse)

def _get_messages_from_url(url: str):
    return {
        "history": [
            HumanMessage(content="", additional_kwargs={"attachments": [url]}),
        ]
    }

def analyze_image(file_path: str):
    try:
        # Загрузка файла и получение его ID
        with open(file_path, "rb") as f:
            uploaded_file = llm.upload_file(f)
        
        # Формирование запроса с системным промптом и изображением
        messages = [
            SystemMessage(
                content=(
                    "Проанализируй изображение и выдели все категории кешбэка, которые на нем указаны. "
                    "Выделяй только название категории и процент кешбэка. "
                    "Возвращай данные в формате JSON: {\"categories\": [{\"category\": \"название\", \"amount\": число}]}. "
                    "Название категории должно быть в нижнем регистре, без лишних знаков пунктуации. "
                    "Пример: {\"categories\": [{\"category\": \"рестораны\", \"amount\": 5}, {\"category\": \"азс\", \"amount\": 3}]}"
                )
            ),
            HumanMessage(
                content=[{"type": "file", "file_id": uploaded_file.id_}]
            )
        ]
        
        # Отправка запроса и получение ответа
        response = llm(messages)
        
        # Парсинг ответа в структурированные данные
        result = parser.parse(response.content)
        return result.categories
    
    except Exception as e:
        logger.error(f"Ошибка при анализе изображения: {str(e)}")
        return [] 