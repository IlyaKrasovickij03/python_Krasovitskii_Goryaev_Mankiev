import logging

import telebot
from apscheduler.schedulers.background import BackgroundScheduler
from decouple import Config, RepositoryEnv

from repository import *

# ==============================
# Настройка логирования
# ==============================
logging.basicConfig(
        level=logging.INFO,  # Можно изменить на DEBUG для более подробного логирования
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler("bot.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )



# Доступ к переменным
config = Config(RepositoryEnv(".env"))
API_TOKEN = config("API_TOKEN") # Замените на токен вашего бота
bot = telebot.TeleBot(API_TOKEN, parse_mode=None)  # parse_mode будет устанавливаться в каждом методе отдельно

conn = sqlite3.connect('bot_database.db', check_same_thread=False)
cursor = conn.cursor()

init_tables(conn, cursor)

scheduler = BackgroundScheduler(timezone="Europe/Moscow")
scheduler.start()

# ==============================
# Хранение состояний пользователей
# ==============================
user_states = {}

# Определение различных состояний
STATE_MAIN_MENU = 'MAIN_MENU'
STATE_CREATE_EVENT_SELECT_USER = 'CREATE_EVENT_SELECT_USER'
STATE_CREATE_EVENT_DESCRIPTION = 'CREATE_EVENT_DESCRIPTION'
STATE_CREATE_EVENT_DATETIME = 'CREATE_EVENT_DATETIME'
STATE_ADD_CUSTOM_REMINDER = 'ADD_CUSTOM_REMINDER'
STATE_EDIT_EVENT_DESCRIPTION = 'EDIT_EVENT_DESCRIPTION'
STATE_EDIT_EVENT_DATETIME = 'EDIT_EVENT_DATETIME'
