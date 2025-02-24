# Рекомендуется установить библиотеку:
# !pip install -q pyTelegramBotAPI

import os
import tempfile
from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

import telebot
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

# Инициализация Telegram-бота через pyTelegramBotAPI
bot = telebot.TeleBot(os.environ["TELEGRAM_TOKEN"])

@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(message, "Привет! Отправь мне изображение, и я анализирую кешбэк категории.")

@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    try:
        # Берём file_id самой последней (максимального качества) фотографии
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        # Скачиваем файл во временную директорию
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        tmp_path = tmp_file.name
        tmp_file.close()
        downloaded_file = bot.download_file(file_info.file_path)
        with open(tmp_path, "wb") as new_file:
            new_file.write(downloaded_file)
        # Передаём загруженное фото в LLM
        with open(tmp_path, "rb") as f:
            uploaded_file = llm.upload_file(f)
        result = chain.batch([uploaded_file.id_])
        if result and result[0].categories:
            response_text = "\n".join(f"{cat.category}: {cat.amount}%" for cat in result[0].categories)
        else:
            response_text = "Нет данных о кешбэке."
        bot.reply_to(message, response_text)
    except Exception as e:
        bot.reply_to(message, f"Ошибка обработки изображения, попробуйсте ручной ввод.")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    bot.polling(none_stop=True)
