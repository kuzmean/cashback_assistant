import os
from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

from langchain_gigachat.chat_models import GigaChat

# Use credentials from environment variable
llm = GigaChat(
    credentials=os.environ["GIGACHAT_CREDENTIALS"],
    temperature=0.1,
    verify_ssl_certs=False,
    timeout=6000,
    model="GigaChat-Max"
)

from typing import List
from langchain.output_parsers import PydanticOutputParser
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableLambda
import re
import json

class CashbackCategory(BaseModel):
    category: str = Field(..., description="Название категории")
    amount: float = Field(..., description="Процент кешбэка")

class CashbackResponse(BaseModel):
    categories: List[CashbackCategory] = Field(..., description="Список категорий с кешбэком")

class RobustParser(PydanticOutputParser):
    def parse(self, text: str) -> CashbackResponse:
        try:
            # Нормализация JSON ответа
            text = text.replace("'", '"').replace("\\", "")
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if not json_match:
                raise ValueError("Не найден JSON в ответе")
            json_str = json_match.group()
            data = json.loads(json_str)
            # Автокоррекция структуры
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

# Пример работы
file = llm.upload_file(open("2025-01-27 23.02.06.jpg", "rb"))
result = chain.batch([file.id_])

import pandas as pd

df = pd.DataFrame(
    [
        {"Категория": cat.category, "Кешбэк (%)": cat.amount}
        for response in result       # Итерация по списку CashbackResponse
        for cat in response.categories  # Итерация по категориям внутри каждого ответа
    ]
)

print(df)