from sqlalchemy import Column, Integer, String, Float, Date, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class CashbackRecord(Base):
    __tablename__ = 'cashback_records'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    bank_name = Column(String)
    category = Column(String)
    percentage = Column(Float)
    expiration_date = Column(Date)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<CashbackRecord(bank='{self.bank_name}', category='{self.category}', {self.percentage}%)>" 