# Forex News Bot Configuration
import os

# Telegram Bot - токен ТОЛЬКО из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')  # ← ИЗМЕНИТЬ!

# Timezone Settings
DEFAULT_TIMEZONE = os.getenv('DEFAULT_TIMEZONE', 'Europe/Belgrade')  # ← ИЗМЕНИТЬ!

# Parser Settings
PARSER_TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Notification Settings
NOTIFICATION_CHECK_INTERVAL = 60
PRE_NOTIFICATION_MINUTES = 15

# Selenium Settings
SELENIUM_HEADLESS = True