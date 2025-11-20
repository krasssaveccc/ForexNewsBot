import json
import os
from datetime import datetime
import pytz
from config import DEFAULT_TIMEZONE

class UserDatabase:
    def __init__(self, db_file="users.json"):
        self.db_file = db_file
        self.users = self._load_users()
    
    def _load_users(self):
        """Загрузка данных пользователей из файла"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_users(self):
        """Сохранение данных пользователей в файл"""
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            return True
        except:
            return False
    
    def get_user(self, user_id):
        """Получение данных пользователя"""
        return self.users.get(str(user_id), {})
    
    def update_user(self, user_id, **updates):
        """Обновление данных пользователя"""
        user_id = str(user_id)
        if user_id not in self.users:
            self.users[user_id] = {
                'morning_notifications': False,
                'reminder_minutes': 15,
                'timezone': DEFAULT_TIMEZONE,  # По умолчанию NY время
                'created_at': datetime.now().isoformat(),
                'first_name': '',
                'last_name': '',
                'username': ''
            }
        
        self.users[user_id].update(updates)
        return self._save_users()
    
    def set_user_timezone(self, user_id, timezone):
        """Установка часового пояса пользователя"""
        return self.update_user(user_id, timezone=timezone)
    
    def get_user_timezone(self, user_id):
        """Получение часового пояса пользователя"""
        user_data = self.get_user(user_id)
        return user_data.get('timezone', DEFAULT_TIMEZONE)
    
    def get_users_with_morning_notifications(self):
        """Получение пользователей с включенными утренними уведомлениями"""
        return [uid for uid, user in self.users.items() 
                if user.get('morning_notifications', False)]
    
    def get_all_users(self):
        """Получение всех пользователей"""
        return list(self.users.keys())
    
    def update_user_profile(self, user_id, first_name, last_name, username):
        """Обновление профиля пользователя"""
        return self.update_user(user_id, 
                              first_name=first_name,
                              last_name=last_name,
                              username=username)

# Глобальный экземпляр базы данных
user_db = UserDatabase()