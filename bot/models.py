from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class CashbackCategory(BaseModel):
    category: str = Field(..., description="Название категории")
    amount: float = Field(..., description="Процент кешбэка")

class CashbackResponse(BaseModel):
    categories: List[CashbackCategory] = Field(..., description="Список категорий с кешбэком")

class UserSession:
    def __init__(self):
        self.bank = None
        self.category = None
        self.stage = None
        self.screenshot = None
        self.await_bank = False
        self.await_category = False
        
    def reset(self):
        self.__init__()

class CashbackEntry:
    def __init__(self, user_id, bank, category, amount, input_type="manual"):
        self.user_id = user_id
        self.bank = bank
        self.category = category
        self.amount = amount
        self.input_type = input_type
        self.created_at = datetime.now().strftime("%d.%m.%Y %H:%M") 