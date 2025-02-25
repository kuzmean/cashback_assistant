import sqlite3
from datetime import datetime
from .config import DATABASE_PATH

# Инициализация базы данных
conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
cursor = conn.cursor()

# Создание таблицы при первом запуске
def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cashback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        bank TEXT,
        category TEXT,
        amount REAL,
        input_type TEXT,
        created_at TEXT
    )
    """)
    conn.commit()

def save_cashback(user_id, bank, category, amount, input_type="manual"):
    cursor.execute(
        "INSERT INTO cashback (user_id, bank, category, amount, input_type, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, bank, category, amount, input_type, datetime.now().strftime("%d.%m.%Y %H:%M"))
    )
    conn.commit()

def get_user_categories(user_id):
    cursor.execute("SELECT DISTINCT category FROM cashback WHERE user_id=?", (user_id,))
    return [row[0] for row in cursor.fetchall()]

def get_user_banks(user_id):
    cursor.execute("SELECT DISTINCT bank FROM cashback WHERE user_id=?", (user_id,))
    banks = [row[0] for row in cursor.fetchall() if row[0] != "Не выбран"]
    return banks

def get_summary(user_id):
    cursor.execute("SELECT bank, category, amount FROM cashback WHERE user_id=?", (user_id,))
    return cursor.fetchall()

def reset_data_for_bank(user_id, bank):
    cursor.execute("DELETE FROM cashback WHERE user_id=? AND bank=?", (user_id, bank))
    conn.commit()

def reset_all_data(user_id):
    cursor.execute("DELETE FROM cashback WHERE user_id=?", (user_id,))
    conn.commit()

# Инициализация при импорте
init_db() 