import threading
import time
from datetime import datetime, timedelta
import pytz
from parser import get_forex_news_for_user
from database import user_db
import telebot
from config import BOT_TOKEN, DEFAULT_TIMEZONE

class NotificationScheduler:
    def __init__(self, bot):
        self.bot = bot
        self.running = False
        self.thread = None
        self.last_morning_notification = None
    
    def start(self):
        """Запуск планировщика"""
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print("🕐 Планировщик уведомлений запущен")
    
    def stop(self):
        """Остановка планировщика"""
        self.running = False
        if self.thread:
            self.thread.join()
        print("🛑 Планировщик уведомлений остановлен")
    
    def _run(self):
        """Основной цикл планировщика"""
        while self.running:
            now_utc = datetime.now(pytz.UTC)
            
            # Проверяем утренние уведомления для каждого пользователя в его времени
            self._check_morning_notifications(now_utc)
            
            # Проверяем напоминания
            self._check_event_reminders(now_utc)
            
            time.sleep(60)
    
    def _check_morning_notifications(self, now_utc):
        """Проверка утренних уведомлений для каждого пользователя"""
        users = user_db.get_users_with_morning_notifications()
        if not users:
            return
        
        today = now_utc.date()
        
        for user_id in users:
            try:
                user_timezone = user_db.get_user_timezone(user_id)
                tz = pytz.timezone(user_timezone)
                user_time = now_utc.astimezone(tz)
                
                # Проверяем, 08:00 ли у пользователя
                if user_time.hour == 8 and user_time.minute == 0:
                    # Проверяем, не отправляли ли уже сегодня
                    user_data = user_db.get_user(user_id)
                    last_notification = user_data.get('last_morning_notification')
                    
                    if last_notification != today.isoformat():
                        self._send_morning_notification(user_id, user_timezone)
                        user_db.update_user(user_id, last_morning_notification=today.isoformat())
                        
            except Exception as e:
                print(f"❌ Ошибка проверки утреннего уведомления для {user_id}: {e}")
    
    def _send_morning_notification(self, user_id, user_timezone):
        """Отправка утреннего уведомления"""
        try:
            morning_news = get_forex_news_for_user(user_id, only_important=True, force_refresh=False)
            
            if morning_news:
                message = "🌅 Доброе утро!\n\n"
                message += "📊 Важные новости на сегодня:\n\n"
                
                for item in morning_news[:5]:
                    emoji = "🔴" if item['impact'] == "High" else "🟡"
                    message += f"{emoji} {item['time']} - {item['currency']}: {item['event']}\n"
                
                message += f"\nВсего важных событий: {len(morning_news)}\n"
                message += f"Часовой пояс: {user_timezone}"
            else:
                message = "🌅 Доброе утро!\n\n📭 На сегодня важных экономических новостей нет.\n"
                message += f"Часовой пояс: {user_timezone}"
            
            self.bot.send_message(user_id, message)
            print(f"✅ Утреннее уведомление отправлено пользователю {user_id}")
            
        except Exception as e:
            print(f"❌ Ошибка отправки утреннего уведомления пользователю {user_id}: {e}")
    
    def _check_event_reminders(self, now_utc):
        """Проверка напоминаний о событиях"""
        for user_id, user_data in user_db.users.items():
            try:
                reminder_minutes = user_data.get('reminder_minutes', 15)
                user_timezone = user_data.get('timezone', DEFAULT_TIMEZONE)
                
                # Получаем новости для пользователя
                user_events = get_forex_news_for_user(user_id, only_important=True, force_refresh=False)
                
                for event in user_events:
                    if 'user_time_obj' in event and event['user_time_obj']:
                        reminder_time = event['user_time_obj'] - timedelta(minutes=reminder_minutes)
                        
                        # Сравниваем с текущим временем пользователя
                        user_tz = pytz.timezone(user_timezone)
                        user_now = now_utc.astimezone(user_tz)
                        
                        if abs((reminder_time - user_now).total_seconds()) < 60:
                            self._send_reminder(user_id, event, reminder_minutes)
                            
            except Exception as e:
                print(f"❌ Ошибка проверки напоминаний для {user_id}: {e}")
    
    def _send_reminder(self, user_id, event, minutes_before):
        """Отправка напоминания о событии"""
        try:
            emoji = "🔴" if event['impact'] == "High" else "🟡"
            
            message = f"⏰ Напоминание за {minutes_before} минут\n\n"
            message += f"{emoji} Скоро: {event['time']}\n"
            message += f"💰 Валюта: {event['currency']}\n"
            message += f"📈 Событие: {event['event']}\n"
            message += f"⚡ Важность: {event['impact']}\n\n"
            
            if event['forecast'] != "—":
                message += f"📊 Прогноз: {event['forecast']}"
                if event['previous'] != "—":
                    message += f" (Предыдущий: {event['previous']})"
                message += "\n\n"
            
            message += "Будьте готовы к повышенной волатильности!"
            
            self.bot.send_message(user_id, message)
            print(f"✅ Напоминание отправлено пользователю {user_id}")
            
        except Exception as e:
            print(f"❌ Ошибка отправки напоминания пользователю {user_id}: {e}")

# Глобальный экземпляр планировщика
scheduler = None