import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import logging
import pytz

# Кэш для новостей
news_cache = {
    'data': None,
    'timestamp': None,
    'last_updated': None
}

CACHE_DURATION = 300  # 5 минут

def convert_time_to_timezone(event_time, from_tz='Europe/Belgrade', to_tz='Europe/Moscow'):
    """
    Конвертирует время между часовыми поясами с улучшенной обработкой ошибок
    """
    try:
        if not event_time or event_time == 'Tentative':
            return event_time
            
        print(f"🕐 Конвертируем '{event_time}' из {from_tz} в {to_tz}")
        
        # Парсим время (улучшенная обработка форматов)
        time_str = event_time.replace('am', ' AM').replace('pm', ' PM')
        
        # Обработка разных форматов времени
        try:
            event_datetime = datetime.strptime(time_str, '%I:%M %p')
        except ValueError:
            # Если не удалось распарсить, возвращаем исходное время
            print(f"⚠️ Не удалось распарсить время: '{event_time}'")
            return event_time
        
        # Устанавливаем сегодняшнюю дату
        today = datetime.now().date()
        event_datetime = event_datetime.replace(year=today.year, month=today.month, day=today.day)
        
        # Конвертируем часовой пояс
        try:
            from_tz_obj = pytz.timezone(from_tz)
            to_tz_obj = pytz.timezone(to_tz)
            
            localized_dt = from_tz_obj.localize(event_datetime)
            converted_dt = localized_dt.astimezone(to_tz_obj)
            
            result = converted_dt.strftime('%I:%M%p').lower().lstrip('0')
            print(f"✅ Результат: '{event_time}' -> '{result}'")
            
            return result
            
        except Exception as tz_error:
            print(f"⚠️ Ошибка конвертации часового пояса: {tz_error}")
            # Возвращаем время с пометкой о часовом поясе
            return f"{event_time} ({to_tz.split('/')[-1]})"
        
    except Exception as e:
        print(f"❌ Общая ошибка конвертации: {e}")
        return event_time

def parse_forexfactory_selenium():
    """Парсинг Forex Factory с использованием Selenium и извлечением данных из JavaScript"""
    driver = None
    try:
        print("🌐 Загружаем Forex Factory с Selenium...")
        
        # Настройки для Selenium
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
        
        driver = webdriver.Chrome(options=options)
        driver.get("https://www.forexfactory.com/")
        
        print("⏳ Ожидаем загрузку календаря...")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "calendar"))
        )
        
        # Извлекаем данные из JavaScript
        calendar_data = extract_calendar_from_javascript(driver)
        
        if calendar_data:
            print(f"📊 Найдено событий через JavaScript: {len(calendar_data)}")
            return calendar_data
        else:
            return parse_calendar_from_html(driver)
            
    except Exception as e:
        print(f"❌ Ошибка парсинга Forex Factory: {str(e)}")
        return []
    finally:
        if driver:
            driver.quit()

def extract_calendar_from_javascript(driver):
    """Извлечение данных календаря из JavaScript объекта"""
    try:
        # Сначала получаем часовой пояс, который видит Forex Factory
        tz_script = "return Intl.DateTimeFormat().resolvedOptions().timeZone;"
        detected_tz = driver.execute_script(tz_script)
        print(f"🌍 Forex Factory видит ваш часовой пояс как: {detected_tz}")
        
        # Потом получаем данные календаря
        script = """
        if (typeof window.calendarComponentStates !== 'undefined') {
            var calendarData = Object.values(window.calendarComponentStates)[0];
            // Добавляем информацию о часовом поясе
            calendarData.detected_timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
            return calendarData;
        }
        return null;
        """
        
        calendar_state = driver.execute_script(script)
        
        if not calendar_state:
            print("❌ Не найден calendarComponentStates в JavaScript")
            return []
        
        events = []
        days = calendar_state.get('days', [])
        detected_timezone = calendar_state.get('detected_timezone', 'Unknown')
        
        print(f"📅 Найдено дней: {len(days)}")
        print(f"🌍 Forex Factory определил часовой пояс: {detected_timezone}")
        
        for day in days:
            day_events = day.get('events', [])
            for event in day_events:
                if not event.get('name') or not event.get('timeLabel'):
                    continue
                
                print(f"🕐 СЫРОЕ ВРЕМЯ: '{event.get('timeLabel')}' | Событие: {event.get('name')}")
                    
                # Преобразуем impact
                impact_title = event.get('impactTitle', '')
                if 'High' in impact_title:
                    impact = 'High'
                elif 'Medium' in impact_title:
                    impact = 'Medium'
                else:
                    impact = 'Low'
                    
                event_data = {
                    'time': event.get('timeLabel', ''),
                    'currency': event.get('currency', ''),
                    'event': event.get('name', ''),
                    'impact': impact,
                    'actual': event.get('actual', '—'),
                    'forecast': event.get('forecast', '—'),
                    'previous': event.get('previous', '—'),
                    'original_timezone': detected_timezone  # сохраняем исходный пояс
                }
                events.append(event_data)
        
        print(f"🔍 Извлечено {len(events)} событий из JavaScript")
        return events
        
    except Exception as e:
        print(f"❌ Ошибка извлечения данных из JavaScript: {str(e)}")
        return []

def parse_calendar_from_html(driver):
    """Традиционный парсинг из HTML (резервный метод)"""
    try:
        print("🔍 Пробуем парсинг из HTML...")
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        events = []
        calendar_table = soup.find('table', class_='calendar__table')
        
        if not calendar_table:
            return []
        
        rows = calendar_table.find_all('tr', class_='calendar__row')
        
        for row in rows:
            try:
                if 'calendar__row--header' in row.get('class', []):
                    continue
                
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue
                
                time = cells[0].get_text(strip=True)
                currency = cells[1].get_text(strip=True)
                event_name = cells[2].get_text(strip=True)
                impact = cells[3].get_text(strip=True)
                
                if not event_name or not time:
                    continue
                
                event_data = {
                    'time': time,
                    'currency': currency,
                    'event': event_name,
                    'impact': impact,
                    'actual': '—',
                    'forecast': '—',
                    'previous': '—',
                    'original_timezone': 'Europe/Belgrade'  # по умолчанию
                }
                events.append(event_data)
                
            except Exception as e:
                continue
                
        print(f"✅ Спарсено событий из HTML: {len(events)}")
        return events
        
    except Exception as e:
        print(f"❌ Ошибка парсинга HTML: {str(e)}")
        return []

def get_forex_news_for_user(user_id=None, only_important=True, force_refresh=False):
    """Основная функция для получения новостей"""
    global news_cache
    
    current_time = time.time()
    
    # Проверяем кэш
    if (not force_refresh and 
        news_cache['data'] is not None and 
        news_cache['timestamp'] is not None and
        current_time - news_cache['timestamp'] < CACHE_DURATION):
        print("💾 Используем кэшированные данные")
        events = news_cache['data']
    else:
        print("🔄 Получаем свежие данные...")
        events = parse_forexfactory_selenium()
        news_cache['data'] = events
        news_cache['timestamp'] = current_time
        news_cache['last_updated'] = datetime.now().strftime('%H:%M:%S')
    
    # Отладочный вывод
    print("🔍 ОТЛАДКА - исходные времена из парсера:")
    for i, event in enumerate(events[:3]):
        print(f"   {i+1}. '{event['time']}' - {event['event']}")
    
    # Получаем часовой пояс пользователя
    user_timezone = 'Europe/Belgrade'  # по умолчанию Белград
    if user_id:
        try:
            from database import user_db
            user_timezone = user_db.get_user_timezone(user_id) or 'Europe/Belgrade'
            print(f"🌍 Часовой пояс пользователя: {user_timezone}")
        except Exception as e:
            print(f"❌ Ошибка получения часового пояса: {e}")
            user_timezone = 'Europe/Belgrade'
    
    # Конвертируем время из исходного пояса Forex Factory в пояс пользователя
    converted_events = []
    for event in events:
        original_time = event['time']
        original_timezone = event.get('original_timezone', 'Europe/Belgrade')
        
        try:
            # Если исходный пояс совпадает с пользовательским - не конвертируем
            if original_timezone == user_timezone:
                converted_time = original_time
                print(f"   ✅ '{original_time}' (без конвертации)")
            else:
                converted_time = convert_time_to_timezone(
                    original_time, 
                    from_tz=original_timezone,
                    to_tz=user_timezone
                )
                print(f"   📅 '{original_time}' ({original_timezone}) -> '{converted_time}' ({user_timezone})")
            
            converted_event = event.copy()
            converted_event['time'] = converted_time
            converted_events.append(converted_event)
            
        except Exception as e:
            print(f"❌ Ошибка при конвертации события: {e}")
            # В случае ошибки оставляем исходное время
            converted_events.append(event)
    
    # Фильтруем по важности если нужно
    if only_important:
        converted_events = [event for event in converted_events if event['impact'] == 'High']
    
    return converted_events

def filter_high_impact_events(events):
    """Фильтрация событий с высоким impact"""
    return [event for event in events if event.get('impact') == 'High']

def cleanup_parser():
    """Очистка ресурсов парсера"""
    print("🧹 Очистка парсера...")

def clear_news_cache():
    """Очистка кэша новостей"""
    global news_cache
    print("🗑️ Очистка кэша новостей...")
    news_cache = {
        'data': None,
        'timestamp': None,
        'last_updated': None
    }