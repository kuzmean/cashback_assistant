import os
import tempfile
from datetime import datetime
from .config import CATEGORY_EMOJIS, DEFAULT_CATEGORY_EMOJI
from .database import get_summary as db_get_summary

def format_summary(user_id: int):
    rows = db_get_summary(user_id)
    summary = {}
    
    for bank, category, amount in rows:
        if category not in summary:
            summary[category] = []
        summary[category].append((bank, amount))
    
    text_lines = ["🏆 Лучшие кэшбэки по категориям:"]
    
    for cat, entries in summary.items():
        # Если первая буква не является буквой, предполагаем, что эмоджи уже есть
        if cat and not cat[0].isalpha():
            cat_label = cat.capitalize()
        elif cat in CATEGORY_EMOJIS:
            cat_label = f"{CATEGORY_EMOJIS[cat]} {cat.capitalize()}"
        else:
            cat_label = f"{DEFAULT_CATEGORY_EMOJI} {cat.capitalize()}"
        
        text_lines.append(f"\n {cat_label}")
        entries.sort(key=lambda x: x[1], reverse=True)
        medals = ["🥇", "🥈", "🥉"]
        
        for idx, (bank, amount) in enumerate(entries[:3]):
            medal = medals[idx] if idx < len(medals) else ""
            text_lines.append(f"└ {medal} {bank}: {int(amount)}%")
    
    text_lines.append(f"\n📅 Актуально на: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(text_lines)

def save_temp_file(file_data):
    # Создание временного файла для сохранения изображения
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    temp_file.write(file_data)
    temp_file.close()
    return temp_file.name

def delete_temp_file(file_path):
    # Удаление временного файла после использования
    try:
        os.unlink(file_path)
    except Exception as e:
        pass 