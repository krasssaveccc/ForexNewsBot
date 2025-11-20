import telebot
from datetime import datetime
import atexit
import pytz
from parser import get_forex_news_for_user, cleanup_parser, clear_news_cache
from database import user_db
from scheduler import NotificationScheduler
from config import BOT_TOKEN, DEFAULT_TIMEZONE

# Создаем бота
bot = telebot.TeleBot(BOT_TOKEN)

# Создаем планировщик
scheduler = NotificationScheduler(bot)

def create_main_keyboard():
    """Создание основной клавиатуры"""
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add("📊 Новости", "⚙️ Настройки")
    keyboard.add("🌅 Утренние уведомления", "⏰ Напоминания")
    keyboard.add("🌍 Часовой пояс", "ℹ️ Помощь")
    return keyboard

def create_settings_keyboard():
    """Создание клавиатуры настроек"""
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add("🌅 Утренние уведомления", "⏰ Напоминания")
    keyboard.add("🌍 Часовой пояс", "📊 Статистика")
    keyboard.add("🔄 Обновить данные", "🔙 Главное меню")
    return keyboard

def create_timezone_keyboard():
    """Создание клавиатуры выбора часового пояса"""
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add("🇷🇺 Москва", "🇬🇧 Лондон", "🇺🇸 Нью-Йорк")
    keyboard.add("🇪🇺 Берлин", "🇷🇸 Белград", "🇯🇵 Токио")  # ← ДОБАВЬТЕ БЕЛГРАД
    keyboard.add("🇦🇺 Сидней", "🔙 Настройки")
    return keyboard

def create_reminder_keyboard():
    """Создание клавиатуры выбора времени напоминаний"""
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    keyboard.add("5 минут", "15 минут", "30 минут")
    keyboard.add("45 минут", "60 минут", "🔙 Настройки")
    return keyboard

def create_back_keyboard():
    """Клавиатура с кнопкой назад"""
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("🔙 Главное меню")
    return keyboard

def format_news_message(news_items, user_timezone):
    """Форматирование новостей для Telegram с Actual/Forecast/Previous"""
    if not news_items:
        return "📭 На сегодня важных экономических новостей нет."
    
    message = "📊 *Экономические новости на сегодня:*\n\n"
    
    for item in news_items:
        # Эмодзи для важности
        if item['impact'] == "High":
            emoji = "🔴"
        elif item['impact'] == "Medium":
            emoji = "🟡" 
        else:
            emoji = "⚪"
            
        message += f"{emoji} *{item['time']}* - {item['currency']}\n"
        message += f"   📅 {item['event']}\n"
        message += f"   ⚡ {item['impact']} Impact\n"
        
        # Добавляем данные если они есть
        has_data = item['actual'] != "—" and item['actual'] != ""
        
        if has_data:
            message += "   📊 Данные:\n"
            if item['forecast'] != "—" and item['forecast'] != "":
                message += f"      • Прогноз: {item['forecast']}\n"
            if item['actual'] != "—" and item['actual'] != "":
                # Выделяем факт жирным
                message += f"      • *Факт*: {item['actual']}\n"
            if item['previous'] != "—" and item['previous'] != "":
                message += f"      • Предыдущий: {item['previous']}\n"
        else:
            # Если данных нет, показываем только если есть прогноз
            if item['forecast'] != "—" and item['forecast'] != "":
                message += "   📊 Данные:\n"
                message += f"      • Прогноз: {item['forecast']}\n"
                if item['previous'] != "—" and item['previous'] != "":
                    message += f"      • Предыдущий: {item['previous']}\n"
        
        message += "\n"
    
    message += "________________________________\n"
    message += f"Часовой пояс: {user_timezone}\n"
    message += f"Обновлено: {datetime.now().strftime('%H:%M %d.%m.%Y')}"
    
    return message

def detect_user_timezone(user_id):
    """Автоматическое определение часового пояса пользователя"""
    try:
        return "Europe/Moscow"
    except:
        return DEFAULT_TIMEZONE

@bot.message_handler(func=lambda message: message.text in ["🇷🇺 Москва", "🇬🇧 Лондон", "🇺🇸 Нью-Йорк", "🇪🇺 Берлин", "🇷🇸 Белград", "🇯🇵 Токио", "🇦🇺 Сидней"])
def handle_timezone_choice(message):
    """Обработчик выбора часового пояса"""
    timezone_map = {
        '🇷🇺 Москва': 'Europe/Moscow',      # UTC+3
        '🇬🇧 Лондон': 'Europe/London',      # UTC+0/UTC+1 
        '🇺🇸 Нью-Йорк': 'America/New_York', # UTC-5/UTC-4
        '🇪🇺 Берлин': 'Europe/Berlin',      # UTC+1/UTC+2
        '🇷🇸 Белград': 'Europe/Belgrade',   # UTC+1/UTC+2 ← ДОБАВЬТЕ
        '🇯🇵 Токио': 'Asia/Tokyo',          # UTC+9
        '🇦🇺 Сидней': 'Australia/Sydney'    # UTC+10/UTC+11
    }
    
    timezone = timezone_map[message.text]
    user_db.set_user_timezone(message.chat.id, timezone)
    
    try:
        tz = pytz.timezone(timezone)
        user_time = datetime.now(pytz.UTC).astimezone(tz).strftime('%H:%M %d.%m.%Y')
    except:
        user_time = "неизвестно"
    
    response = f"✅ Часовой пояс установлен!\n\n"
    response += f"🌍 Новый часовой пояс: {timezone}\n"
    response += f"🕐 Ваше время: {user_time}\n\n"
    
    # Добавляем пояснение для Белграда
    if timezone == 'Europe/Belgrade':
        response += "💡 Теперь время событий будет совпадать с Forex Factory\n"
    
    response += "Теперь все события будут показываться в вашем местном времени."
    
    bot.reply_to(message, response, reply_markup=create_settings_keyboard())
    
    welcome = """
🤖 Forex News Bot

Добро пожаловать! Я буду присылать вам важные экономические новости с Forex Factory.

🎯 Что я умею:
• Показывать важные экономические события
• Присылать утренние сводки в 08:00
• Напоминать о событиях заранее
• Показывать время в вашем часовом поясе

👇 Используйте кнопки ниже для управления:
    """
    bot.reply_to(message, welcome, reply_markup=create_main_keyboard())

@bot.message_handler(commands=['refresh'])
def handle_refresh_command(message):
    """Принудительное обновление кэша новостей"""
    try:
        clear_news_cache()
        bot.reply_to(message, "🔄 Кэш новостей очищен! При следующем запросе данные обновятся.",
                   reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка очистки кэша: {e}",
                   reply_markup=create_main_keyboard())

# Обработчики текстовых сообщений (кнопок)
@bot.message_handler(func=lambda message: message.text == "📊 Новости")
def handle_news_button(message):
    """Обработчик кнопки Новости"""
    try:
        bot.reply_to(message, "🔄 Получаю новости... Это может занять несколько секунд.", 
                    reply_markup=create_back_keyboard())
        
        # Используем force_refresh=True для принудительного обновления
        news = get_forex_news_for_user(message.chat.id, only_important=True, force_refresh=True)
        user_timezone = user_db.get_user_timezone(message.chat.id)
        response = format_news_message(news, user_timezone)
        
        # Отправляем с parse_mode для Markdown
        bot.send_message(message.chat.id, response, 
                        parse_mode='Markdown', 
                        reply_markup=create_main_keyboard())
        
    except Exception as e:
        bot.reply_to(message, "❌ Произошла ошибка при получении новостей",
                    reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: message.text == "⚙️ Настройки")
def handle_settings_button(message):
    """Обработчик кнопки Настройки"""
    user_data = user_db.get_user(message.chat.id)
    
    morning_status = "✅ ВКЛ" if user_data.get('morning_notifications') else "❌ ВЫКЛ"
    reminder_minutes = user_data.get('reminder_minutes', 15)
    timezone = user_data.get('timezone', DEFAULT_TIMEZONE)
    
    try:
        tz = pytz.timezone(timezone)
        user_time = datetime.now(pytz.UTC).astimezone(tz).strftime('%H:%M %d.%m.%Y')
    except:
        user_time = "неизвестно"
    
    settings_text = f"""
⚙️ Ваши настройки:

🌅 Утренние уведомления: {morning_status}
⏰ Напоминания за: {reminder_minutes} мин
🌍 Часовой пояс: {timezone}
🕐 Ваше время: {user_time}

👇 Выберите что хотите настроить:
    """
    bot.reply_to(message, settings_text, reply_markup=create_settings_keyboard())

@bot.message_handler(func=lambda message: message.text == "🔄 Обновить данные")
def handle_refresh_button(message):
    """Обработчик кнопки Обновить данные"""
    try:
        clear_news_cache()
        bot.reply_to(message, "✅ Данные обновлены! Теперь события будут в правильном порядке.",
                   reply_markup=create_settings_keyboard())
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка обновления: {e}",
                   reply_markup=create_settings_keyboard())

@bot.message_handler(func=lambda message: message.text == "🌅 Утренние уведомления")
def handle_morning_button(message):
    """Обработчик кнопки Утренние уведомления"""
    user_data = user_db.get_user(message.chat.id)
    current_status = user_data.get('morning_notifications', False)
    
    new_status = not current_status
    user_db.update_user(message.chat.id, morning_notifications=new_status)
    
    if new_status:
        response = "✅ Утренние уведомления включены!\n\n"
        response += "Теперь вы будете получать сводку важных новостей каждый день в 08:00 утра."
    else:
        response = "❌ Утренние уведомления выключены.\n\n"
        response += "Вы больше не будете получать утренние сводки."
    
    bot.reply_to(message, response, reply_markup=create_settings_keyboard())

@bot.message_handler(func=lambda message: message.text == "⏰ Напоминания")
def handle_reminder_button(message):
    """Обработчик кнопки Напоминания"""
    response = "⏰ Выберите за сколько минут присылать напоминания:\n\n"
    response += "Вы будете получать уведомления перед важными экономическими событиями."
    
    bot.reply_to(message, response, reply_markup=create_reminder_keyboard())

@bot.message_handler(func=lambda message: message.text in ["5 минут", "15 минут", "30 минут", "45 минут", "60 минут"])
def handle_reminder_time(message):
    """Обработчик выбора времени напоминания"""
    minutes_map = {
        '5 минут': 5,
        '15 минут': 15, 
        '30 минут': 30,
        '45 минут': 45,
        '60 минут': 60
    }
    
    minutes = minutes_map[message.text]
    user_db.update_user(message.chat.id, reminder_minutes=minutes)
    
    response = f"✅ Напоминания установлены за {minutes} минут!\n\n"
    response += f"Теперь вы будете получать уведомления за {minutes} минут до важных экономических событий."
    
    bot.reply_to(message, response, reply_markup=create_settings_keyboard())

@bot.message_handler(func=lambda message: message.text == "🌍 Часовой пояс")
def handle_timezone_button(message):
    """Обработчик кнопки Часовой пояс"""
    user_timezone = user_db.get_user_timezone(message.chat.id)
    
    try:
        tz = pytz.timezone(user_timezone)
        user_time = datetime.now(pytz.UTC).astimezone(tz).strftime('%H:%M %d.%m.%Y')
    except:
        user_time = "неизвестно"
    
    response = f"🌍 Текущий часовой пояс: {user_timezone}\n"
    response += f"🕐 Ваше время: {user_time}\n\n"
    response += "👇 Выберите ваш часовой пояс:"
    
    bot.reply_to(message, response, reply_markup=create_timezone_keyboard())

@bot.message_handler(func=lambda message: message.text in ["🇷🇺 Москва", "🇬🇧 Лондон", "🇺🇸 Нью-Йорк", "🇪🇺 Берлин", "🇷🇸 Белград", "🇯🇵 Токио", "🇦🇺 Сидней"])
def handle_timezone_choice(message):
    """Обработчик выбора часового пояса"""
    timezone_map = {
        '🇷🇺 Москва': 'Europe/Moscow',           # UTC+3
        '🇬🇧 Лондон': 'Europe/London',           # UTC+0/UTC+1 
        '🇺🇸 Нью-Йорк': 'America/New_York',      # UTC-5/UTC-4 ← ПРАВИЛЬНЫЙ!
        '🇪🇺 Берлин': 'Europe/Berlin',           # UTC+1/UTC+2
        '🇷🇸 Белград': 'Europe/Belgrade',        # UTC+1/UTC+2
        '🇯🇵 Токио': 'Asia/Tokyo',               # UTC+9
        '🇦🇺 Сидней': 'Australia/Sydney'         # UTC+10/UTC+11
    }
    
    timezone = timezone_map[message.text]
    user_db.set_user_timezone(message.chat.id, timezone)
    
    try:
        tz = pytz.timezone(timezone)
        user_time = datetime.now(pytz.UTC).astimezone(tz).strftime('%H:%M %d.%m.%Y')
    except Exception as e:
        print(f"❌ Ошибка установки часового пояса: {e}")
        user_time = "неизвестно"
    
    response = f"✅ Часовой пояс установлен!\n\n"
    response += f"🌍 Новый часовой пояс: {timezone}\n"
    response += f"🕐 Ваше время: {user_time}\n\n"
    
    bot.reply_to(message, response, reply_markup=create_settings_keyboard())

@bot.message_handler(func=lambda message: message.text == "📊 Статистика")
def handle_stats_button(message):
    """Обработчик кнопки Статистика"""
    try:
        bot.reply_to(message, "📊 Собираю статистику...",
                    reply_markup=create_back_keyboard())
        
        all_events = get_forex_news_for_user(message.chat.id, only_important=False, force_refresh=False)
        
        high_count = len([e for e in all_events if e['impact'] == 'High'])
        medium_count = len([e for e in all_events if e['impact'] == 'Medium'])
        low_count = len([e for e in all_events if e['impact'] == 'Low'])
        
        stats_message = f"""
📈 Статистика событий на сегодня:

🔴 Высокая важность: {high_count}
🟡 Средняя важность: {medium_count}  
⚪ Низкая важность: {low_count}
📊 Всего событий: {len(all_events)}

Обновлено: {datetime.now().strftime('%H:%M %d.%m.%Y')}
        """
        
        bot.reply_to(message, stats_message, reply_markup=create_settings_keyboard())
        
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка при получении статистики",
                    reply_markup=create_settings_keyboard())

@bot.message_handler(func=lambda message: message.text == "ℹ️ Помощь")
def handle_help_button(message):
    """Обработчик кнопки Помощь"""
    help_text = """
📋 Как пользоваться ботом:

📊 Новости - Показать важные события на сегодня
⚙️ Настройки - Настроить уведомления и часовой пояс
🌅 Утренние уведомления - Вкл/выкл сводки в 08:00
⏰ Напоминания - Установить время напоминаний
🌍 Часовой пояс - Сменить ваш часовой пояс
🔄 Обновить данные - Обновить кэш новостей

💡 Особенности:
• Все события хранятся в NY времени (UTC-5)
• Автоматически конвертируются в ваше время
• Данные обновляются раз в день

🆘 Если что-то не работает:
Попробуйте нажать "🔄 Обновить данные"
    """
    bot.reply_to(message, help_text, reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: message.text == "🔙 Главное меню")
def handle_back_button(message):
    """Обработчик кнопки Назад в главное меню"""
    bot.reply_to(message, "👇 Выберите действие:", 
                reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: message.text == "🔙 Настройки")
def handle_back_to_settings(message):
    """Обработчик кнопки Назад в настройки"""
    handle_settings_button(message)

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    """Обработчик всех остальных сообщений"""
    bot.reply_to(message, "🤔 Не понимаю ваше сообщение.\n\n👇 Используйте кнопки ниже:", 
                reply_markup=create_main_keyboard())

if __name__ == "__main__":
    print("🚀 Запуск Forex News Bot...")
    print("💡 Бот использует Selenium для парсинга")
    print("🔔 Планировщик уведомлений запускается...")
    
    # Запускаем планировщик
    scheduler.start()
    
    # Регистрируем очистку при выходе
    atexit.register(cleanup_parser)
    atexit.register(scheduler.stop)
    
    try:
        bot.polling()
    except KeyboardInterrupt:
        print("\n🛑 Остановка бота...")
    finally:
        scheduler.stop()
        cleanup_parser()
        print("✅ Ресурсы очищены")# Добавьте это в конец bot.py
from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return "Forex Telegram Bot is running!"

@app.route('/health')
def health():
    return "OK"

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False)

def main():
    """Основная функция запуска бота"""
    print("🚀 Запуск Forex News Bot...")
    print("💡 Бот использует Selenium для парсинга")
    print("🔔 Планировщик уведомлений запускается...")
    
    # Запускаем планировщик
    scheduler.start()
    
    # Регистрируем очистку при выходе
    atexit.register(cleanup_parser)
    atexit.register(scheduler.stop)
    
    try:
        bot.polling(none_stop=True, timeout=60)
    except KeyboardInterrupt:
        print("\n🛑 Остановка бота...")
    finally:
        scheduler.stop()
        cleanup_parser()
        print("✅ Ресурсы очищены")

if __name__ == "__main__":
    print("🚀 Запуск Forex News Bot на Render...")
    
    # Простой веб-сервер для health checks
    def health_server():
        from http.server import HTTPServer, BaseHTTPRequestHandler
        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'OK')
            def log_message(self, format, *args):
                pass  # Отключаем логи
        
        server = HTTPServer(('0.0.0.0', 5000), HealthHandler)
        print("🌐 Health check server running on port 5000")
        server.serve_forever()
    
    # Запускаем веб-сервер в фоне
    import threading
    web_thread = threading.Thread(target=health_server, daemon=True)
    web_thread.start()
    
    # Запускаем бота
    main()