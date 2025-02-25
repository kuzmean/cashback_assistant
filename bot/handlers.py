import os
import tempfile
import logging
from telebot import TeleBot
from telebot import types

from .config import CARD_LINKS
from .database import save_cashback, reset_data_for_bank, reset_all_data
from .api import analyze_image
from .keyboards import (
    main_menu_keyboard, add_info_keyboard, input_method_keyboard,
    bank_keyboard, category_keyboard, reset_confirm_keyboard,
    full_reset_confirm_keyboard, add_more_keyboard, screenshot_confirm_keyboard
)
from .utils import format_summary, save_temp_file, delete_temp_file

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальная сессия для хранения промежуточных данных пользователя
sessions = {}

def register_handlers(bot: TeleBot):
    
    # Обработчик команды /start
    @bot.message_handler(commands=["start"])
    def command_start(message):
        sessions[message.from_user.id] = {}  # сброс сессии
        welcome_text = (
            "Welcome to Cashback Assistant! 🤑\n\n"
            "Я помогу вам отслеживать лучшие предложения и сохранять информацию о кешбэке.\n"
            "Выберите, что хотите сделать:"
        )
        bot.reply_to(message, welcome_text, reply_markup=main_menu_keyboard())

    # Обработчик команды /offer
    @bot.message_handler(commands=["offer"])
    def card_links(message):
        links_text = "💳 Оформление карт:\n"
        for bank, link in CARD_LINKS.items():
            links_text += f"{bank}: {link}\n"
        bot.reply_to(message, links_text, reply_markup=main_menu_keyboard())
    
    # Обработчик добавления информации
    @bot.message_handler(func=lambda m: "добавить информацию" in m.text.lower())
    def add_information(message):
        sessions[message.from_user.id] = {}  # Сброс сессии для нового ввода
        user_id = message.from_user.id
        markup = bank_keyboard(user_id)
        bot.reply_to(message, "Выберите банк:", reply_markup=markup)
    
    # Обработчик показа сводки
    @bot.message_handler(func=lambda m: "показать сводку" in m.text.lower())
    def show_summary(message):
        summary = format_summary(message.from_user.id)
        bot.reply_to(message, f"\n{summary}", reply_markup=main_menu_keyboard())
        
        offer_msg = "💳 Чтобы увеличить вашу выгоду, оформите карту:\n"
        for bank, link in CARD_LINKS.items():
            offer_msg += f"{bank}: {link}\n"
        bot.send_message(message.from_user.id, offer_msg, reply_markup=main_menu_keyboard())
    
    # Обработчик сброса данных
    @bot.message_handler(func=lambda m: "сбросить данные" in m.text.lower())
    def reset_data(message):
        from .database import get_user_banks
        user_id = message.from_user.id
        banks = get_user_banks(user_id)
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        # Если есть сохранённые банки, добавить их кнопки
        if banks:
            buttons = [types.InlineKeyboardButton(text=bank, callback_data=f"resetbank_{bank}") for bank in banks]
            keyboard.add(*buttons)
        
        # Всегда добавляем кнопку для полного сброса
        keyboard.add(types.InlineKeyboardButton(text="Полный сброс статистики", callback_data="reset_all"))
        bot.reply_to(message, "Выберите сброс: для отдельного банка или полный сброс статистики:", reply_markup=keyboard)
    
    # Обработчик возврата в главное меню
    @bot.message_handler(func=lambda m: m.text == "Назад")
    def back_to_main(message):
        bot.reply_to(message, "Главное меню", reply_markup=main_menu_keyboard())
    
    # Обработчик выбора способа ввода
    @bot.message_handler(func=lambda m: m.text in ["Ручной ввод", "Скриншот"])
    def handle_input_method(message):
        user_id = message.from_user.id
        if user_id not in sessions or "bank" not in sessions[user_id]:
            bot.reply_to(message, "Сначала выберите банк", reply_markup=main_menu_keyboard())
            return
        
        if message.text == "Ручной ввод":
            markup = category_keyboard(user_id)
            bot.reply_to(message, "Выберите категорию:", reply_markup=markup)
        else:  # "Скриншот"
            bot.reply_to(message, "Пожалуйста, отправьте скриншот с условиями кэшбэка:", reply_markup=types.ReplyKeyboardRemove())
    
    # Обработчик фотографий
    @bot.message_handler(content_types=["photo"])
    def handle_photo(message):
        user_id = message.from_user.id
        if user_id not in sessions or "bank" not in sessions[user_id]:
            bot.reply_to(message, "Сначала выберите банк и метод ввода", reply_markup=main_menu_keyboard())
            return
        
        try:
            # Получаем файл с наилучшим качеством
            file_info = bot.get_file(message.photo[-1].file_id)
            file_data = bot.download_file(file_info.file_path)
            
            # Сохраняем во временный файл
            temp_file = save_temp_file(file_data)
            
            # Отправляем на анализ
            bot.send_message(user_id, "⏳ Анализирую изображение...")
            categories = analyze_image(temp_file)
            
            # Удаляем временный файл
            delete_temp_file(temp_file)
            
            if not categories:
                bot.reply_to(message, "⚠️ Не удалось найти данные о кэшбэке")
            else:
                # Сохраняем результат в сессию
                sessions[user_id]["screenshot"] = categories
                
                # Формируем текст с результатами
                response = "✅ Распознанные категории:\n\n"
                for cat in categories:
                    response += f"▪️ {cat.category.capitalize()}: {int(cat.amount)}%\n"
                
                # Отправляем результат с кнопками подтверждения
                bot.reply_to(message, response, reply_markup=screenshot_confirm_keyboard())
        
        except Exception as e:
            logger.error(f"Ошибка: {str(e)}")
            bot.reply_to(message, "❌ Произошла ошибка при обработке")
    
    # Обработчик текстовых сообщений для ручного ввода
    @bot.message_handler(func=lambda m: True)
    def handle_text(message):
        user_id = message.from_user.id
        sessions.setdefault(user_id, {})
        
        # Обработка ожидания ввода банка
        if sessions[user_id].get("await_bank", False):
            sessions[user_id]["bank"] = message.text
            sessions[user_id]["await_bank"] = False
            bot.reply_to(message, f"Выбран банк: {message.text}\nВыберите способ ввода информации:", reply_markup=input_method_keyboard())
            return
        
        # Обработка ожидания ввода категории
        if sessions[user_id].get("await_category", False):
            sessions[user_id]["category"] = message.text
            sessions[user_id]["await_category"] = False
            sessions[user_id]["stage"] = "await_cashback"
            bot.reply_to(message, f"Выбрана категория: {message.text}\nВведите величину кешбэка (целое число):")
            return
        
        # Обработка ожидания ввода кэшбэка
        if sessions[user_id].get("stage") == "await_cashback":
            try:
                amount = float(message.text.replace(',', '.').strip('%'))
                bank = sessions[user_id]["bank"]
                category = sessions[user_id]["category"]
                
                # Сохраняем в базу
                save_cashback(user_id, bank, category, amount)
                
                # Уведомляем пользователя
                bot.reply_to(message, f"✅ Сохранено: {category.capitalize()} - {int(amount)}%", reply_markup=add_more_keyboard())
                
                # Сбрасываем состояние
                sessions[user_id]["stage"] = None
            except ValueError:
                bot.reply_to(message, "❌ Пожалуйста, введите числовое значение")
    
    # Обработчики callback-запросов
    
    # Обработчик выбора банка
    @bot.callback_query_handler(func=lambda call: call.data.startswith("bank_"))
    def callback_bank(call):
        user_id = call.from_user.id
        bank = call.data.split("_", 1)[1]
        if bank == "other":
            bot.send_message(user_id, "Введите название вашего банка:")
            sessions[user_id] = {"await_bank": True}
        else:
            sessions.setdefault(user_id, {})["bank"] = bank
            bot.send_message(user_id, f"Выбран банк: {bank}\nВыберите способ ввода информации:", reply_markup=input_method_keyboard())
        bot.answer_callback_query(call.id)
    
    # Обработчик выбора категории
    @bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
    def callback_category(call):
        user_id = call.from_user.id
        cat = call.data.split("_", 1)[1]
        if cat == "other":
            bot.send_message(user_id, "Введите название категории:")
            sessions[user_id]["await_category"] = True
        else:
            sessions.setdefault(user_id, {})["category"] = cat
            bot.send_message(user_id, f"Выбрана категория: {cat}\nВведите величину кешбэка (целое число):")
            sessions[user_id]["stage"] = "await_cashback"
        bot.answer_callback_query(call.id)
    
    # Обработчик сброса данных банка
    @bot.callback_query_handler(func=lambda call: call.data.startswith("resetbank_"))
    def callback_reset_bank(call):
        user_id = call.from_user.id
        bank = call.data.split("_", 1)[1]
        msg = f"Вы действительно хотите сбросить данные для банка {bank}?"
        bot.send_message(user_id, msg, reply_markup=reset_confirm_keyboard(bank))
        bot.answer_callback_query(call.id)
    
    # Обработчик полного сброса
    @bot.callback_query_handler(func=lambda call: call.data == "reset_all")
    def callback_reset_all(call):
        user_id = call.from_user.id
        bot.send_message(user_id, "Вы действительно хотите полностью сбросить всю статистику?", reply_markup=full_reset_confirm_keyboard())
        bot.answer_callback_query(call.id)
    
    # Обработчик подтверждения полного сброса
    @bot.callback_query_handler(func=lambda call: call.data == "reset_all_confirm")
    def callback_reset_all_confirm(call):
        user_id = call.from_user.id
        reset_all_data(user_id)
        bot.send_message(user_id, "✅ Полный сброс статистики выполнен.", reply_markup=main_menu_keyboard())
        bot.answer_callback_query(call.id)
    
    # Обработчик отмены сброса
    @bot.callback_query_handler(func=lambda call: call.data == "reset_cancel")
    def callback_reset_cancel(call):
        user_id = call.from_user.id
        bot.send_message(user_id, "Сброс данных отменён.", reply_markup=main_menu_keyboard())
        bot.answer_callback_query(call.id)
    
    # Обработчик подтверждения сохранения скриншота
    @bot.callback_query_handler(func=lambda call: call.data == "confirm_screenshot")
    def confirm_screenshot(call):
        user_id = call.from_user.id
        categories = sessions.get(user_id, {}).get("screenshot", [])
        bank = sessions.get(user_id, {}).get("bank", "Не выбран")
        
        if categories:
            for cat in categories:
                save_cashback(user_id, bank, cat.category, int(cat.amount), input_type="screenshot")
            
            response = "\n".join(f"{cat.category.capitalize()}: {int(cat.amount)}% 💰" for cat in categories)
            bot.send_message(user_id, f"✅ Сохранено:\n{response}", reply_markup=main_menu_keyboard())
            sessions[user_id].pop("screenshot", None)
        else:
            bot.send_message(user_id, "❌ Нет данных для сохранения.", reply_markup=main_menu_keyboard())
        
        bot.answer_callback_query(call.id)
    
    # Обработчик отмены сохранения скриншота
    @bot.callback_query_handler(func=lambda call: call.data == "cancel_screenshot")
    def cancel_screenshot(call):
        user_id = call.from_user.id
        sessions[user_id].pop("screenshot", None)
        bot.send_message(user_id, "Отменено. Вы можете попробовать ввести данные вручную.", reply_markup=input_method_keyboard())
        bot.answer_callback_query(call.id)
    
    # Обработчик подтверждения сброса данных банка
    @bot.callback_query_handler(func=lambda call: call.data.startswith("reset_") and call.data not in ["reset_all", "reset_all_confirm", "reset_cancel"])
    def callback_reset_bank_confirm(call):
        user_id = call.from_user.id
        bank = call.data.split("_", 1)[1]
        reset_data_for_bank(user_id, bank)
        bot.send_message(user_id, f"Данные для банка {bank} сброшены.", reply_markup=main_menu_keyboard())
        bot.answer_callback_query(call.id)
    
    # Обработчик "Добавить ещё"
    @bot.callback_query_handler(func=lambda call: call.data == "add_more")
    def callback_add_more(call):
        user_id = call.from_user.id
        if user_id in sessions and "bank" in sessions[user_id]:
            markup = category_keyboard(user_id)
            bot.send_message(user_id, "Выберите категорию:", reply_markup=markup)
        else:
            markup = bank_keyboard(user_id)
            bot.send_message(user_id, "Выберите банк:", reply_markup=markup)
        bot.answer_callback_query(call.id)
    
    # Обработчик "Главное меню"
    @bot.callback_query_handler(func=lambda call: call.data == "back_main")
    def callback_back_main(call):
        user_id = call.from_user.id
        bot.send_message(user_id, "Главное меню", reply_markup=main_menu_keyboard())
        bot.answer_callback_query(call.id) 